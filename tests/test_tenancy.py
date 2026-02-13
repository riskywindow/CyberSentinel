"""Tests for multi-tenancy isolation and query safety.

Covers:
  - Neo4j tenant isolation (all Cypher queries include tenant filters)
  - ClickHouse SafeQueryBuilder (rejects unsafe interpolation)
  - Cross-tenant leakage integration tests
  - SQL / Cypher injection security tests
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from storage.clickhouse.client import (
    ClickHouseClient,
    SafeQueryBuilder,
    UnsafeQueryError,
)
from storage.neo4j.client import Neo4jClient, _VALID_ENTITY_TYPES


# ===================================================================
# 1. Neo4j tenant isolation — unit tests
# ===================================================================

class TestNeo4jTenantIsolation:
    """Every Neo4j query must include tenant_id filtering."""

    def _make_client(self, tenant_id: str = "acme") -> Neo4jClient:
        """Return a Neo4jClient wired to a mock driver."""
        client = Neo4jClient(tenant_id=tenant_id)
        mock_driver = MagicMock()
        client._driver = mock_driver
        # session context-manager
        self._session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=self._session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        return client

    def _last_cypher(self) -> str:
        """Return the Cypher string from the most recent session.run() call."""
        assert self._session.run.called, "session.run() was never called"
        return self._session.run.call_args_list[-1][0][0]

    def _all_cyphers(self) -> List[str]:
        """Return all Cypher strings passed to session.run()."""
        return [c[0][0] for c in self._session.run.call_args_list]

    def _all_params(self) -> List[Dict[str, Any]]:
        """Return kwargs dicts for every session.run() call."""
        return [c[1] for c in self._session.run.call_args_list]

    # -- constructor --

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            Neo4jClient(tenant_id="")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            Neo4jClient(tenant_id="   ")

    def test_tenant_id_stored(self):
        c = Neo4jClient(tenant_id="  acme  ")
        assert c.tenant_id == "acme"

    # -- create_host --

    def test_create_host_includes_tenant(self):
        c = self._make_client("tenant_a")
        c.create_host("h1", "web-01")
        cypher = self._last_cypher()
        assert "tenant_id: $tid" in cypher
        params = self._session.run.call_args[1]
        assert params["tid"] == "tenant_a"

    # -- create_process --

    def test_create_process_includes_tenant(self):
        c = self._make_client("tenant_b")
        c.create_process("p1", 1234, "sshd", "h1")
        cyphers = self._all_cyphers()
        for cypher in cyphers:
            assert "tenant_id: $tid" in cypher or "tenant_id" in cypher

    # -- create_connection --

    def test_create_connection_includes_tenant(self):
        c = self._make_client("t1")
        c.create_connection("p1", "10.0.0.1", 443)
        cypher = self._last_cypher()
        assert "tenant_id: $tid" in cypher

    # -- create_file_access --

    def test_create_file_access_includes_tenant(self):
        c = self._make_client("t1")
        c.create_file_access("p1", "/etc/passwd")
        cypher = self._last_cypher()
        assert "tenant_id: $tid" in cypher

    # -- create_ttp_indication --

    def test_create_ttp_indication_includes_tenant(self):
        c = self._make_client("t1")
        c.create_ttp_indication("h1", "Host", "ttp1", "T1059", 0.9, 1700000000)
        for cypher in self._all_cyphers():
            assert "tenant_id: $tid" in cypher

    def test_create_ttp_indication_rejects_invalid_entity_type(self):
        c = self._make_client("t1")
        with pytest.raises(ValueError, match="Invalid entity_type"):
            c.create_ttp_indication("h1", "FakeType", "ttp1", "T1059", 0.9, 1700000000)

    # -- get_incident_subgraph --

    def test_get_incident_subgraph_includes_tenant(self):
        c = self._make_client("t1")
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: [] if k in ("nodes", "relationships") else None
        self._session.run.return_value.single.return_value = mock_record
        c.get_incident_subgraph(["e1", "e2"])
        cypher = self._last_cypher()
        assert "tenant_id = $tid" in cypher

    # -- query_ttp_indicators --

    def test_query_ttp_indicators_includes_tenant(self):
        c = self._make_client("t1")
        self._session.run.return_value = iter([])
        c.query_ttp_indicators("T1059")
        cypher = self._last_cypher()
        assert "t.tenant_id = $tid" in cypher
        assert "e.tenant_id = $tid" in cypher

    # -- sync_attack_to_graph --

    def test_sync_attack_to_graph_includes_tenant(self):
        c = self._make_client("t1")
        c.sync_attack_to_graph([{"id": "T1059", "name": "Scripting", "tactic": "execution"}])
        for cypher in self._all_cyphers():
            assert "tenant_id" in cypher
        for params in self._all_params():
            assert params.get("tid") == "t1"


# ===================================================================
# 2. ClickHouse SafeQueryBuilder — unit tests
# ===================================================================

class TestSafeQueryBuilder:
    """SafeQueryBuilder must always inject tenant_id and reject injections."""

    def test_basic_build(self):
        qb = SafeQueryBuilder("telemetry", "acme")
        sql, params = qb.build()
        assert "tenant_id = %(tenant_id)s" in sql
        assert params["tenant_id"] == "acme"
        assert "FROM telemetry" in sql

    def test_columns_and_where(self):
        qb = (
            SafeQueryBuilder("alerts", "t1")
            .columns("ts", "id", "severity")
            .where("severity = %(sev)s", sev="high")
            .order_by("ts DESC")
            .limit(10)
        )
        sql, params = qb.build()
        assert "SELECT ts, id, severity FROM alerts" in sql
        assert "tenant_id = %(tenant_id)s" in sql
        assert "severity = %(sev)s" in sql
        assert "ORDER BY ts DESC" in sql
        assert "LIMIT 10" in sql
        assert params["tenant_id"] == "t1"
        assert params["sev"] == "high"

    def test_group_by(self):
        qb = SafeQueryBuilder("findings", "t1").group_by("incident_id")
        sql, _ = qb.build()
        assert "GROUP BY incident_id" in sql

    # -- injection rejection --

    def test_rejects_drop_in_table(self):
        with pytest.raises(UnsafeQueryError):
            SafeQueryBuilder("alerts; DROP TABLE alerts", "t1")

    def test_rejects_sql_comment_in_param(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.where("id = %(id)s", id="abc -- drop")

    def test_rejects_union_select(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.where("1=1 UNION SELECT * FROM secrets")

    def test_rejects_semicolon_drop(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.where("1=1; DROP TABLE alerts")

    def test_rejects_block_comment(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.where("id = %(id)s", id="x /* comment */")

    def test_rejects_tautology(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.where("' OR '1'='1")

    def test_rejects_negative_limit(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.limit(-1)

    def test_rejects_non_int_limit(self):
        qb = SafeQueryBuilder("alerts", "t1")
        with pytest.raises(UnsafeQueryError):
            qb.limit("100; DROP")  # type: ignore

    def test_rejects_unsafe_table_name(self):
        with pytest.raises(UnsafeQueryError):
            SafeQueryBuilder("alerts;DROP", "t1")

    def test_rejects_injection_in_tenant_id(self):
        with pytest.raises(UnsafeQueryError):
            SafeQueryBuilder("alerts", "'; DROP TABLE alerts --")

    def test_tenant_always_in_where(self):
        """No matter what, tenant_id filter is present."""
        qb = SafeQueryBuilder("telemetry", "xyz")
        sql, params = qb.build()
        assert "tenant_id = %(tenant_id)s" in sql
        assert params["tenant_id"] == "xyz"


# ===================================================================
# 3. ClickHouseClient — tenant scoping
# ===================================================================

class TestClickHouseClientTenancy:
    """ClickHouseClient must stamp tenant_id on every insert and filter on every query."""

    def test_empty_tenant_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            ClickHouseClient(tenant_id="")

    def test_insert_telemetry_includes_tenant(self):
        ch = ClickHouseClient(tenant_id="acme")
        ch.client = MagicMock()
        ts = datetime(2024, 1, 1)
        ch.insert_telemetry(ts, "web-01", "syslog", '{"event":"test"}')
        args = ch.client.insert.call_args
        row = args[0][1][0]
        # Row should be: [ts, tenant_id, host, source, ecs_json]
        assert row[1] == "acme"

    def test_insert_alert_includes_tenant(self):
        ch = ClickHouseClient(tenant_id="beta")
        ch.client = MagicMock()
        ts = datetime(2024, 1, 1)
        ch.insert_alert(ts, "a1", "high", ["t1"], ["e1"], "summary", "ref")
        row = ch.client.insert.call_args[0][1][0]
        assert row[1] == "beta"

    def test_insert_finding_includes_tenant(self):
        ch = ClickHouseClient(tenant_id="gamma")
        ch.client = MagicMock()
        ts = datetime(2024, 1, 1)
        ch.insert_finding(ts, "f1", "inc1", "hyp", ["n1"], ["T1059"], "{}")
        row = ch.client.insert.call_args[0][1][0]
        assert row[1] == "gamma"

    def test_insert_action_plan_includes_tenant(self):
        ch = ClickHouseClient(tenant_id="delta")
        ch.client = MagicMock()
        ts = datetime(2024, 1, 1)
        ch.insert_action_plan(ts, "inc1", ["pb1"], "{}", "high")
        row = ch.client.insert.call_args[0][1][0]
        assert row[1] == "delta"

    def test_insert_playbook_run_includes_tenant(self):
        ch = ClickHouseClient(tenant_id="epsilon")
        ch.client = MagicMock()
        ts = datetime(2024, 1, 1)
        ch.insert_playbook_run(ts, "pb1", "inc1", "running", "log line")
        row = ch.client.insert.call_args[0][1][0]
        assert row[1] == "epsilon"

    def test_query_telemetry_includes_tenant_filter(self):
        ch = ClickHouseClient(tenant_id="acme")
        ch.client = MagicMock()
        ch.client.query.return_value = MagicMock(result_rows=[])
        ch.query_telemetry(host="web-01")
        query_str = ch.client.query.call_args[0][0]
        assert "tenant_id = %(tenant_id)s" in query_str
        params = ch.client.query.call_args[1]["parameters"]
        assert params["tenant_id"] == "acme"

    def test_query_alerts_includes_tenant_filter(self):
        ch = ClickHouseClient(tenant_id="acme")
        ch.client = MagicMock()
        ch.client.query.return_value = MagicMock(result_rows=[])
        ch.query_alerts_for_incident("inc1")
        query_str = ch.client.query.call_args[0][0]
        assert "tenant_id = %(tenant_id)s" in query_str

    def test_query_builder_factory(self):
        ch = ClickHouseClient(tenant_id="zeta")
        qb = ch.query_builder("telemetry")
        sql, params = qb.build()
        assert params["tenant_id"] == "zeta"


# ===================================================================
# 4. Cross-tenant leakage — integration test (mocked backends)
# ===================================================================

class TestCrossTenantLeakage:
    """Write data for two tenants and verify no cross-tenant leakage."""

    def _mock_ch(self, tenant_id: str) -> ClickHouseClient:
        ch = ClickHouseClient(tenant_id=tenant_id)
        ch.client = MagicMock()
        return ch

    def _mock_neo4j(self, tenant_id: str) -> Neo4jClient:
        client = Neo4jClient(tenant_id=tenant_id)
        mock_driver = MagicMock()
        client._driver = mock_driver
        session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        return client, session

    def test_clickhouse_insert_different_tenants(self):
        """Two tenants insert data — each row has the correct tenant_id."""
        ch_a = self._mock_ch("tenant_a")
        ch_b = self._mock_ch("tenant_b")

        ts = datetime(2024, 6, 1)
        ch_a.insert_telemetry(ts, "host-a", "syslog", '{"a":1}')
        ch_b.insert_telemetry(ts, "host-b", "syslog", '{"b":2}')

        row_a = ch_a.client.insert.call_args[0][1][0]
        row_b = ch_b.client.insert.call_args[0][1][0]

        assert row_a[1] == "tenant_a"
        assert row_b[1] == "tenant_b"

    def test_clickhouse_query_different_tenants(self):
        """Queries for tenant_a include only tenant_a filter."""
        ch_a = self._mock_ch("tenant_a")
        ch_a.client.query.return_value = MagicMock(result_rows=[])

        ch_a.query_telemetry()
        query_str = ch_a.client.query.call_args[0][0]
        params = ch_a.client.query.call_args[1]["parameters"]

        assert "tenant_id = %(tenant_id)s" in query_str
        assert params["tenant_id"] == "tenant_a"
        # Must not contain tenant_b
        assert "tenant_b" not in query_str

    def test_neo4j_create_host_different_tenants(self):
        """Hosts created by different tenants carry different tenant_id params."""
        neo_a, sess_a = self._mock_neo4j("tenant_a")
        neo_b, sess_b = self._mock_neo4j("tenant_b")

        neo_a.create_host("h1", "web-01")
        neo_b.create_host("h1", "web-01")

        params_a = sess_a.run.call_args[1]
        params_b = sess_b.run.call_args[1]

        assert params_a["tid"] == "tenant_a"
        assert params_b["tid"] == "tenant_b"

    def test_neo4j_query_ttp_different_tenants(self):
        """TTP queries scope to correct tenant."""
        neo_a, sess_a = self._mock_neo4j("tenant_a")
        neo_b, sess_b = self._mock_neo4j("tenant_b")

        sess_a.run.return_value = iter([])
        sess_b.run.return_value = iter([])

        neo_a.query_ttp_indicators("T1059")
        neo_b.query_ttp_indicators("T1059")

        cypher_a = sess_a.run.call_args[0][0]
        cypher_b = sess_b.run.call_args[0][0]

        params_a = sess_a.run.call_args[1]
        params_b = sess_b.run.call_args[1]

        assert params_a["tid"] == "tenant_a"
        assert params_b["tid"] == "tenant_b"

        # Both queries contain tenant filter
        assert "tenant_id = $tid" in cypher_a
        assert "tenant_id = $tid" in cypher_b


# ===================================================================
# 5. Security tests — injection attempts
# ===================================================================

class TestInjectionPrevention:
    """Injection-like strings must be caught by SafeQueryBuilder."""

    INJECTION_PAYLOADS = [
        "'; DROP TABLE telemetry --",
        "1; DELETE FROM alerts",
        "x UNION SELECT * FROM secrets",
        "x UNION ALL SELECT 1,2,3",
        "admin'-- ",
        "1 /* bypass */",
        "' OR '1'='1",
        "' AND 'x'='x",
        "'; TRUNCATE TABLE findings --",
        "x; ALTER TABLE telemetry ADD COLUMN evil String",
        "x; CREATE TABLE pwned (id Int32) ENGINE=Memory",
        "x; INSERT INTO alerts VALUES ('hacked')",
        "x; UPDATE alerts SET severity='hacked'",
    ]

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_query_builder_rejects_injection_in_param(self, payload):
        qb = SafeQueryBuilder("telemetry", "safe_tenant")
        with pytest.raises(UnsafeQueryError):
            qb.where("host = %(host)s", host=payload)

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_query_builder_rejects_injection_in_clause(self, payload):
        qb = SafeQueryBuilder("telemetry", "safe_tenant")
        with pytest.raises(UnsafeQueryError):
            qb.where(payload)

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_query_builder_rejects_injection_in_tenant_id(self, payload):
        with pytest.raises(UnsafeQueryError):
            SafeQueryBuilder("telemetry", payload)

    def test_safe_values_pass(self):
        """Normal values must not trigger false positives."""
        qb = (
            SafeQueryBuilder("telemetry", "acme_corp")
            .columns("ts", "host", "source")
            .where("host = %(host)s", host="web-server-01")
            .where("source = %(source)s", source="syslog")
            .order_by("ts DESC")
            .limit(100)
        )
        sql, params = qb.build()
        assert "tenant_id = %(tenant_id)s" in sql
        assert params["host"] == "web-server-01"

    def test_neo4j_entity_type_whitelist(self):
        """Only whitelisted entity types can be used in Cypher formatting."""
        c = Neo4jClient(tenant_id="t1")
        c._driver = MagicMock()
        sess = MagicMock()
        c._driver.session.return_value.__enter__ = MagicMock(return_value=sess)
        c._driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # Valid type should succeed
        c.create_ttp_indication("h1", "Host", "ttp1", "T1059", 0.9, 1700000000)
        assert sess.run.called

        # Injection in entity_type should fail
        with pytest.raises(ValueError):
            c.create_ttp_indication("h1", "Host} DETACH DELETE n //", "ttp1", "T1059", 0.9, 1700000000)


# ===================================================================
# 6. Graph sync tenant awareness
# ===================================================================

class TestGraphSyncTenancy:
    """GraphSynchronizer and KnowledgeGraphManager must pass tenant_id."""

    def test_graph_synchronizer_inherits_tenant(self):
        from knowledge.graph_sync import GraphSynchronizer
        neo = Neo4jClient(tenant_id="sync_tenant")
        neo._driver = MagicMock()
        gs = GraphSynchronizer(neo)
        assert gs._tid == "sync_tenant"

    def test_knowledge_graph_manager_inherits_tenant(self):
        from knowledge.graph_sync import KnowledgeGraphManager
        neo = Neo4jClient(tenant_id="mgr_tenant")
        neo._driver = MagicMock()
        with patch("knowledge.graph_sync.KnowledgeCorpus"):
            mgr = KnowledgeGraphManager(neo)
        assert mgr._tid == "mgr_tenant"


# ===================================================================
# 7. Incident service uses query builder (tenant-scoped)
# ===================================================================

class TestIncidentServiceTenancy:
    """incident_svc must use SafeQueryBuilder (tenant-scoped) instead of raw SQL."""

    def test_list_incidents_uses_query_builder(self):
        from api.services.incident_svc import list_incidents

        ch = ClickHouseClient(tenant_id="inc_tenant")
        ch.client = MagicMock()
        ch.client.query.return_value = MagicMock(result_rows=[])

        list_incidents(ch, limit=50)

        query_str = ch.client.query.call_args[0][0]
        params = ch.client.query.call_args[1]["parameters"]

        assert "tenant_id = %(tenant_id)s" in query_str
        assert params["tenant_id"] == "inc_tenant"
        # Must NOT use .format() style interpolation
        assert "{limit}" not in query_str

    def test_get_incident_detail_uses_query_builder(self):
        from api.services.incident_svc import get_incident_detail

        ch = ClickHouseClient(tenant_id="det_tenant")
        ch.client = MagicMock()
        ch.client.query.return_value = MagicMock(result_rows=[])

        neo = Neo4jClient(tenant_id="det_tenant")
        neo._driver = MagicMock()

        result = get_incident_detail(ch, neo, "INC-001")

        query_str = ch.client.query.call_args[0][0]
        params = ch.client.query.call_args[1]["parameters"]

        assert "tenant_id = %(tenant_id)s" in query_str
        assert params["tenant_id"] == "det_tenant"
        assert params["incident_id"] == "INC-001"

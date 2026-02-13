"""ClickHouse client for CyberSentinel with tenant isolation and safe queries."""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

try:
    import clickhouse_connect
except ImportError:
    clickhouse_connect = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SafeQueryBuilder — prevents SQL injection via string interpolation
# ---------------------------------------------------------------------------

# Only allow simple identifiers in column/table positions (letters, digits, underscore)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Patterns that indicate dangerous string interpolation attempts
_INJECTION_PATTERNS = [
    re.compile(r";\s*(DROP|DELETE|ALTER|INSERT|UPDATE|CREATE|TRUNCATE)", re.IGNORECASE),
    re.compile(r"--"),                     # SQL comment injection
    re.compile(r"/\*"),                    # block comment injection
    re.compile(r"'\s*(OR|AND)\s+'", re.IGNORECASE),   # tautology injection
    re.compile(r"UNION\s+(ALL\s+)?SELECT", re.IGNORECASE),
]


class UnsafeQueryError(Exception):
    """Raised when a query or parameter contains injection-like patterns."""


class SafeQueryBuilder:
    """Build ClickHouse SELECT queries with mandatory tenant_id filtering.

    All values go through driver-level parameterization (``%(name)s`` syntax
    for ``clickhouse-connect``).  The builder **rejects** any query or
    parameter value that contains known injection patterns.
    """

    def __init__(self, table: str, tenant_id: str) -> None:
        if not _SAFE_IDENTIFIER.match(table):
            raise UnsafeQueryError(f"Invalid table name: {table!r}")
        self._validate_no_injection(tenant_id, "tenant_id")
        self._table = table
        self._tenant_id = tenant_id
        self._columns: List[str] = ["*"]
        self._where: List[str] = ["tenant_id = %(tenant_id)s"]
        self._params: Dict[str, Any] = {"tenant_id": tenant_id}
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._group_by: Optional[str] = None

    # -- fluent API --

    def columns(self, *cols: str) -> "SafeQueryBuilder":
        for c in cols:
            if not _SAFE_IDENTIFIER.match(c.split("(")[0].strip()):
                # Allow simple aggregate expressions like count() but not arbitrary SQL
                if not re.match(r"^[A-Za-z_]+\(.*\)$", c):
                    raise UnsafeQueryError(f"Invalid column expression: {c!r}")
        self._columns = list(cols)
        return self

    def where(self, clause: str, **params: Any) -> "SafeQueryBuilder":
        self._validate_clause(clause)
        for key, val in params.items():
            if isinstance(val, str):
                self._validate_no_injection(val, key)
        self._where.append(clause)
        self._params.update(params)
        return self

    def order_by(self, expr: str) -> "SafeQueryBuilder":
        self._validate_clause(expr)
        self._order_by = expr
        return self

    def group_by(self, expr: str) -> "SafeQueryBuilder":
        self._validate_clause(expr)
        self._group_by = expr
        return self

    def limit(self, n: int) -> "SafeQueryBuilder":
        if not isinstance(n, int) or n < 0:
            raise UnsafeQueryError(f"LIMIT must be a non-negative integer, got {n!r}")
        self._limit = n
        return self

    def build(self) -> Tuple[str, Dict[str, Any]]:
        """Return ``(query_string, parameters)`` ready for the driver."""
        cols = ", ".join(self._columns)
        sql = f"SELECT {cols} FROM {self._table}"
        sql += " WHERE " + " AND ".join(self._where)
        if self._group_by:
            sql += f" GROUP BY {self._group_by}"
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"
        if self._limit is not None:
            sql += f" LIMIT {self._limit}"
        return sql, dict(self._params)

    # -- validation helpers --

    @staticmethod
    def _validate_no_injection(value: str, label: str = "value") -> None:
        for pat in _INJECTION_PATTERNS:
            if pat.search(value):
                raise UnsafeQueryError(
                    f"Potential injection detected in {label}: {value!r}"
                )

    @staticmethod
    def _validate_clause(clause: str) -> None:
        for pat in _INJECTION_PATTERNS:
            if pat.search(clause):
                raise UnsafeQueryError(
                    f"Potential injection in clause: {clause!r}"
                )


# ---------------------------------------------------------------------------
# ClickHouseClient
# ---------------------------------------------------------------------------

class ClickHouseClient:
    """ClickHouse client with mandatory tenant isolation.

    Every insert stamps ``tenant_id``; every query filters by it.
    """

    def __init__(self, host: str = "localhost", port: int = 8123,
                 database: str = "cybersentinel", username: str = "default",
                 password: str = "", tenant_id: str = "default"):
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be a non-empty string")
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.tenant_id = tenant_id.strip()
        self.client = None

    def connect(self) -> None:
        """Connect to ClickHouse server."""
        if clickhouse_connect is None:
            raise ImportError("clickhouse-connect not installed. Run: pip install clickhouse-connect")

        # First connect to default database to create our database if needed
        default_client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            database="default",
            username=self.username,
            password=self.password
        )

        # Create database if it doesn't exist
        try:
            default_client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
        except Exception as e:
            logger.warning(f"Could not create database {self.database}: {e}")
        finally:
            default_client.close()

        # Now connect to our target database
        self.client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.username,
            password=self.password
        )

        logger.info(f"Connected to ClickHouse at {self.host}:{self.port}/{self.database} (tenant={self.tenant_id})")

    def disconnect(self) -> None:
        """Disconnect from ClickHouse server."""
        if self.client:
            self.client.close()
            self.client = None

    def install_schema(self) -> None:
        """Install the ClickHouse schema."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")

        schema_path = Path(__file__).parent / "ddl.sql"
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        # Execute each statement separately
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        for stmt in statements:
            try:
                self.client.command(stmt)
                logger.debug(f"Executed: {stmt[:50]}...")
            except Exception as e:
                logger.error(f"Failed to execute statement: {stmt[:50]}...: {e}")
                raise

        logger.info("ClickHouse schema installed successfully")

    # ------------------------------------------------------------------
    # Query builder factory
    # ------------------------------------------------------------------
    def query_builder(self, table: str) -> SafeQueryBuilder:
        """Return a SafeQueryBuilder pre-scoped to the current tenant."""
        return SafeQueryBuilder(table, self.tenant_id)

    # ------------------------------------------------------------------
    # Inserts — all include tenant_id
    # ------------------------------------------------------------------
    def insert_telemetry(self, ts: datetime, host: str, source: str, ecs_json: str) -> None:
        """Insert telemetry record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        self.client.insert('telemetry', [[ts, self.tenant_id, host, source, ecs_json]])

    def insert_alert(self, ts: datetime, alert_id: str, severity: str,
                    tags: List[str], entities: List[str], summary: str,
                    evidence_ref: str) -> None:
        """Insert alert record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        self.client.insert('alerts', [[ts, self.tenant_id, alert_id, severity, tags,
                                       entities, summary, evidence_ref]])

    def insert_finding(self, ts: datetime, finding_id: str, incident_id: str,
                      hypothesis: str, graph_nodes: List[str],
                      candidate_ttps: List[str], rationale_json: str) -> None:
        """Insert finding record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        self.client.insert('findings', [[ts, self.tenant_id, finding_id, incident_id,
                                        hypothesis, graph_nodes, candidate_ttps,
                                        rationale_json]])

    def insert_action_plan(self, ts: datetime, incident_id: str,
                          playbooks: List[str], change_set_json: str,
                          risk_tier: str) -> None:
        """Insert action plan record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        self.client.insert('action_plans', [[ts, self.tenant_id, incident_id, playbooks,
                                            change_set_json, risk_tier]])

    def insert_playbook_run(self, ts: datetime, playbook_id: str,
                           incident_id: str, status: str, logs: str) -> None:
        """Insert playbook run record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        self.client.insert('playbook_runs', [[ts, self.tenant_id, playbook_id, incident_id,
                                             status, logs]])

    # ------------------------------------------------------------------
    # Queries — all parameterized, all scoped by tenant_id
    # ------------------------------------------------------------------
    def query_telemetry(self, host: Optional[str] = None,
                       source: Optional[str] = None,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Query telemetry records with optional filters."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")

        qb = self.query_builder("telemetry").columns(
            "ts", "host", "source", "ecs_json"
        ).order_by("ts DESC").limit(int(limit))

        if host:
            qb.where("host = %(host)s", host=host)
        if source:
            qb.where("source = %(source)s", source=source)
        if start_time:
            qb.where("ts >= %(start_time)s", start_time=start_time)
        if end_time:
            qb.where("ts <= %(end_time)s", end_time=end_time)

        query, params = qb.build()
        result = self.client.query(query, parameters=params)
        return [
            {'ts': row[0], 'host': row[1], 'source': row[2], 'ecs_json': row[3]}
            for row in result.result_rows
        ]

    def query_alerts_for_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        """Query alerts related to an incident (by time correlation)."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")

        qb = (
            self.query_builder("alerts")
            .columns("ts", "id", "severity", "tags", "entities", "summary", "evidence_ref")
            .order_by("ts DESC")
            .limit(50)
        )

        query, params = qb.build()
        result = self.client.query(query, parameters=params)
        return [
            {
                'ts': row[0], 'id': row[1], 'severity': row[2],
                'tags': row[3], 'entities': row[4],
                'summary': row[5], 'evidence_ref': row[6]
            }
            for row in result.result_rows
        ]

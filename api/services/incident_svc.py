"""Incident service — ClickHouse queries + Neo4j enrichment (tenant-aware)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from storage import ClickHouseClient, Neo4jClient

logger = logging.getLogger(__name__)


def list_incidents(ch: ClickHouseClient,
                   severity: Optional[str] = None,
                   status: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
    """Return incident summaries grouped from the *findings* table.

    All queries are scoped to the tenant configured on ``ch``.
    """
    qb = (
        ch.query_builder("findings")
        .columns(
            "incident_id",
            "min(ts)",
            "max(ts)",
            "groupUniqArray(hypothesis)",
            "groupUniqArrayArray(graph_nodes)",
            "groupUniqArrayArray(candidate_ttps)",
            "count()",
        )
        .group_by("incident_id")
        .order_by("max(ts) DESC")
        .limit(int(limit))
    )

    query, params = qb.build()
    result = ch.client.query(query, parameters=params)

    rows: List[Dict[str, Any]] = []
    for r in result.result_rows:
        incident_id, first_seen, last_seen, hypotheses, hosts, techniques, cnt = r
        rows.append({
            "id": incident_id,
            "title": hypotheses[0] if hypotheses else incident_id,
            "severity": "medium",
            "status": "open",
            "timestamp": str(first_seen),
            "affectedHosts": list(hosts),
            "techniques": list(techniques),
            "analyst": "",
            "alertCount": cnt,
        })

    # Optional client-side filters (CH doesn't store severity/status on findings)
    if severity:
        rows = [r for r in rows if r["severity"] == severity]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return rows


def get_incident_detail(ch: ClickHouseClient,
                        neo4j: Neo4jClient,
                        incident_id: str) -> Optional[Dict[str, Any]]:
    """Return a single incident with timeline, alerts and Neo4j subgraph.

    All queries are scoped to the tenant configured on ``ch`` / ``neo4j``.
    """
    qb = (
        ch.query_builder("findings")
        .columns("ts", "id", "hypothesis", "graph_nodes",
                 "candidate_ttps", "rationale_json")
        .where("incident_id = %(incident_id)s", incident_id=incident_id)
        .order_by("ts")
    )

    query, params = qb.build()
    result = ch.client.query(query, parameters=params)
    findings = result.result_rows

    if not findings:
        return None

    hosts: set[str] = set()
    techniques: set[str] = set()
    timeline: List[Dict[str, Any]] = []

    for ts, finding_id, hypothesis, graph_nodes, candidate_ttps, rationale_json in findings:
        hosts.update(graph_nodes or [])
        techniques.update(candidate_ttps or [])
        rationale = {}
        if rationale_json:
            try:
                rationale = json.loads(rationale_json)
            except (json.JSONDecodeError, TypeError):
                pass
        timeline.append({
            "ts": str(ts),
            "findingId": finding_id,
            "hypothesis": hypothesis,
            "rationale": rationale,
        })

    # Best-effort alert enrichment
    alerts: List[Dict[str, Any]] = []
    try:
        alerts = ch.query_alerts_for_incident(incident_id)
    except Exception:
        logger.debug("Could not fetch alerts for %s", incident_id, exc_info=True)

    # Best-effort Neo4j subgraph
    graph = {"nodes": [], "relationships": []}
    try:
        entity_ids = list(hosts)
        if entity_ids:
            graph = neo4j.get_incident_subgraph(entity_ids)
    except Exception:
        logger.debug("Could not fetch subgraph for %s", incident_id, exc_info=True)

    first_ts = findings[0][0]
    hypotheses = [f[2] for f in findings if f[2]]

    return {
        "id": incident_id,
        "title": hypotheses[0] if hypotheses else incident_id,
        "severity": "medium",
        "status": "open",
        "timestamp": str(first_ts),
        "affectedHosts": sorted(hosts),
        "techniques": sorted(techniques),
        "analyst": "",
        "alertCount": len(alerts),
        "description": hypotheses[0] if hypotheses else "",
        "timeline": timeline,
        "entities": alerts,
        "artifacts": [],
        "graph": graph,
    }

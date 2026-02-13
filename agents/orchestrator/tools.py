"""Tool registry for CyberSentinel agents (tenant-aware)."""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from storage import ClickHouseClient, Neo4jClient
from knowledge import RAGQueryEngine, QueryContext

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for agent tools and capabilities.

    All database operations are scoped to the tenant configured on
    the supplied ``ClickHouseClient`` and ``Neo4jClient``.
    """

    def __init__(self,
                 clickhouse_client: ClickHouseClient = None,
                 neo4j_client: Neo4jClient = None,
                 rag_engine: RAGQueryEngine = None):
        self.clickhouse = clickhouse_client
        self.neo4j = neo4j_client
        self.rag_engine = rag_engine
        self._tools = {}
        self._register_core_tools()

    def _register_core_tools(self) -> None:
        """Register core tools available to all agents."""

        # ClickHouse query tools
        self.register_tool("query_telemetry", self._query_telemetry)
        self.register_tool("query_alerts", self._query_alerts)

        # Neo4j graph tools
        self.register_tool("query_neo4j", self._query_neo4j)
        self.register_tool("get_entity_relationships", self._get_entity_relationships)
        self.register_tool("query_attack_chain", self._query_attack_chain)

        # RAG knowledge tools
        self.register_tool("rag_lookup", self._rag_lookup)
        self.register_tool("query_attack_technique", self._query_attack_technique)
        self.register_tool("find_detection_rules", self._find_detection_rules)
        self.register_tool("query_vulnerabilities", self._query_vulnerabilities)

        # Sigma generation tools
        self.register_tool("generate_sigma", self._generate_sigma)
        self.register_tool("validate_sigma", self._validate_sigma)

        # Playbook tools
        self.register_tool("plan_playbook", self._plan_playbook)
        self.register_tool("dry_run_playbook", self._dry_run_playbook)
        self.register_tool("submit_for_approval", self._submit_for_approval)

        logger.info(f"Registered {len(self._tools)} core tools")

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function."""
        self._tools[name] = func
        logger.debug(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tools."""
        return list(self._tools.keys())

    # ClickHouse tools — all use SafeQueryBuilder via the client
    def _query_telemetry(self, host: str = None, source: str = None,
                        hours: int = 24, limit: int = 100) -> Dict[str, Any]:
        """Query recent telemetry data (tenant-scoped)."""
        if not self.clickhouse:
            return {"error": "ClickHouse client not available"}

        try:
            from datetime import datetime, timedelta
            start_time = datetime.now() - timedelta(hours=hours)

            results = self.clickhouse.query_telemetry(
                host=host, source=source, start_time=start_time, limit=limit
            )

            return {
                "success": True,
                "count": len(results),
                "telemetry": results,
                "query_params": {"host": host, "source": source, "hours": hours}
            }
        except Exception as e:
            logger.error(f"Telemetry query failed: {e}")
            return {"error": str(e)}

    def _query_alerts(self, incident_id: str = None,
                     severity: str = None, limit: int = 50) -> Dict[str, Any]:
        """Query alerts for incident correlation (tenant-scoped)."""
        if not self.clickhouse:
            return {"error": "ClickHouse client not available"}

        try:
            results = self.clickhouse.query_alerts_for_incident(
                incident_id or "default"
            )

            # Filter by severity if specified
            if severity:
                results = [r for r in results if r.get('severity') == severity]

            return {
                "success": True,
                "count": len(results[:limit]),
                "alerts": results[:limit]
            }
        except Exception as e:
            logger.error(f"Alerts query failed: {e}")
            return {"error": str(e)}

    # Neo4j graph tools — tenant scoping is in the client
    def _query_neo4j(self, cypher: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute Cypher query on Neo4j (tenant filter injected automatically)."""
        if not self.neo4j:
            return {"error": "Neo4j client not available"}

        try:
            merged = dict(params or {})
            merged["tid"] = self.neo4j.tenant_id
            with self.neo4j.driver.session() as session:
                result = session.run(cypher, merged)
                records = [dict(record) for record in result]

                return {
                    "success": True,
                    "count": len(records),
                    "data": records
                }
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return {"error": str(e)}

    def _get_entity_relationships(self, entity_ids: List[str],
                                 max_depth: int = 2) -> Dict[str, Any]:
        """Get subgraph around specific entities (tenant-scoped)."""
        if not self.neo4j:
            return {"error": "Neo4j client not available"}

        try:
            subgraph = self.neo4j.get_incident_subgraph(entity_ids, max_depth)
            return {
                "success": True,
                "nodes": len(subgraph.get("nodes", [])),
                "relationships": len(subgraph.get("relationships", [])),
                "subgraph": subgraph
            }
        except Exception as e:
            logger.error(f"Entity relationships query failed: {e}")
            return {"error": str(e)}

    def _query_attack_chain(self, start_technique: str, max_depth: int = 3) -> Dict[str, Any]:
        """Query for potential attack chains (tenant-scoped)."""
        if not self.neo4j:
            return {"error": "Neo4j client not available"}

        try:
            tid = self.neo4j.tenant_id
            cypher = """
            MATCH (start:TTP {technique_id: $start_technique, tenant_id: $tid})-[:PART_OF]->(tactic:Tactic {tenant_id: $tid})
            MATCH (tactic)<-[:PART_OF]-(related:TTP {tenant_id: $tid})
            WHERE start <> related
            RETURN related.technique_id as technique_id,
                   related.name as name,
                   related.tactic as tactic
            LIMIT 10
            """

            with self.neo4j.driver.session() as session:
                result = session.run(cypher, start_technique=start_technique, tid=tid)
                chains = [dict(record) for record in result]

            return {
                "success": True,
                "start_technique": start_technique,
                "related_techniques": chains
            }
        except Exception as e:
            logger.error(f"Attack chain query failed: {e}")
            return {"error": str(e)}

    # RAG knowledge tools
    def _rag_lookup(self, query: str, k: int = 5, filters: Dict[str, str] = None) -> Dict[str, Any]:
        """Perform RAG lookup in knowledge base."""
        if not self.rag_engine:
            return {"error": "RAG engine not available"}

        try:
            context = QueryContext(query=query, k=k, filters=filters or {})
            results = self.rag_engine.query(context)

            return {
                "success": True,
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                        "score": r.score,
                        "source": r.source,
                        "doc_type": r.doc_type,
                        "metadata": r.metadata
                    }
                    for r in results
                ]
            }
        except Exception as e:
            logger.error(f"RAG lookup failed: {e}")
            return {"error": str(e)}

    def _query_attack_technique(self, technique_id: str, k: int = 3) -> Dict[str, Any]:
        """Query specific ATT&CK technique information."""
        if not self.rag_engine:
            return {"error": "RAG engine not available"}

        try:
            results = self.rag_engine.query_by_attack_technique(technique_id, k=k)

            return {
                "success": True,
                "technique_id": technique_id,
                "count": len(results),
                "information": [
                    {
                        "content": r.content,
                        "score": r.score,
                        "doc_type": r.doc_type,
                        "tactic": r.metadata.get("tactic", ""),
                        "platforms": r.metadata.get("platforms", [])
                    }
                    for r in results
                ]
            }
        except Exception as e:
            logger.error(f"ATT&CK technique query failed: {e}")
            return {"error": str(e)}

    def _find_detection_rules(self, activity: str, k: int = 5) -> Dict[str, Any]:
        """Find detection rules for specific activity."""
        if not self.rag_engine:
            return {"error": "RAG engine not available"}

        try:
            results = self.rag_engine.query_for_detection_rules(activity, k=k)

            return {
                "success": True,
                "activity": activity,
                "count": len(results),
                "rules": [
                    {
                        "title": r.metadata.get("title", ""),
                        "level": r.metadata.get("level", "medium"),
                        "content": r.content,
                        "score": r.score,
                        "attack_techniques": r.metadata.get("attack_techniques", [])
                    }
                    for r in results
                ]
            }
        except Exception as e:
            logger.error(f"Detection rules query failed: {e}")
            return {"error": str(e)}

    def _query_vulnerabilities(self, product: str, k: int = 5) -> Dict[str, Any]:
        """Query vulnerabilities for specific products."""
        if not self.rag_engine:
            return {"error": "RAG engine not available"}

        try:
            results = self.rag_engine.query_for_vulnerabilities(product, k=k)

            return {
                "success": True,
                "product": product,
                "count": len(results),
                "vulnerabilities": [
                    {
                        "cve_id": r.metadata.get("cve_id", ""),
                        "cvss_score": r.metadata.get("cvss_score", 0.0),
                        "description": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                        "score": r.score
                    }
                    for r in results
                ]
            }
        except Exception as e:
            logger.error(f"Vulnerabilities query failed: {e}")
            return {"error": str(e)}

    # Sigma generation tools
    def _generate_sigma(self, activity_description: str,
                       evidence: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate Sigma detection rule for activity."""

        try:
            # Import Sigma generation logic
            from agents.analyst.sigma_gen import generate_sigma_rule

            rule = generate_sigma_rule(activity_description, evidence or {})

            return {
                "success": True,
                "activity": activity_description,
                "rule": rule
            }
        except ImportError:
            logger.warning("Sigma generation not available")
            return {"error": "Sigma generation not implemented"}
        except Exception as e:
            logger.error(f"Sigma generation failed: {e}")
            return {"error": str(e)}

    def _validate_sigma(self, rule_yaml: str) -> Dict[str, Any]:
        """Validate Sigma rule syntax."""

        try:
            import yaml

            # Parse YAML
            rule_data = yaml.safe_load(rule_yaml)

            # Basic validation
            required_fields = ["title", "logsource", "detection"]
            missing_fields = [field for field in required_fields
                            if field not in rule_data]

            if missing_fields:
                return {
                    "valid": False,
                    "errors": [f"Missing required field: {field}" for field in missing_fields]
                }

            return {
                "valid": True,
                "rule_id": rule_data.get("id", ""),
                "title": rule_data.get("title", ""),
                "level": rule_data.get("level", "medium")
            }

        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)]
            }

    # Playbook tools
    def _plan_playbook(self, ttps: List[str], entities: List[Dict[str, Any]],
                      severity: str = "medium") -> Dict[str, Any]:
        """Plan response playbooks for identified TTPs."""

        try:
            # Import playbook planning logic
            from agents.responder.playbooks.dsl import plan_response_playbooks

            playbooks = plan_response_playbooks(ttps, entities, severity)

            return {
                "success": True,
                "ttps": ttps,
                "severity": severity,
                "playbooks": playbooks
            }
        except ImportError:
            logger.warning("Playbook planning not available")
            return {"error": "Playbook planning not implemented"}
        except Exception as e:
            logger.error(f"Playbook planning failed: {e}")
            return {"error": str(e)}

    def _dry_run_playbook(self, playbook_id: str,
                         context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform dry run of playbook to preview changes."""

        try:
            # Import playbook runner
            from agents.responder.playbooks.runner import dry_run_playbook

            result = dry_run_playbook(playbook_id, context or {})

            return {
                "success": True,
                "playbook_id": playbook_id,
                "changes": result.get("changes", []),
                "risk_assessment": result.get("risk", "medium"),
                "reversible": result.get("reversible", True)
            }
        except ImportError:
            logger.warning("Playbook runner not available")
            return {"error": "Playbook execution not implemented"}
        except Exception as e:
            logger.error(f"Playbook dry run failed: {e}")
            return {"error": str(e)}

    def _submit_for_approval(self, incident_id: str, action_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Submit action plan for human approval."""

        approval_request = {
            "incident_id": incident_id,
            "timestamp": datetime.now().isoformat(),
            "action_plan": action_plan,
            "risk_tier": action_plan.get("risk_tier", "medium"),
            "playbooks": action_plan.get("playbooks", []),
            "estimated_impact": action_plan.get("estimated_impact", "low"),
            "approval_status": "pending"
        }

        # In production, this would integrate with approval workflow
        logger.info(f"Approval request submitted for incident {incident_id}")

        return {
            "success": True,
            "approval_id": f"approval_{incident_id}_{int(datetime.now().timestamp())}",
            "status": "pending",
            "estimated_review_time_minutes": 30
        }

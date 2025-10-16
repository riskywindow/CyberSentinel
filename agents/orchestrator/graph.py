"""LangGraph orchestrator for CyberSentinel multi-agent workflow."""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Annotated, TypedDict
from datetime import datetime
from dataclasses import dataclass, asdict

try:
    from langgraph import StateGraph, END
    from langgraph.graph import Graph
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    # Mock LangGraph for demo if not available
    class StateGraph:
        def __init__(self, schema): pass
        def add_node(self, name, func): pass
        def add_edge(self, from_node, to_node): pass
        def add_conditional_edges(self, from_node, condition, edges): pass
        def set_entry_point(self, node): pass
        def compile(self, **kwargs): return MockGraph()
    
    class MockGraph:
        def invoke(self, state): return state
        async def ainvoke(self, state): return state
    
    END = "END"
    MemorySaver = None
    SqliteSaver = None

from bus.proto import cybersentinel_pb2 as pb

logger = logging.getLogger(__name__)

class IncidentState(TypedDict):
    """State object for incident processing workflow."""
    incident_id: str
    frames: List[Dict[str, Any]]  # Bus payloads
    graph_focus: Dict[str, Any]   # Subgraph nodes/edges
    budget_tokens: int
    budget_time_seconds: int
    severity: str
    decisions: List[Dict[str, Any]]  # Structured rationales
    
    # Agent outputs
    scout_findings: Optional[Dict[str, Any]]
    analyst_findings: Optional[Dict[str, Any]]
    responder_plan: Optional[Dict[str, Any]]
    
    # Workflow control
    current_step: str
    should_escalate: bool
    approval_required: bool
    
    # Context and evidence
    entities: List[Dict[str, Any]]
    candidate_ttps: List[str]
    evidence_refs: List[str]
    confidence_score: float

@dataclass
class WorkflowConfig:
    """Configuration for orchestrator workflow."""
    max_tokens: int = 10000
    max_time_seconds: int = 300
    scout_enabled: bool = True
    analyst_enabled: bool = True
    responder_enabled: bool = True
    require_approval_for_high_risk: bool = True
    enable_opa_gates: bool = True
    checkpoint_path: str = "data/workflow_checkpoints"

class CyberSentinelOrchestrator:
    """Main orchestrator for CyberSentinel multi-agent workflow."""
    
    def __init__(self, config: WorkflowConfig = None):
        self.config = config or WorkflowConfig()
        self.graph = None
        self._tools_registry = {}
        self._build_graph()
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow graph."""
        
        # Create state graph
        graph_builder = StateGraph(IncidentState)
        
        # Add nodes
        graph_builder.add_node("ingest_node", self._ingest_node)
        
        if self.config.scout_enabled:
            graph_builder.add_node("scout_node", self._scout_node)
        
        if self.config.analyst_enabled:
            graph_builder.add_node("analyst_node", self._analyst_node)
        
        if self.config.responder_enabled:
            graph_builder.add_node("responder_node", self._responder_node)
        
        graph_builder.add_node("escalation_node", self._escalation_node)
        graph_builder.add_node("completion_node", self._completion_node)
        
        # Set entry point
        graph_builder.set_entry_point("ingest_node")
        
        # Add edges
        if self.config.scout_enabled:
            graph_builder.add_edge("ingest_node", "scout_node")
            
            if self.config.analyst_enabled:
                graph_builder.add_conditional_edges(
                    "scout_node",
                    self._should_analyze,
                    {
                        "analyze": "analyst_node",
                        "escalate": "escalation_node",
                        "complete": "completion_node"
                    }
                )
            else:
                graph_builder.add_edge("scout_node", "completion_node")
        else:
            graph_builder.add_edge("ingest_node", "completion_node")
        
        if self.config.analyst_enabled and self.config.responder_enabled:
            graph_builder.add_conditional_edges(
                "analyst_node", 
                self._should_respond,
                {
                    "respond": "responder_node",
                    "escalate": "escalation_node", 
                    "complete": "completion_node"
                }
            )
            
            graph_builder.add_conditional_edges(
                "responder_node",
                self._should_escalate,
                {
                    "escalate": "escalation_node",
                    "complete": "completion_node"
                }
            )
        elif self.config.analyst_enabled:
            graph_builder.add_edge("analyst_node", "completion_node")
        
        graph_builder.add_edge("escalation_node", END)
        graph_builder.add_edge("completion_node", END)
        
        # Compile graph with checkpointing
        try:
            if SqliteSaver:
                checkpointer = SqliteSaver.from_conn_string(f"sqlite:///{self.config.checkpoint_path}/checkpoints.db")
            else:
                checkpointer = MemorySaver() if MemorySaver else None
            
            self.graph = graph_builder.compile(checkpointer=checkpointer)
        except Exception as e:
            logger.warning(f"Could not compile graph with checkpointing: {e}")
            self.graph = graph_builder.compile()
        
        logger.info("Multi-agent workflow graph compiled successfully")
    
    def _ingest_node(self, state: IncidentState) -> IncidentState:
        """Process incoming frames and prepare for analysis."""
        
        logger.info(f"Processing incident {state['incident_id']} - ingest phase")
        
        # Initialize state if needed
        if not state.get("current_step"):
            state["current_step"] = "ingest"
            state["should_escalate"] = False
            state["approval_required"] = False
            state["entities"] = []
            state["candidate_ttps"] = []
            state["evidence_refs"] = []
            state["confidence_score"] = 0.0
            state["decisions"] = []
        
        # Process frames to extract basic info
        entities = []
        evidence_refs = []
        
        for frame in state.get("frames", []):
            # Extract entities from alerts
            if "alert" in frame:
                alert = frame["alert"]
                for entity in alert.get("entities", []):
                    if isinstance(entity, dict):
                        entities.append(entity)
                    else:
                        # Handle string format "type:id"
                        if ":" in str(entity):
                            entity_type, entity_id = str(entity).split(":", 1)
                            entities.append({"type": entity_type, "id": entity_id})
                
                evidence_refs.append(alert.get("evidence_ref", ""))
            
            # Extract from findings
            if "finding" in frame:
                finding = frame["finding"]
                for node in finding.get("graph_nodes", []):
                    if isinstance(node, dict):
                        entities.append(node)
                
                ttps = finding.get("candidate_ttps", [])
                state["candidate_ttps"].extend(ttps)
        
        state["entities"] = entities
        state["evidence_refs"] = [ref for ref in evidence_refs if ref]
        
        # Check budget constraints
        if state["budget_tokens"] <= 0:
            logger.warning("Token budget exhausted, escalating")
            state["should_escalate"] = True
        
        if state["budget_time_seconds"] <= 0:
            logger.warning("Time budget exhausted, escalating")
            state["should_escalate"] = True
        
        # Record decision
        state["decisions"].append({
            "step": "ingest",
            "timestamp": datetime.now().isoformat(),
            "decision": "Processed frames and extracted entities",
            "entities_found": len(entities),
            "ttps_found": len(state["candidate_ttps"]),
            "budget_remaining": state["budget_tokens"]
        })
        
        logger.info(f"Ingest completed: {len(entities)} entities, {len(state['candidate_ttps'])} TTPs")
        return state
    
    def _scout_node(self, state: IncidentState) -> IncidentState:
        """Scout agent processing - deduplication and initial tagging."""
        
        logger.info(f"Scout processing incident {state['incident_id']}")
        state["current_step"] = "scout"
        
        # Import scout agent
        from agents.scout.agent import ScoutAgent
        
        scout = ScoutAgent()
        
        # Process alerts for deduplication and tagging
        scout_input = {
            "frames": state["frames"],
            "entities": state["entities"],
            "existing_ttps": state["candidate_ttps"]
        }
        
        scout_result = scout.process_alerts(scout_input)
        
        state["scout_findings"] = scout_result
        
        # Update state with scout findings
        if scout_result:
            state["candidate_ttps"].extend(scout_result.get("new_ttps", []))
            state["confidence_score"] = scout_result.get("confidence", 0.0)
            state["severity"] = scout_result.get("severity", "medium")
        
        # Update budget
        tokens_used = scout_result.get("tokens_used", 100)
        state["budget_tokens"] -= tokens_used
        
        # Record decision
        state["decisions"].append({
            "step": "scout", 
            "timestamp": datetime.now().isoformat(),
            "decision": "Completed alert analysis and TTP tagging",
            "confidence": state["confidence_score"],
            "severity": state["severity"],
            "new_ttps": scout_result.get("new_ttps", []) if scout_result else [],
            "tokens_used": tokens_used
        })
        
        logger.info(f"Scout completed: confidence={state['confidence_score']}, severity={state['severity']}")
        return state
    
    def _analyst_node(self, state: IncidentState) -> IncidentState:
        """Analyst agent processing - hypothesis building and Sigma generation."""
        
        logger.info(f"Analyst processing incident {state['incident_id']}")
        state["current_step"] = "analyst"
        
        # Import analyst agent
        from agents.analyst.agent import AnalystAgent
        
        analyst = AnalystAgent()
        
        # Build hypothesis and generate detection rules
        analyst_input = {
            "scout_findings": state.get("scout_findings", {}),
            "entities": state["entities"],
            "candidate_ttps": state["candidate_ttps"],
            "evidence_refs": state["evidence_refs"],
            "severity": state["severity"]
        }
        
        analyst_result = analyst.analyze_incident(analyst_input)
        
        state["analyst_findings"] = analyst_result
        
        # Update state with analyst findings
        if analyst_result:
            state["confidence_score"] = max(state["confidence_score"], 
                                          analyst_result.get("confidence", 0.0))
            
            # Check if high confidence warrants response
            if analyst_result.get("confidence", 0.0) > 0.8:
                state["should_escalate"] = analyst_result.get("requires_response", False)
        
        # Update budget
        tokens_used = analyst_result.get("tokens_used", 200) if analyst_result else 200
        state["budget_tokens"] -= tokens_used
        
        # Record decision with rationale
        rationale = analyst_result.get("rationale", {}) if analyst_result else {}
        state["decisions"].append({
            "step": "analyst",
            "timestamp": datetime.now().isoformat(), 
            "decision": "Completed hypothesis building and detection rule generation",
            "hypothesis": analyst_result.get("hypothesis", "") if analyst_result else "",
            "confidence": state["confidence_score"],
            "rationale": rationale,
            "sigma_rules_generated": len(analyst_result.get("sigma_rules", [])) if analyst_result else 0,
            "tokens_used": tokens_used
        })
        
        logger.info(f"Analyst completed: hypothesis generated, confidence={state['confidence_score']}")
        return state
    
    def _responder_node(self, state: IncidentState) -> IncidentState:
        """Responder agent processing - playbook selection and execution planning."""
        
        logger.info(f"Responder processing incident {state['incident_id']}")
        state["current_step"] = "responder"
        
        # Import responder agent
        from agents.responder.agent import ResponderAgent
        
        responder = ResponderAgent()
        
        # Plan response based on analyst findings
        responder_input = {
            "analyst_findings": state.get("analyst_findings", {}),
            "entities": state["entities"],
            "candidate_ttps": state["candidate_ttps"],
            "severity": state["severity"]
        }
        
        responder_result = responder.plan_response(responder_input)
        
        state["responder_plan"] = responder_result
        
        # Check if approval required for high-risk actions
        if responder_result:
            risk_tier = responder_result.get("risk_tier", "medium")
            
            if risk_tier == "high" and self.config.require_approval_for_high_risk:
                state["approval_required"] = True
                state["should_escalate"] = True
        
        # Update budget
        tokens_used = responder_result.get("tokens_used", 150) if responder_result else 150
        state["budget_tokens"] -= tokens_used
        
        # Record decision
        state["decisions"].append({
            "step": "responder",
            "timestamp": datetime.now().isoformat(),
            "decision": "Completed response planning",
            "playbooks_selected": responder_result.get("playbooks", []) if responder_result else [],
            "risk_tier": responder_result.get("risk_tier", "medium") if responder_result else "medium",
            "approval_required": state["approval_required"],
            "tokens_used": tokens_used
        })
        
        logger.info(f"Responder completed: risk_tier={responder_result.get('risk_tier') if responder_result else 'unknown'}")
        return state
    
    def _escalation_node(self, state: IncidentState) -> IncidentState:
        """Handle escalation for human review."""
        
        logger.info(f"Escalating incident {state['incident_id']} for human review")
        state["current_step"] = "escalated"
        
        # Create escalation summary
        escalation_summary = {
            "incident_id": state["incident_id"],
            "reason": "High-risk actions or budget constraints require human approval",
            "severity": state["severity"],
            "confidence": state["confidence_score"],
            "candidate_ttps": state["candidate_ttps"],
            "entities_count": len(state["entities"]),
            "approval_required": state.get("approval_required", False),
            "budget_exhausted": state["budget_tokens"] <= 0,
            "decisions_made": len(state["decisions"]),
            "escalation_time": datetime.now().isoformat()
        }
        
        # Record escalation decision
        state["decisions"].append({
            "step": "escalation",
            "timestamp": datetime.now().isoformat(),
            "decision": "Incident escalated for human review",
            "summary": escalation_summary
        })
        
        # In production, this would notify human analysts
        logger.info(f"Escalation summary: {escalation_summary}")
        
        return state
    
    def _completion_node(self, state: IncidentState) -> IncidentState:
        """Complete incident processing."""
        
        logger.info(f"Completing incident {state['incident_id']}")
        state["current_step"] = "completed"
        
        # Create completion summary
        completion_summary = {
            "incident_id": state["incident_id"],
            "total_steps": len(state["decisions"]),
            "final_confidence": state["confidence_score"],
            "final_severity": state["severity"],
            "ttps_identified": len(set(state["candidate_ttps"])),
            "entities_processed": len(state["entities"]),
            "tokens_used": self.config.max_tokens - state["budget_tokens"],
            "completion_time": datetime.now().isoformat()
        }
        
        # Record completion decision
        state["decisions"].append({
            "step": "completion",
            "timestamp": datetime.now().isoformat(),
            "decision": "Incident processing completed",
            "summary": completion_summary
        })
        
        logger.info(f"Incident {state['incident_id']} completed: {completion_summary}")
        return state
    
    # Conditional routing functions
    def _should_analyze(self, state: IncidentState) -> str:
        """Determine if scout findings warrant analyst review."""
        
        if state.get("should_escalate", False):
            return "escalate"
        
        scout_findings = state.get("scout_findings", {})
        confidence = scout_findings.get("confidence", 0.0)
        
        # Analyze if confidence is above threshold
        if confidence > 0.3:
            return "analyze"
        else:
            return "complete"
    
    def _should_respond(self, state: IncidentState) -> str:
        """Determine if analyst findings warrant response planning."""
        
        if state.get("should_escalate", False):
            return "escalate"
        
        analyst_findings = state.get("analyst_findings", {})
        confidence = analyst_findings.get("confidence", 0.0)
        
        # Respond if high confidence and response warranted
        if confidence > 0.7 and analyst_findings.get("requires_response", False):
            return "respond"
        else:
            return "complete"
    
    def _should_escalate(self, state: IncidentState) -> str:
        """Determine if responder plan requires escalation."""
        
        if state.get("should_escalate", False) or state.get("approval_required", False):
            return "escalate"
        else:
            return "complete"
    
    async def process_incident(self, incident_id: str, 
                             frames: List[Dict[str, Any]],
                             budget_tokens: int = None,
                             budget_time: int = None) -> Dict[str, Any]:
        """Process an incident through the multi-agent workflow."""
        
        initial_state = IncidentState(
            incident_id=incident_id,
            frames=frames,
            graph_focus={},
            budget_tokens=budget_tokens or self.config.max_tokens,
            budget_time_seconds=budget_time or self.config.max_time_seconds,
            severity="medium",
            decisions=[],
            scout_findings=None,
            analyst_findings=None, 
            responder_plan=None,
            current_step="",
            should_escalate=False,
            approval_required=False,
            entities=[],
            candidate_ttps=[],
            evidence_refs=[],
            confidence_score=0.0
        )
        
        logger.info(f"Starting incident processing: {incident_id}")
        start_time = time.time()
        
        try:
            # Execute workflow
            if hasattr(self.graph, 'ainvoke'):
                final_state = await self.graph.ainvoke(initial_state)
            else:
                final_state = self.graph.invoke(initial_state)
            
            end_time = time.time()
            
            # Prepare result summary
            result = {
                "incident_id": incident_id,
                "status": "completed",
                "processing_time_seconds": end_time - start_time,
                "final_state": final_state,
                "decisions": final_state.get("decisions", []),
                "summary": {
                    "confidence": final_state.get("confidence_score", 0.0),
                    "severity": final_state.get("severity", "medium"),
                    "ttps_identified": len(set(final_state.get("candidate_ttps", []))),
                    "entities_processed": len(final_state.get("entities", [])),
                    "tokens_used": self.config.max_tokens - final_state.get("budget_tokens", 0),
                    "escalated": final_state.get("current_step") == "escalated"
                }
            }
            
            logger.info(f"Incident {incident_id} processing completed in {result['processing_time_seconds']:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error processing incident {incident_id}: {e}")
            return {
                "incident_id": incident_id,
                "status": "error",
                "error": str(e),
                "processing_time_seconds": time.time() - start_time
            }
    
    def get_workflow_stats(self) -> Dict[str, Any]:
        """Get statistics about the orchestrator workflow."""
        
        return {
            "config": asdict(self.config),
            "graph_nodes": len(self.graph._nodes) if hasattr(self.graph, '_nodes') else 0,
            "tools_registered": len(self._tools_registry)
        }
#!/usr/bin/env python3
"""Test script for multi-agent orchestration flow (Milestones 4-5)."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.orchestrator.graph import CyberSentinelOrchestrator
from agents.scout.agent import ScoutAgent
from agents.analyst.agent import AnalystAgent  
from agents.responder.agent import ResponderAgent
from knowledge.rag_index import RAGIndexBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_sample_incident_frames():
    """Create sample incident frames for testing."""
    
    frames = [
        {
            "frame_id": "frame_001",
            "timestamp": "2023-10-01T14:30:00Z",
            "alert": {
                "id": "alert_ssh_brute_001",
                "ts": "2023-10-01T14:30:00Z",
                "severity": "high", 
                "summary": "SSH brute force attack detected from 192.168.1.100",
                "entities": ["ip:192.168.1.100", "host:web-server-01", "user:admin"],
                "tags": ["ssh", "brute_force", "T1110"],
                "source_ip": "192.168.1.100",
                "dest_ip": "10.0.0.15"
            }
        },
        {
            "frame_id": "frame_002", 
            "timestamp": "2023-10-01T14:31:30Z",
            "alert": {
                "id": "alert_ssh_brute_002",
                "ts": "2023-10-01T14:31:30Z",
                "severity": "high",
                "summary": "SSH brute force attack detected from 192.168.1.100", 
                "entities": ["ip:192.168.1.100", "host:web-server-01", "user:admin"],
                "tags": ["ssh", "brute_force", "T1110"],
                "source_ip": "192.168.1.100",
                "dest_ip": "10.0.0.15"
            }
        },
        {
            "frame_id": "frame_003",
            "timestamp": "2023-10-01T14:35:00Z", 
            "alert": {
                "id": "alert_lateral_movement_001",
                "ts": "2023-10-01T14:35:00Z",
                "severity": "critical",
                "summary": "Suspicious SSH connection to database server",
                "entities": ["ip:10.0.0.15", "host:db-server-01", "user:admin"],
                "tags": ["ssh", "lateral_movement", "T1021.004"],
                "source_ip": "10.0.0.15",
                "dest_ip": "10.0.0.50"
            }
        }
    ]
    
    return frames

async def test_individual_agents():
    """Test individual agents separately."""
    
    logger.info("=== Testing Individual Agents ===")
    
    # Create sample data
    frames = create_sample_incident_frames()
    
    # Initialize RAG engine (if available)
    try:
        rag_builder = RAGIndexBuilder()
        rag_engine = rag_builder.get_query_engine()
        logger.info("RAG engine initialized successfully")
    except Exception as e:
        logger.warning(f"RAG engine not available: {e}")
        rag_engine = None
    
    # Test Scout Agent
    logger.info("Testing Scout Agent...")
    scout_agent = ScoutAgent(rag_engine)
    
    scout_input = {
        "frames": frames,
        "existing_ttps": []
    }
    
    scout_result = scout_agent.process_alerts(scout_input)
    logger.info(f"Scout processed {scout_result['alerts_processed']} alerts")
    logger.info(f"Scout found {len(scout_result['new_ttps'])} new TTPs: {scout_result['new_ttps']}")
    logger.info(f"Scout confidence: {scout_result['confidence']}")
    
    # Test Analyst Agent
    logger.info("Testing Analyst Agent...")
    analyst_agent = AnalystAgent(rag_engine)
    
    # Extract entities from frames
    entities = []
    for frame in frames:
        alert = frame.get("alert", {})
        for entity_str in alert.get("entities", []):
            if ":" in entity_str:
                entity_type, entity_id = entity_str.split(":", 1)
                entities.append({"type": entity_type, "id": entity_id})
    
    analyst_input = {
        "scout_findings": scout_result,
        "entities": entities,
        "candidate_ttps": scout_result["new_ttps"],
        "evidence_refs": [frame["frame_id"] for frame in frames],
        "severity": scout_result["severity"]
    }
    
    analyst_result = analyst_agent.analyze_incident(analyst_input)
    logger.info(f"Analyst hypothesis: {analyst_result['hypothesis'][:100]}...")
    logger.info(f"Analyst confidence: {analyst_result['confidence']}")
    logger.info(f"Requires response: {analyst_result['requires_response']}")
    logger.info(f"Sigma rules generated: {len(analyst_result['sigma_rules'])}")
    
    # Test Responder Agent
    logger.info("Testing Responder Agent...")
    responder_agent = ResponderAgent()
    
    responder_input = {
        **analyst_result,
        "entities": entities,
        "tagged_alerts": scout_result.get("tagged_alerts", [])
    }
    
    responder_result = responder_agent.plan_response(responder_input)
    logger.info(f"Response required: {responder_result['response_required']}")
    
    if responder_result["response_required"]:
        playbook_plan = responder_result["playbook_plan"]
        logger.info(f"Planned {len(playbook_plan.get('playbooks', []))} playbooks")
        logger.info(f"Risk assessment: {responder_result['risk_assessment']['overall_risk']}")
        logger.info(f"Approval required: {responder_result['approval_required']}")
        
        # Test playbook execution (if low risk)
        if not responder_result["approval_required"]:
            logger.info("Testing playbook execution...")
            try:
                execution_variables = {
                    "incident": {
                        "primary_host": "web-server-01",
                        "malicious_ip": "192.168.1.100",
                        "malicious_process": "suspicious.exe"
                    }
                }
                
                execution_result = await responder_agent.execute_response(
                    playbook_plan, execution_variables
                )
                logger.info(f"Execution status: {execution_result['overall_status']}")
                logger.info(f"Successful playbooks: {execution_result['successful_playbooks']}")
            except Exception as e:
                logger.error(f"Playbook execution failed: {e}")
    
    return {
        "scout_result": scout_result,
        "analyst_result": analyst_result, 
        "responder_result": responder_result
    }

async def test_full_orchestration():
    """Test full multi-agent orchestration."""
    
    logger.info("=== Testing Full Orchestration ===")
    
    # Initialize orchestrator
    try:
        rag_builder = RAGIndexBuilder()
        rag_engine = rag_builder.get_query_engine()
    except:
        rag_engine = None
    
    orchestrator = CyberSentinelOrchestrator()
    
    # Create incident
    frames = create_sample_incident_frames()
    incident_id = "test_incident_001"
    
    # Extract entities
    entities = []
    for frame in frames:
        alert = frame.get("alert", {})
        for entity_str in alert.get("entities", []):
            if ":" in entity_str:
                entity_type, entity_id = entity_str.split(":", 1)
                entities.append({"type": entity_type, "id": entity_id})
    
    initial_state = {
        "incident_id": incident_id,
        "frames": frames,
        "entities": entities,
        "budget_tokens": 10000,
        "severity": "high",
        "decisions": []
    }
    
    logger.info(f"Starting orchestration for incident {incident_id}")
    logger.info(f"Processing {len(frames)} frames with {len(entities)} entities")
    
    try:
        # Run orchestration
        result = await orchestrator.process_incident(incident_id, frames)
        
        # Log results
        logger.info("=== Orchestration Results ===")
        logger.info(f"Incident ID: {result['incident_id']}")
        logger.info(f"Status: {result['status']}")
        logger.info(f"Processing time: {result['processing_time_seconds']:.2f}s")
        logger.info(f"Decisions made: {len(result['decisions'])}")
        
        final_state = result['final_state']
        logger.info(f"Final severity: {final_state['severity']}")
        logger.info(f"Final confidence: {final_state['confidence_score']}")
        logger.info(f"TTPs identified: {len(final_state['candidate_ttps'])}")
        
        # Scout findings
        if "scout_findings" in final_state:
            scout_findings = final_state["scout_findings"]
            logger.info(f"Scout processed {scout_findings.get('alerts_processed', 0)} alerts")
            logger.info(f"Scout identified {len(scout_findings.get('new_ttps', []))} new TTPs")
        
        # Analyst findings
        if "analyst_findings" in final_state:
            analyst_findings = final_state["analyst_findings"]
            logger.info(f"Analyst confidence: {analyst_findings.get('confidence', 0.0)}")
            logger.info(f"Sigma rules generated: {len(analyst_findings.get('sigma_rules', []))}")
        
        # Responder plan
        if "responder_plan" in final_state:
            responder_plan = final_state["responder_plan"]
            logger.info(f"Response required: {responder_plan.get('response_required', False)}")
            if responder_plan.get("response_required"):
                playbook_plan = responder_plan.get("playbook_plan", {})
                logger.info(f"Planned playbooks: {len(playbook_plan.get('playbooks', []))}")
                logger.info(f"Approval required: {responder_plan.get('approval_required', True)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        raise

def test_playbook_loading():
    """Test playbook loading and validation."""
    
    logger.info("=== Testing Playbook Loading ===")
    
    responder_agent = ResponderAgent()
    
    # Test available playbooks
    available_playbooks = responder_agent.get_available_playbooks()
    logger.info(f"Available playbooks: {available_playbooks}")
    
    # Test individual playbook info
    for playbook_id in available_playbooks:
        info = responder_agent.get_playbook_info(playbook_id)
        if info:
            logger.info(f"Playbook {playbook_id}:")
            logger.info(f"  Name: {info['name']}")
            logger.info(f"  Risk tier: {info['risk_tier']}")
            logger.info(f"  Steps: {info['step_count']}")
            logger.info(f"  Duration: {info['estimated_duration_minutes']} min")
            logger.info(f"  Reversible: {info['reversible']}")
        else:
            logger.error(f"Failed to load playbook: {playbook_id}")

def test_opa_policies():
    """Test OPA policy evaluation."""
    
    logger.info("=== Testing OPA Policies ===")
    
    from agents.responder.opa_client import OPAClient
    
    opa_client = OPAClient()
    
    # Test policy evaluation
    test_result = opa_client.test_policy_evaluation()
    logger.info(f"OPA test result: {json.dumps(test_result, indent=2)}")
    
    # Test policy loading (if OPA is available)
    if opa_client._is_opa_available():
        logger.info("OPA server is available")
        load_result = opa_client.load_policy_files()
        logger.info(f"Policy loading result: {load_result}")
    else:
        logger.info("OPA server not available, using fallback policies")

async def main():
    """Main test execution."""
    
    logger.info("Starting CyberSentinel Multi-Agent Orchestration Tests")
    logger.info("=" * 60)
    
    try:
        # Test playbook loading
        test_playbook_loading()
        print()
        
        # Test OPA policies
        test_opa_policies()
        print()
        
        # Test individual agents
        individual_results = await test_individual_agents()
        print()
        
        # Test full orchestration
        orchestration_result = await test_full_orchestration()
        print()
        
        logger.info("=== All Tests Completed Successfully ===")
        
        # Summary
        logger.info("Test Summary:")
        logger.info(f"- Scout agent: ✓")
        logger.info(f"- Analyst agent: ✓") 
        logger.info(f"- Responder agent: ✓")
        logger.info(f"- Full orchestration: ✓")
        logger.info(f"- Playbook loading: ✓")
        logger.info(f"- OPA policies: ✓")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
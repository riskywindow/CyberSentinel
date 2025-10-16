#!/usr/bin/env python3
"""Simple test script for individual agents without orchestrator dependencies."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_sample_incident_data():
    """Create sample incident data for testing."""
    
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
    
    # Extract entities
    entities = []
    for frame in frames:
        alert = frame.get("alert", {})
        for entity_str in alert.get("entities", []):
            if ":" in entity_str:
                entity_type, entity_id = entity_str.split(":", 1)
                entities.append({"type": entity_type, "id": entity_id})
    
    return frames, entities

def test_scout_agent():
    """Test Scout Agent independently."""
    
    logger.info("=== Testing Scout Agent ===")
    
    try:
        from agents.scout.agent import ScoutAgent
        
        frames, entities = create_sample_incident_data()
        
        # Initialize scout (without RAG for simplicity)
        scout_agent = ScoutAgent(rag_engine=None)
        
        scout_input = {
            "frames": frames,
            "existing_ttps": []
        }
        
        scout_result = scout_agent.process_alerts(scout_input)
        
        logger.info(f"✓ Scout processed {scout_result['alerts_processed']} alerts")
        logger.info(f"✓ Found {len(scout_result['new_ttps'])} new TTPs: {scout_result['new_ttps']}")
        logger.info(f"✓ Confidence: {scout_result['confidence']}")
        logger.info(f"✓ Severity: {scout_result['severity']}")
        
        return scout_result
        
    except Exception as e:
        logger.error(f"✗ Scout Agent test failed: {e}")
        raise

def test_analyst_agent():
    """Test Analyst Agent independently."""
    
    logger.info("=== Testing Analyst Agent ===")
    
    try:
        from agents.analyst.agent import AnalystAgent
        
        frames, entities = create_sample_incident_data()
        
        # Create mock scout findings
        scout_findings = {
            "alerts_processed": 3,
            "unique_alerts": 3,
            "new_ttps": ["T1110", "T1021.004"],
            "confidence": 0.8,
            "tagged_alerts": [
                {
                    "id": "alert_ssh_brute_001",
                    "summary": "SSH brute force attack detected",
                    "attack_techniques": [
                        {
                            "technique_id": "T1110",
                            "name": "Brute Force",
                            "tactic": "Credential Access",
                            "confidence": 0.9
                        }
                    ]
                }
            ]
        }
        
        # Initialize analyst (without RAG for simplicity)
        analyst_agent = AnalystAgent(rag_engine=None)
        
        analyst_input = {
            "scout_findings": scout_findings,
            "entities": entities,
            "candidate_ttps": ["T1110", "T1021.004"],
            "evidence_refs": ["frame_001", "frame_002", "frame_003"],
            "severity": "high"
        }
        
        analyst_result = analyst_agent.analyze_incident(analyst_input)
        
        logger.info(f"✓ Hypothesis: {analyst_result['hypothesis'][:100]}...")
        logger.info(f"✓ Confidence: {analyst_result['confidence']}")
        logger.info(f"✓ Requires response: {analyst_result['requires_response']}")
        logger.info(f"✓ Sigma rules generated: {len(analyst_result['sigma_rules'])}")
        logger.info(f"✓ Severity assessment: {analyst_result['severity_assessment']}")
        
        return analyst_result
        
    except Exception as e:
        logger.error(f"✗ Analyst Agent test failed: {e}")
        raise

async def test_responder_agent():
    """Test Responder Agent independently."""
    
    logger.info("=== Testing Responder Agent ===")
    
    try:
        from agents.responder.agent import ResponderAgent
        
        frames, entities = create_sample_incident_data()
        
        # Create mock analyst findings
        analyst_findings = {
            "hypothesis": "Multi-stage attack involving credential access and lateral movement",
            "confidence": 0.85,
            "requires_response": True,
            "severity_assessment": "high",
            "ttp_analysis": {
                "ttps": ["T1110", "T1021.004"],
                "tactics": {
                    "Credential Access": ["T1110"],
                    "Lateral Movement": ["T1021.004"]
                },
                "patterns": [
                    {"type": "credential_harvesting", "severity": "high"},
                    {"type": "lateral_movement", "severity": "medium"}
                ]
            },
            "timeline": [
                {
                    "timestamp": "2023-10-01T14:30:00Z",
                    "event": "SSH brute force attack initiated",
                    "source": "alert_analysis"
                }
            ],
            "indicators": [
                {"type": "ip_address", "value": "192.168.1.100", "confidence": 0.9}
            ]
        }
        
        # Initialize responder
        responder_agent = ResponderAgent()
        
        responder_input = {
            **analyst_findings,
            "entities": entities,
            "tagged_alerts": []
        }
        
        responder_result = responder_agent.plan_response(responder_input)
        
        logger.info(f"✓ Response required: {responder_result['response_required']}")
        
        if responder_result["response_required"]:
            playbook_plan = responder_result["playbook_plan"]
            logger.info(f"✓ Planned {len(playbook_plan.get('playbooks', []))} playbooks")
            logger.info(f"✓ Risk assessment: {responder_result['risk_assessment']['overall_risk']}")
            logger.info(f"✓ Approval required: {responder_result['approval_required']}")
            
            # List planned playbooks
            for pb in playbook_plan.get("playbooks", []):
                logger.info(f"  - {pb['name']} (risk: {pb['risk_tier']})")
            
            # Test playbook execution for low-risk scenarios
            if not responder_result["approval_required"]:
                logger.info("Testing playbook execution...")
                try:
                    execution_variables = {
                        "incident": {
                            "primary_host": "web-server-01",
                            "malicious_ip": "192.168.1.100"
                        }
                    }
                    
                    execution_result = await responder_agent.execute_response(
                        playbook_plan, execution_variables
                    )
                    logger.info(f"✓ Execution status: {execution_result['overall_status']}")
                    logger.info(f"✓ Successful playbooks: {execution_result['successful_playbooks']}")
                    
                except Exception as e:
                    logger.warning(f"Playbook execution failed (expected in test): {e}")
        
        return responder_result
        
    except Exception as e:
        logger.error(f"✗ Responder Agent test failed: {e}")
        raise

def test_playbooks():
    """Test playbook loading and validation."""
    
    logger.info("=== Testing Playbooks ===")
    
    try:
        from agents.responder.agent import ResponderAgent
        
        responder_agent = ResponderAgent()
        
        # Test available playbooks
        available_playbooks = responder_agent.get_available_playbooks()
        logger.info(f"✓ Found {len(available_playbooks)} available playbooks")
        
        # Test each playbook
        for playbook_id in available_playbooks:
            info = responder_agent.get_playbook_info(playbook_id)
            if info:
                logger.info(f"✓ {playbook_id}: {info['name']} ({info['step_count']} steps, {info['risk_tier']} risk)")
            else:
                logger.error(f"✗ Failed to load playbook: {playbook_id}")
        
        # Test playbook selection
        from agents.responder.playbooks.dsl import plan_response_playbooks
        
        ttps = ["T1110", "T1021.004"]
        entities = [{"type": "ip", "id": "192.168.1.100"}, {"type": "host", "id": "web-server-01"}]
        
        playbook_plan = plan_response_playbooks(ttps, entities, "high")
        logger.info(f"✓ Selected {len(playbook_plan.get('playbooks', []))} playbooks for TTPs {ttps}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Playbook test failed: {e}")
        raise

def test_opa_policies():
    """Test OPA policy evaluation."""
    
    logger.info("=== Testing OPA Policies ===")
    
    try:
        from agents.responder.opa_client import OPAClient
        
        opa_client = OPAClient()
        
        # Test with sample data
        sample_data = {
            "risk_assessment": {
                "overall_risk": "medium",
                "risk_score": 0.6
            },
            "incident": {
                "confidence": 0.8,
                "severity": "high",
                "entities": [{"type": "host", "id": "web-server-01"}]
            },
            "playbook_plan": {
                "playbooks": [
                    {
                        "id": "isolate_host",
                        "risk_tier": "high",
                        "reversible": True
                    }
                ],
                "estimated_duration_minutes": 15
            }
        }
        
        policy_result = opa_client.evaluate_response_authorization(sample_data)
        
        logger.info(f"✓ Policy evaluation completed")
        logger.info(f"✓ Allow: {policy_result.get('allow', False)}")
        logger.info(f"✓ Approval required: {policy_result.get('approval_required', True)}")
        logger.info(f"✓ Policy source: {policy_result.get('policy_source', 'unknown')}")
        
        if policy_result.get("recommendations"):
            logger.info(f"✓ Recommendations: {len(policy_result['recommendations'])}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ OPA policy test failed: {e}")
        raise

async def main():
    """Main test execution."""
    
    logger.info("Starting CyberSentinel Individual Agent Tests")
    logger.info("=" * 50)
    
    test_results = {}
    
    try:
        # Test individual components
        logger.info("1. Testing Scout Agent...")
        scout_result = test_scout_agent()
        test_results["scout"] = True
        print()
        
        logger.info("2. Testing Analyst Agent...")
        analyst_result = test_analyst_agent()
        test_results["analyst"] = True
        print()
        
        logger.info("3. Testing Responder Agent...")
        responder_result = await test_responder_agent()
        test_results["responder"] = True
        print()
        
        logger.info("4. Testing Playbook System...")
        test_playbooks()
        test_results["playbooks"] = True
        print()
        
        logger.info("5. Testing OPA Policies...")
        test_opa_policies()
        test_results["opa"] = True
        print()
        
        # Summary
        logger.info("=" * 50)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 50)
        
        passed = sum(test_results.values())
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✓ PASSED" if result else "✗ FAILED"
            logger.info(f"{test_name.capitalize()}: {status}")
        
        logger.info("=" * 50)
        logger.info(f"OVERALL: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 All agent tests completed successfully!")
            logger.info("Multi-agent orchestration system is ready for Milestones 4-5")
        else:
            logger.error("❌ Some tests failed")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
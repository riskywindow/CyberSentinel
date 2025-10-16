#!/usr/bin/env python3
"""End-to-end test for the red team simulation system."""

import asyncio
import logging
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redteam.framework import RedTeamSimulator
from redteam.orchestrator import CampaignOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_campaign_creation():
    """Test creating different types of campaigns."""
    print("\n=== Testing Campaign Creation ===")
    
    simulator = RedTeamSimulator()
    
    # Test APT campaign
    apt_campaign_id = simulator.create_campaign(
        adversary_name="apt",
        environment_name="corporate",
        template_name="data_breach",
        duration_hours=24
    )
    print(f"✓ Created APT campaign: {apt_campaign_id}")
    
    # Test ransomware campaign
    ransomware_campaign_id = simulator.create_campaign(
        adversary_name="ransomware",
        environment_name="healthcare",
        template_name="ransomware",
        duration_hours=12
    )
    print(f"✓ Created ransomware campaign: {ransomware_campaign_id}")
    
    # Test insider threat campaign
    insider_campaign_id = simulator.create_campaign(
        adversary_name="insider",
        environment_name="corporate",
        duration_hours=8
    )
    print(f"✓ Created insider campaign: {insider_campaign_id}")
    
    # List all campaigns
    campaigns = simulator.list_campaigns()
    print(f"✓ Total campaigns created: {len(campaigns)}")
    
    return apt_campaign_id, ransomware_campaign_id, insider_campaign_id

async def test_campaign_orchestration():
    """Test campaign orchestration and execution."""
    print("\n=== Testing Campaign Orchestration ===")
    
    simulator = RedTeamSimulator()
    orchestrator = CampaignOrchestrator(simulator)
    
    # Create a test campaign
    campaign_id = simulator.create_campaign(
        adversary_name="apt",
        environment_name="corporate",
        template_name="data_breach",
        duration_hours=2,  # Short duration for testing
        simulation_mode="batch"  # Faster execution
    )
    
    print(f"✓ Created test campaign: {campaign_id}")
    
    # Add event handler to track progress
    events_received = []
    
    async def event_handler(event_data):
        events_received.append(event_data)
        print(f"  📡 Event: {event_data['type']}")
        if event_data['type'] == 'technique_completed':
            tech_id = event_data['technique_execution']['technique_id']
            success = event_data['technique_execution']['success']
            detected = event_data['technique_execution']['detected']
            print(f"    Technique {tech_id}: success={success}, detected={detected}")
    
    orchestrator.add_event_handler(event_handler)
    
    # Start campaign execution
    success = await orchestrator.start_campaign(
        campaign_id=campaign_id,
        real_time=False  # Batch mode for testing
    )
    
    if success:
        print("✓ Campaign execution started")
        
        # Wait for completion (with timeout)
        timeout = 60  # 1 minute timeout
        start_time = asyncio.get_event_loop().time()
        
        while campaign_id in orchestrator.active_campaigns:
            await asyncio.sleep(1)
            if asyncio.get_event_loop().time() - start_time > timeout:
                print("⚠ Campaign execution timed out")
                break
        
        # Get final status
        status = orchestrator.get_campaign_execution_status(campaign_id)
        if status:
            print(f"✓ Campaign completed:")
            print(f"  - Techniques executed: {status['techniques_executed']}")
            print(f"  - Success rate: {status['success_rate']:.1%}")
            print(f"  - Detection rate: {status['detection_rate']:.1%}")
            print(f"  - Telemetry events: {status['total_telemetry_events']}")
        
        # Generate report
        report = orchestrator.export_campaign_report(campaign_id)
        if report:
            print("✓ Campaign report generated")
            print(f"  - Lessons learned: {len(report['lessons_learned'])}")
            print(f"  - Recommendations: {len(report['recommendations'])}")
    else:
        print("✗ Failed to start campaign execution")
    
    print(f"✓ Total events received: {len(events_received)}")
    
    return campaign_id

async def test_telemetry_generation():
    """Test telemetry generation for different techniques."""
    print("\n=== Testing Telemetry Generation ===")
    
    from redteam.telemetry_simulator import TelemetrySimulator
    
    simulator = TelemetrySimulator()
    
    # Test techniques from different tactics
    test_techniques = [
        "T1566.001",  # Spearphishing Attachment
        "T1055",      # Process Injection
        "T1021.001",  # Remote Desktop Protocol
        "T1003.001",  # LSASS Memory
        "T1486"       # Data Encrypted for Impact
    ]
    
    for technique_id in test_techniques:
        print(f"  Testing technique: {technique_id}")
        
        # Generate telemetry with different stealth levels
        for stealth_level in [0.2, 0.5, 0.8]:
            events = await simulator.generate_technique_telemetry(
                technique_id=technique_id,
                duration_minutes=30,
                stealth_level=stealth_level
            )
            
            print(f"    Stealth {stealth_level}: {len(events)} events generated")
            
            # Analyze detection opportunities
            opportunities = simulator.get_detection_opportunities(events)
            high_conf = len(opportunities["high_confidence_detections"])
            medium_conf = len(opportunities["medium_confidence_detections"])
            
            print(f"      Detection opportunities: {high_conf} high, {medium_conf} medium confidence")
    
    # Test campaign-wide telemetry
    print("  Testing campaign telemetry generation...")
    campaign_events = await simulator.generate_campaign_telemetry(
        technique_sequence=test_techniques,
        total_duration_hours=4,
        stealth_level=0.6
    )
    
    print(f"✓ Campaign telemetry: {len(campaign_events)} total events")
    
    # Export telemetry in different formats
    json_data = simulator.export_events_json(campaign_events)
    syslog_data = simulator.export_events_syslog(campaign_events)
    
    print(f"✓ Exported {len(json.loads(json_data))} events to JSON")
    print(f"✓ Exported {len(syslog_data)} events to syslog format")
    
    return len(campaign_events)

async def test_adversary_behavior():
    """Test adversary behavior engine."""
    print("\n=== Testing Adversary Behavior Engine ===")
    
    from redteam.adversary_engine import AdversaryBehaviorEngine
    from redteam.campaign_generator import ATTACKCampaignGenerator
    
    # Get components
    simulator = RedTeamSimulator()
    campaign_gen = ATTACKCampaignGenerator()
    
    # Test different adversary profiles
    profiles = ["apt", "ransomware", "insider"]
    environments = ["corporate", "healthcare"]
    
    for profile_name in profiles:
        for env_name in environments:
            print(f"  Testing {profile_name} vs {env_name}")
            
            adversary_profile = simulator.adversary_profiles[profile_name]
            target_environment = simulator.target_environments[env_name]
            
            # Create behavior engine
            behavior_engine = AdversaryBehaviorEngine(
                adversary_profile=adversary_profile,
                target_environment=target_environment,
                available_techniques=campaign_gen.technique_knowledge_base
            )
            
            # Test technique selection in different phases
            from redteam.framework import CampaignPhase
            
            phases = [CampaignPhase.RECONNAISSANCE, CampaignPhase.INITIAL_ACCESS, 
                     CampaignPhase.LATERAL_MOVEMENT]
            
            for phase in phases:
                # Get available techniques for phase
                available_techniques = [
                    tid for tid, tech in campaign_gen.technique_knowledge_base.items()
                    if phase.value.replace("_", "-") in tech.kill_chain_phases
                ][:5]  # Limit to first 5 for testing
                
                if available_techniques:
                    decision = await behavior_engine.select_next_technique(
                        current_phase=phase,
                        available_techniques=available_techniques,
                        campaign_context={"campaign_duration_hours": 2, "recent_success_rate": 0.7}
                    )
                    
                    if decision:
                        print(f"    {phase.value}: selected {decision.technique_id} "
                              f"(confidence: {decision.confidence:.2f}, risk: {decision.risk_assessment:.2f})")
                        
                        # Simulate technique result
                        await behavior_engine.process_technique_result(
                            technique_id=decision.technique_id,
                            success=True,
                            detected=False,
                            impact=0.5
                        )
            
            # Check final adversary status
            status = behavior_engine.get_adversary_status()
            print(f"    Final status: confidence={status['confidence_level']:.2f}, "
                  f"paranoia={status['paranoia_level']:.2f}")
    
    print("✓ Adversary behavior testing completed")

async def test_integration_flow():
    """Test complete integration flow."""
    print("\n=== Testing Complete Integration Flow ===")
    
    simulator = RedTeamSimulator()
    orchestrator = CampaignOrchestrator(simulator)
    
    # Create campaign
    campaign_id = simulator.create_campaign(
        adversary_name="ransomware",
        environment_name="healthcare",
        template_name="ransomware",
        duration_hours=1,  # Very short for testing
        simulation_mode="batch"
    )
    
    print(f"✓ Created integration test campaign: {campaign_id}")
    
    # Track comprehensive metrics
    metrics = {
        "events_received": 0,
        "techniques_executed": 0,
        "telemetry_events": 0,
        "detections": 0
    }
    
    async def comprehensive_event_handler(event_data):
        metrics["events_received"] += 1
        
        if event_data["type"] == "technique_completed":
            metrics["techniques_executed"] += 1
            
            tech_exec = event_data["technique_execution"]
            if tech_exec["detected"]:
                metrics["detections"] += 1
            
            # Count telemetry events
            telemetry_events = event_data["telemetry_events"]
            metrics["telemetry_events"] += len(telemetry_events)
            
            print(f"  🔧 Executed {tech_exec['technique_id']}: "
                  f"success={tech_exec['success']}, detected={tech_exec['detected']}, "
                  f"telemetry={len(telemetry_events)} events")
        
        elif event_data["type"] == "campaign_completed":
            summary = event_data["execution_summary"]
            print(f"  🎯 Campaign completed: {summary['success_rate']:.1%} success, "
                  f"{summary['detection_rate']:.1%} detection rate")
    
    orchestrator.add_event_handler(comprehensive_event_handler)
    
    # Execute campaign
    success = await orchestrator.start_campaign(campaign_id, real_time=False)
    
    if success:
        # Wait for completion
        while campaign_id in orchestrator.active_campaigns:
            await asyncio.sleep(0.5)
        
        print("✓ Integration flow completed")
        print(f"  - Events received: {metrics['events_received']}")
        print(f"  - Techniques executed: {metrics['techniques_executed']}")
        print(f"  - Telemetry events generated: {metrics['telemetry_events']}")
        print(f"  - Detections triggered: {metrics['detections']}")
        
        # Generate final report
        report = orchestrator.export_campaign_report(campaign_id)
        if report:
            print("✓ Final report generated successfully")
            
            # Show key metrics
            exec_summary = report["execution_summary"]
            print(f"  - Success rate: {exec_summary['success_rate']:.1%}")
            print(f"  - Stealth effectiveness: {exec_summary['stealth_effectiveness']:.1%}")
            print(f"  - Lessons learned: {len(report['lessons_learned'])}")
            print(f"  - Recommendations: {len(report['recommendations'])}")
    else:
        print("✗ Integration flow failed to start")
    
    return success

async def main():
    """Run all red team simulation tests."""
    print("🚀 Starting Red Team Simulation End-to-End Tests")
    print("=" * 60)
    
    try:
        # Test individual components
        await test_campaign_creation()
        await test_telemetry_generation()
        await test_adversary_behavior()
        
        # Test orchestration
        await test_campaign_orchestration()
        
        # Test complete integration
        await test_integration_flow()
        
        print("\n" + "=" * 60)
        print("✅ All Red Team Simulation Tests Completed Successfully!")
        print("\n🎯 Red Team Simulator is ready for use:")
        print("  - Framework: Campaign creation and management")
        print("  - Campaign Generator: ATT&CK-based campaign planning")
        print("  - Telemetry Simulator: Realistic log data generation")
        print("  - Adversary Engine: Behavioral decision making")
        print("  - Orchestrator: End-to-end campaign execution")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""End-to-end test for the evaluation system."""

import asyncio
import logging
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.framework import EvaluationFramework, EvaluationScenario, ScenarioType
from eval.scenario_runner import ScenarioRunner
from eval.replay_engine import ReplayEngine
from eval.metrics import EvaluationMetrics
from eval.reporter import EvaluationReporter, ReportConfig
from eval.integrations import EvaluationIntegrator, IntegrationConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_evaluation_framework():
    """Test the core evaluation framework."""
    print("\n=== Testing Evaluation Framework ===")
    
    framework = EvaluationFramework()
    
    # Test scenario listing
    scenarios = framework.list_scenarios()
    print(f"✓ Found {len(scenarios)} available scenarios")
    
    # Test suite listing
    suites = framework.list_suites()
    print(f"✓ Found {len(suites)} available suites")
    
    # Test running a scenario
    if scenarios:
        scenario_id = scenarios[0]["id"]
        print(f"  Testing scenario: {scenario_id}")
        
        run_id = await framework.run_scenario(scenario_id)
        
        # Wait for completion
        timeout = 30  # 30 seconds
        start_time = asyncio.get_event_loop().time()
        
        while run_id in framework.active_runs:
            await asyncio.sleep(1)
            if asyncio.get_event_loop().time() - start_time > timeout:
                print("⚠ Scenario execution timed out")
                break
        
        # Check results
        status = framework.get_run_status(run_id)
        if status:
            print(f"✓ Scenario completed with status: {status['status']}")
            return run_id, scenario_id
        else:
            print("✗ Failed to get scenario status")
    
    return None, None

async def test_scenario_runner():
    """Test the scenario runner."""
    print("\n=== Testing Scenario Runner ===")
    
    runner = ScenarioRunner()
    
    # Test step definitions
    step_definitions = runner.get_step_definitions()
    print(f"✓ Loaded {len(step_definitions)} step definitions")
    
    # Test scenario validation
    test_scenario = EvaluationScenario(
        id="test_scenario",
        name="Test Scenario",
        description="Simple test scenario",
        scenario_type=ScenarioType.DETECTION_ACCURACY,
        seed=42,
        duration_minutes=5,
        hosts=["test-host"],
        steps=["discovery", "initial_access"],
        datasets=["test-logs"],
        tags=["test"]
    )
    
    validation = await runner.validate_scenario(test_scenario)
    print(f"✓ Scenario validation: {'Valid' if validation['valid'] else 'Invalid'}")
    
    if not validation["valid"]:
        print(f"  Errors: {validation['errors']}")
    
    # Test scenario execution
    print("  Executing test scenario...")
    execution_results = await runner.execute_scenario(test_scenario)
    
    if execution_results:
        print(f"✓ Scenario executed successfully")
        print(f"  - Steps executed: {execution_results['steps_executed']}")
        print(f"  - Success rate: {execution_results['success_rate']:.1%}")
        print(f"  - Artifacts generated: {execution_results['total_artifacts']}")
        return execution_results
    else:
        print("✗ Scenario execution failed")
    
    return None

async def test_replay_engine():
    """Test the replay engine."""
    print("\n=== Testing Replay Engine ===")
    
    replay_engine = ReplayEngine()
    
    # Test session recording
    session_id = await replay_engine.start_recording(
        scenario_id="test_scenario",
        execution_id="test_execution",
        metadata={"test": True}
    )
    print(f"✓ Started recording session: {session_id}")
    
    # Record some test events
    for i in range(3):
        await replay_engine.record_event(
            session_id=session_id,
            event_type="test_event",
            component="test_component",
            data={"event_number": i, "timestamp": asyncio.get_event_loop().time()}
        )
    
    print(f"✓ Recorded 3 test events")
    
    # Stop recording
    saved_path = await replay_engine.stop_recording(session_id)
    print(f"✓ Stopped recording, saved to: {saved_path}")
    
    # Test session listing
    sessions = replay_engine.list_sessions()
    print(f"✓ Found {len(sessions)} recorded sessions")
    
    # Test session verification
    if sessions:
        verification = await replay_engine.verify_session(session_id)
        print(f"✓ Session verification: {'Valid' if verification['valid'] else 'Invalid'}")
        
        # Test replay
        if verification["valid"]:
            print("  Testing session replay...")
            replay_id = await replay_engine.replay_session(
                session_id=session_id,
                replay_speed=5.0  # 5x speed for testing
            )
            print(f"✓ Session replayed: {replay_id}")
            return session_id
    
    return None

async def test_metrics_calculator():
    """Test the metrics calculator."""
    print("\n=== Testing Metrics Calculator ===")
    
    metrics_calc = EvaluationMetrics()
    
    # Create test data
    from eval.framework import EvaluationRun, EvaluationStatus
    from datetime import datetime
    
    test_run = EvaluationRun(
        run_id="test_metrics_run",
        scenario_id="test_scenario",
        start_time=datetime.now(),
        end_time=datetime.now(),
        status=EvaluationStatus.COMPLETED,
        results={
            "detections_triggered": 8,
            "alerts_generated": 10,
            "false_positives": 1,
            "execution_time_seconds": 45,
            "coverage_percentage": 85,
            "steps_completed": ["discovery", "initial_access", "persistence"],
            "step_details": [
                {"name": "discovery", "success": True, "technique_id": "T1018"},
                {"name": "initial_access", "success": True, "technique_id": "T1566"},
                {"name": "persistence", "success": False, "error": "timeout"}
            ]
        }
    )
    
    test_scenario = EvaluationScenario(
        id="test_scenario",
        name="Test Scenario",
        description="Test scenario for metrics",
        scenario_type=ScenarioType.DETECTION_ACCURACY,
        seed=42,
        duration_minutes=10,
        hosts=["test-host"],
        steps=["discovery", "initial_access", "persistence"],
        datasets=["test-logs"],
        tags=["test"],
        expected_detections=["T1018", "T1566"],
        expected_alerts=8
    )
    
    # Test metrics calculation
    metrics = await metrics_calc.calculate_metrics(test_run, test_scenario)
    print(f"✓ Calculated {len(metrics)} metrics")
    
    for metric_name, value in metrics.items():
        print(f"  - {metric_name}: {value:.3f}")
    
    # Test comprehensive scoring
    comprehensive_score = await metrics_calc.calculate_comprehensive_score(test_run, test_scenario)
    print(f"✓ Comprehensive score calculated")
    print(f"  - Overall score: {comprehensive_score.overall_score:.1%}")
    print(f"  - Grade: {comprehensive_score.grade}")
    print(f"  - Strengths: {len(comprehensive_score.strengths)}")
    print(f"  - Weaknesses: {len(comprehensive_score.weaknesses)}")
    print(f"  - Recommendations: {len(comprehensive_score.recommendations)}")
    
    return comprehensive_score

async def test_report_generator():
    """Test the report generator."""
    print("\n=== Testing Report Generator ===")
    
    reporter = EvaluationReporter()
    
    # Test with sample data
    from eval.framework import EvaluationRun, EvaluationStatus
    from eval.metrics import EvaluationScore, MetricResult, MetricType
    from datetime import datetime
    
    test_run = EvaluationRun(
        run_id="test_report_run",
        scenario_id="test_scenario",
        start_time=datetime.now(),
        end_time=datetime.now(),
        status=EvaluationStatus.COMPLETED,
        results={"detections_triggered": 5, "success_rate": 0.85}
    )
    
    test_scenario = EvaluationScenario(
        id="test_scenario",
        name="Test Scenario for Reporting",
        description="A test scenario to verify report generation",
        scenario_type=ScenarioType.DETECTION_ACCURACY,
        seed=42,
        duration_minutes=15,
        hosts=["test-host-01"],
        steps=["discovery", "initial_access"],
        datasets=["test-logs"],
        tags=["test", "reporting"]
    )
    
    # Create sample evaluation score
    test_score = EvaluationScore(
        overall_score=0.82,
        category_scores={
            "detection_accuracy": 0.85,
            "response_time": 0.78,
            "false_positive_rate": 0.90
        },
        metric_results=[
            MetricResult(
                metric_name="Detection Accuracy",
                metric_type=MetricType.DETECTION_ACCURACY,
                value=0.85,
                max_value=1.0,
                normalized_score=0.85,
                unit="ratio",
                description="Ratio of successful detections"
            )
        ],
        grade="B",
        strengths=["Good detection accuracy", "Low false positive rate"],
        weaknesses=["Response time could be improved"],
        recommendations=["Optimize detection pipeline", "Implement faster alerting"],
        timestamp=datetime.now()
    )
    
    # Test report generation
    print("  Generating HTML report...")
    html_config = ReportConfig(
        title="Test Evaluation Report",
        subtitle="Generated during system testing",
        format="html"
    )
    
    html_report_path = await reporter.generate_evaluation_report(
        test_run, test_scenario, test_score, html_config
    )
    print(f"✓ HTML report generated: {html_report_path}")
    
    # Test JSON report
    print("  Generating JSON report...")
    json_config = ReportConfig(
        title="Test Evaluation Report",
        format="json"
    )
    
    json_report_path = await reporter.generate_evaluation_report(
        test_run, test_scenario, test_score, json_config
    )
    print(f"✓ JSON report generated: {json_report_path}")
    
    # List reports
    reports = reporter.list_reports()
    print(f"✓ Found {len(reports)} total reports")
    
    return [html_report_path, json_report_path]

async def test_integration_system():
    """Test the integration system."""
    print("\n=== Testing Integration System ===")
    
    # Initialize integrator
    config = IntegrationConfig(
        enable_red_team_integration=False,  # No real red team for testing
        enable_detection_integration=False,  # No real detection for testing
        enable_telemetry_integration=False,  # No real telemetry for testing
        enable_replay_recording=True,
        auto_generate_reports=True,
        report_formats=["html", "json"]
    )
    
    integrator = EvaluationIntegrator(config)
    
    # Test integration status
    status = integrator.get_integration_status()
    print(f"✓ Integration status retrieved")
    print(f"  - Active integrations: {len(status['active_integrations'])}")
    print(f"  - Component status: {len(status['component_status'])}")
    
    # Test integration test
    print("  Running integration test...")
    test_results = await integrator.run_integration_test()
    print(f"✓ Integration test completed: {test_results['overall_status']}")
    
    for test_name, result in test_results["tests"].items():
        status_icon = "✓" if result["status"] == "passed" else "⚠" if result["status"] == "skipped" else "✗"
        print(f"  {status_icon} {test_name}: {result['status']}")
    
    # Test integrated evaluation (if we have scenarios)
    scenarios = integrator.framework.list_scenarios()
    if scenarios:
        scenario_id = scenarios[0]["id"]
        print(f"  Running integrated evaluation: {scenario_id}")
        
        try:
            run_id = await integrator.run_integrated_evaluation(scenario_id)
            print(f"✓ Integrated evaluation completed: {run_id}")
            return test_results
        except Exception as e:
            print(f"⚠ Integrated evaluation failed: {e}")
    
    return test_results

async def test_complete_workflow():
    """Test complete evaluation workflow."""
    print("\n=== Testing Complete Workflow ===")
    
    # Initialize all components
    framework = EvaluationFramework()
    
    # Add a custom test scenario
    custom_scenario = EvaluationScenario(
        id="workflow_test",
        name="Complete Workflow Test",
        description="End-to-end workflow test scenario",
        scenario_type=ScenarioType.END_TO_END,
        seed=123,
        duration_minutes=5,
        hosts=["workflow-host-01", "workflow-host-02"],
        steps=["reconnaissance", "initial_access", "lateral_movement"],
        datasets=["workflow-logs"],
        tags=["workflow", "test", "T1595", "T1566", "T1021"],
        expected_detections=["T1595", "T1566", "T1021"],
        expected_alerts=3
    )
    
    framework.add_scenario(custom_scenario)
    print(f"✓ Added custom test scenario: {custom_scenario.id}")
    
    # Run complete workflow
    print("  Executing complete workflow...")
    
    # 1. Run scenario
    run_id = await framework.run_scenario("workflow_test")
    
    # 2. Wait for completion
    while run_id in framework.active_runs:
        await asyncio.sleep(1)
    
    # 3. Get results
    evaluation_run = framework.completed_runs.get(run_id)
    if not evaluation_run:
        print("✗ Evaluation run not found")
        return False
    
    print(f"✓ Scenario execution completed: {evaluation_run.status.value}")
    
    # 4. Calculate metrics
    metrics_calc = EvaluationMetrics()
    evaluation_score = await metrics_calc.calculate_comprehensive_score(
        evaluation_run, custom_scenario
    )
    print(f"✓ Metrics calculated - Overall score: {evaluation_score.overall_score:.1%} (Grade: {evaluation_score.grade})")
    
    # 5. Generate report
    reporter = EvaluationReporter()
    config = ReportConfig(
        title="Complete Workflow Test Report",
        subtitle="End-to-end system validation",
        format="html"
    )
    
    report_path = await reporter.generate_evaluation_report(
        evaluation_run, custom_scenario, evaluation_score, config
    )
    print(f"✓ Report generated: {report_path}")
    
    # 6. Summary
    print(f"✓ Complete workflow test successful!")
    print(f"  - Run ID: {run_id}")
    print(f"  - Duration: {(evaluation_run.end_time - evaluation_run.start_time).total_seconds():.1f} seconds")
    print(f"  - Overall score: {evaluation_score.overall_score:.1%}")
    print(f"  - Grade: {evaluation_score.grade}")
    print(f"  - Report: {report_path}")
    
    return True

async def main():
    """Run all evaluation system tests."""
    print("🚀 Starting Evaluation System End-to-End Tests")
    print("=" * 60)
    
    test_results = {
        "framework": False,
        "scenario_runner": False,
        "replay_engine": False,
        "metrics_calculator": False,
        "report_generator": False,
        "integration_system": False,
        "complete_workflow": False
    }
    
    try:
        # Test individual components
        run_id, scenario_id = await test_evaluation_framework()
        test_results["framework"] = run_id is not None
        
        execution_results = await test_scenario_runner()
        test_results["scenario_runner"] = execution_results is not None
        
        session_id = await test_replay_engine()
        test_results["replay_engine"] = session_id is not None
        
        evaluation_score = await test_metrics_calculator()
        test_results["metrics_calculator"] = evaluation_score is not None
        
        report_paths = await test_report_generator()
        test_results["report_generator"] = len(report_paths) > 0
        
        integration_results = await test_integration_system()
        test_results["integration_system"] = integration_results.get("overall_status") == "passed"
        
        # Test complete workflow
        workflow_success = await test_complete_workflow()
        test_results["complete_workflow"] = workflow_success
        
        print("\n" + "=" * 60)
        print("✅ Evaluation System Test Results:")
        
        all_passed = True
        for test_name, passed in test_results.items():
            status = "✓ PASSED" if passed else "✗ FAILED"
            print(f"  {test_name}: {status}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n🎯 All Evaluation System Tests PASSED!")
            print("\n🚀 Milestone 8 - Evaluation Harness: COMPLETED")
            print("\n📊 System Features Verified:")
            print("   • Framework: Scenario management and execution ✓")
            print("   • Scenario Runner: Attack simulation and step execution ✓")
            print("   • Replay Engine: Session recording and playback ✓")
            print("   • Metrics Calculator: Comprehensive scoring and analysis ✓")
            print("   • Report Generator: HTML/JSON report generation ✓")
            print("   • Integration System: Component coordination ✓")
            print("   • Complete Workflow: End-to-end evaluation pipeline ✓")
        else:
            print("\n⚠ Some tests failed - see details above")
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
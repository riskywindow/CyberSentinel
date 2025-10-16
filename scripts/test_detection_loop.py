#!/usr/bin/env python3
"""Test script for detection loop system (Milestone 6)."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from detection.coordinator import DetectionLoopCoordinator, DetectionLoopConfig
from detection.rule_deployment import SigmaRuleDeployer
from detection.feedback_loop import DetectionFeedbackLoop, FeedbackType
from detection.performance_monitor import RulePerformanceMonitor
from detection.tuning_engine import ContinuousTuningEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_sample_sigma_rules():
    """Create sample Sigma rules for testing."""
    
    rules = [
        {
            "rule_id": "test_rule_001",
            "title": "Detect SSH Brute Force Attack",
            "rule_yaml": """
title: SSH Brute Force Attack
id: test_rule_001
status: experimental
description: Detects SSH brute force attacks
author: CyberSentinel
date: 2023/10/01
logsource:
    service: sshd
    product: linux
detection:
    selection:
        event.outcome: "failure"
        destination.port: 22
        network.protocol: "tcp"
    condition: selection | count() > 5
    timeframe: 5m
level: medium
falsepositives:
    - Legitimate failed login attempts
    - Network connectivity issues
            """.strip(),
            "validation": {"valid": True, "errors": []},
            "source_incident": "incident_001",
            "generated_at": "2023-10-01T15:30:00Z",
            "incident_severity": "high"
        },
        {
            "rule_id": "test_rule_002", 
            "title": "Detect Suspicious Process Execution",
            "rule_yaml": """
title: Suspicious Process Execution
id: test_rule_002
status: experimental
description: Detects execution of suspicious processes
author: CyberSentinel
date: 2023/10/01
logsource:
    category: process_creation
    product: linux
detection:
    selection:
        process.name: "*suspicious*"
        event.category: "process"
    condition: selection
level: high
falsepositives:
    - Legitimate administrative tools
            """.strip(),
            "validation": {"valid": True, "errors": []},
            "source_incident": "incident_002",
            "generated_at": "2023-10-01T16:15:00Z",
            "incident_severity": "critical"
        },
        {
            "rule_id": "test_rule_003",
            "title": "Detect Network Anomaly",
            "rule_yaml": """
title: Network Anomaly Detection
id: test_rule_003
status: experimental
description: Detects unusual network traffic patterns
author: CyberSentinel
date: 2023/10/01
logsource:
    category: network
    product: linux
detection:
    selection:
        network.bytes: ">10000000"
        event.category: "network"
    condition: selection
level: low
falsepositives:
    - Large file transfers
    - Backup operations
            """.strip(),
            "validation": {"valid": True, "errors": []},
            "source_incident": "incident_003",
            "generated_at": "2023-10-01T17:00:00Z",
            "incident_severity": "medium"
        }
    ]
    
    return rules

async def test_rule_deployment():
    """Test Sigma rule deployment system."""
    
    logger.info("=== Testing Rule Deployment System ===")
    
    try:
        deployer = SigmaRuleDeployer()
        
        # Test deployment status
        status = deployer.get_deployment_status()
        logger.info(f"✓ Deployment targets: {status['total_targets']}")
        logger.info(f"✓ Enabled targets: {status['enabled_targets']}")
        
        # Test connection to all targets
        connections = await deployer.test_all_connections()
        logger.info(f"✓ Connection tests completed")
        
        for target_name, connected in connections.items():
            status_symbol = "✓" if connected else "✗"
            logger.info(f"  {status_symbol} {target_name}")
        
        # Test rule deployment
        sample_rules = create_sample_sigma_rules()
        
        for rule in sample_rules[:2]:  # Deploy first 2 rules
            success = await deployer.deploy_rule(
                rule, 
                engines=["mock-engine"],  # Use mock engine for testing
                auto_deploy=True
            )
            
            status_symbol = "✓" if success else "✗"
            logger.info(f"  {status_symbol} Deployed {rule['rule_id']}: {rule['title']}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Rule deployment test failed: {e}")
        return False

async def test_feedback_loop():
    """Test detection feedback loop system."""
    
    logger.info("=== Testing Feedback Loop System ===")
    
    try:
        feedback_loop = DetectionFeedbackLoop()
        
        # Submit sample feedback
        rule_ids = ["test_rule_001", "test_rule_002", "test_rule_003"]
        
        feedback_submitted = 0
        for i, rule_id in enumerate(rule_ids):
            # Submit different types of feedback
            feedback_types = [FeedbackType.TRUE_POSITIVE, FeedbackType.FALSE_POSITIVE, FeedbackType.BENIGN_POSITIVE]
            
            for j, feedback_type in enumerate(feedback_types):
                success = await feedback_loop.submit_feedback(
                    rule_id=rule_id,
                    alert_id=f"alert_{rule_id}_{j}",
                    feedback_type=feedback_type,
                    source="analyst",
                    confidence=0.8 + (j * 0.1),
                    analyst_notes=f"Test feedback for {feedback_type.value}"
                )
                
                if success:
                    feedback_submitted += 1
        
        logger.info(f"✓ Submitted {feedback_submitted} feedback items")
        
        # Analyze rule performance
        for rule_id in rule_ids:
            metrics = await feedback_loop.analyze_rule_performance(rule_id, evaluation_hours=24)
            
            if metrics:
                logger.info(f"✓ {rule_id} performance:")
                logger.info(f"  - Performance score: {metrics.performance_score:.3f}")
                logger.info(f"  - Precision: {metrics.precision:.3f}")
                logger.info(f"  - Recall: {metrics.recall:.3f}")
                logger.info(f"  - F1 score: {metrics.f1_score:.3f}")
        
        # Generate feedback report
        report = await feedback_loop.generate_feedback_report(rule_ids)
        logger.info(f"✓ Generated feedback report:")
        logger.info(f"  - Rules analyzed: {report['total_rules_analyzed']}")
        logger.info(f"  - Avg performance: {report['summary']['avg_performance_score']:.3f}")
        logger.info(f"  - High performers: {len(report['summary']['high_performers'])}")
        logger.info(f"  - Poor performers: {len(report['summary']['poor_performers'])}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Feedback loop test failed: {e}")
        return False

async def test_performance_monitor():
    """Test rule performance monitoring system."""
    
    logger.info("=== Testing Performance Monitor ===")
    
    try:
        monitor = RulePerformanceMonitor()
        
        # Test performance analysis
        rule_ids = ["test_rule_001", "test_rule_002", "test_rule_003"]
        
        performance_scores = await monitor.analyze_rule_performance(rule_ids, window_hours=168)
        
        logger.info(f"✓ Analyzed performance for {len(performance_scores)} rules")
        
        for rule_id, score in performance_scores.items():
            logger.info(f"  - {rule_id}: {score:.3f}")
        
        # Generate health report
        health_report = await monitor.get_rule_health_report(rule_ids)
        
        logger.info(f"✓ Health report generated:")
        logger.info(f"  - Total rules: {health_report['total_rules']}")
        logger.info(f"  - Healthy rules: {health_report['summary']['healthy_rules']}")
        logger.info(f"  - Warning rules: {health_report['summary']['warning_rules']}")
        logger.info(f"  - Critical rules: {health_report['summary']['critical_rules']}")
        logger.info(f"  - Avg health score: {health_report['summary']['avg_health_score']:.3f}")
        
        # Test threshold updates
        original_thresholds = monitor.get_performance_thresholds()
        logger.info(f"✓ Current thresholds: {len(original_thresholds)} configured")
        
        # Update thresholds
        new_thresholds = {"min_performance_score": 0.7}
        monitor.update_performance_thresholds(new_thresholds)
        
        updated_thresholds = monitor.get_performance_thresholds()
        logger.info(f"✓ Updated thresholds: min_performance_score = {updated_thresholds['min_performance_score']}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Performance monitor test failed: {e}")
        return False

async def test_tuning_engine():
    """Test continuous tuning engine."""
    
    logger.info("=== Testing Tuning Engine ===")
    
    try:
        tuning_engine = ContinuousTuningEngine()
        
        # Test rule tuning
        performance_scores = {
            "test_rule_001": 0.4,  # Poor performance - needs tuning
            "test_rule_002": 0.8,  # Good performance
            "test_rule_003": 0.3   # Very poor performance - needs tuning
        }
        
        deployed_rules = set(performance_scores.keys())
        
        tuned_count = await tuning_engine.tune_rules(performance_scores, deployed_rules)
        
        logger.info(f"✓ Tuned {tuned_count} rules automatically")
        
        # Check pending recommendations
        pending = tuning_engine.get_pending_recommendations()
        logger.info(f"✓ Generated recommendations for {len(pending)} rules")
        
        for rule_id, recommendations in pending.items():
            logger.info(f"  - {rule_id}: {len(recommendations)} recommendations")
            for rec in recommendations:
                logger.info(f"    * {rec['strategy']} - {rec['description']}")
        
        # Test manual approval of a recommendation
        if pending:
            rule_id = list(pending.keys())[0]
            recommendations = pending[rule_id]
            
            if recommendations:
                rec_id = f"{rule_id}_{recommendations[0]['strategy']}"
                approval_success = await tuning_engine.approve_recommendation(rule_id, rec_id)
                
                status_symbol = "✓" if approval_success else "✗"
                logger.info(f"  {status_symbol} Manual approval test")
        
        # Get tuning statistics
        stats = tuning_engine.get_tuning_statistics()
        logger.info(f"✓ Tuning statistics:")
        logger.info(f"  - Pending recommendations: {stats['total_pending_recommendations']}")
        logger.info(f"  - Applied tunings: {stats['total_applied_tunings']}")
        logger.info(f"  - Success rate: {stats['success_rate']:.3f}")
        
        # Get tuning history
        history = tuning_engine.get_tuning_history(limit=10)
        logger.info(f"✓ Tuning history: {len(history)} recent entries")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Tuning engine test failed: {e}")
        return False

async def test_detection_coordinator():
    """Test detection loop coordinator."""
    
    logger.info("=== Testing Detection Loop Coordinator ===")
    
    try:
        # Create test configuration
        config = DetectionLoopConfig(
            cycle_interval_minutes=1,  # Short interval for testing
            lookback_hours=24,
            min_confidence_threshold=0.7,
            max_rules_per_cycle=5,
            auto_deployment_enabled=True,
            detection_engines=["mock-engine"]
        )
        
        # Initialize coordinator (without storage for testing)
        coordinator = DetectionLoopCoordinator(
            config=config,
            clickhouse_client=None,  # Mock storage
            neo4j_client=None
        )
        
        # Test single cycle execution
        logger.info("Running single detection cycle...")
        
        cycle_result = await coordinator.run_single_cycle()
        
        if cycle_result:
            logger.info(f"✓ Detection cycle completed:")
            logger.info(f"  - Cycle ID: {cycle_result.cycle_id}")
            logger.info(f"  - Status: {cycle_result.status}")
            logger.info(f"  - Incidents processed: {cycle_result.incidents_processed}")
            logger.info(f"  - Rules deployed: {cycle_result.rules_deployed}")
            logger.info(f"  - Rules tuned: {cycle_result.rules_tuned}")
            logger.info(f"  - Feedback collected: {cycle_result.feedback_collected}")
        else:
            logger.warning("✗ No cycle result returned")
        
        # Test coordinator status
        status = coordinator.get_status()
        logger.info(f"✓ Coordinator status:")
        logger.info(f"  - Running: {status['running']}")
        logger.info(f"  - Total cycles: {status['total_cycles']}")
        logger.info(f"  - Deployed rules: {status['deployed_rules_count']}")
        
        # Test cycle history
        history = coordinator.get_cycle_history(limit=5)
        logger.info(f"✓ Cycle history: {len(history)} entries")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Detection coordinator test failed: {e}")
        return False

async def test_end_to_end_integration():
    """Test end-to-end detection loop integration."""
    
    logger.info("=== Testing End-to-End Integration ===")
    
    try:
        # Test complete workflow with mock data
        sample_rules = create_sample_sigma_rules()
        
        # 1. Deploy rules
        deployer = SigmaRuleDeployer()
        deployed_rules = set()
        
        for rule in sample_rules:
            success = await deployer.deploy_rule(rule, engines=["mock-engine"], auto_deploy=True)
            if success:
                deployed_rules.add(rule["rule_id"])
        
        logger.info(f"✓ Deployed {len(deployed_rules)} rules")
        
        # 2. Simulate feedback collection
        feedback_loop = DetectionFeedbackLoop()
        
        for rule_id in deployed_rules:
            # Submit mixed feedback
            await feedback_loop.submit_feedback(
                rule_id=rule_id,
                alert_id=f"alert_{rule_id}_tp",
                feedback_type=FeedbackType.TRUE_POSITIVE,
                source="analyst"
            )
            
            await feedback_loop.submit_feedback(
                rule_id=rule_id,
                alert_id=f"alert_{rule_id}_fp",
                feedback_type=FeedbackType.FALSE_POSITIVE,
                source="analyst"
            )
        
        logger.info(f"✓ Submitted feedback for {len(deployed_rules)} rules")
        
        # 3. Monitor performance
        monitor = RulePerformanceMonitor()
        performance_scores = await monitor.analyze_rule_performance(list(deployed_rules))
        
        logger.info(f"✓ Monitored performance for {len(performance_scores)} rules")
        
        # 4. Apply tuning
        tuning_engine = ContinuousTuningEngine()
        tuned_count = await tuning_engine.tune_rules(performance_scores, deployed_rules)
        
        logger.info(f"✓ Applied tuning to {tuned_count} rules")
        
        # 5. Generate comprehensive report
        feedback_report = await feedback_loop.generate_feedback_report(list(deployed_rules))
        health_report = await monitor.get_rule_health_report(list(deployed_rules))
        tuning_stats = tuning_engine.get_tuning_statistics()
        
        logger.info(f"✓ End-to-end integration test completed:")
        logger.info(f"  - Rules deployed: {len(deployed_rules)}")
        logger.info(f"  - Avg performance: {feedback_report['summary']['avg_performance_score']:.3f}")
        logger.info(f"  - Avg health score: {health_report['summary']['avg_health_score']:.3f}")
        logger.info(f"  - Tuning recommendations: {tuning_stats['total_pending_recommendations']}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ End-to-end integration test failed: {e}")
        return False

async def main():
    """Main test execution."""
    
    logger.info("Starting CyberSentinel Detection Loop Tests")
    logger.info("=" * 60)
    
    test_results = {}
    
    try:
        # Test individual components
        logger.info("1. Testing Rule Deployment...")
        test_results["rule_deployment"] = await test_rule_deployment()
        print()
        
        logger.info("2. Testing Feedback Loop...")
        test_results["feedback_loop"] = await test_feedback_loop()
        print()
        
        logger.info("3. Testing Performance Monitor...")
        test_results["performance_monitor"] = await test_performance_monitor()
        print()
        
        logger.info("4. Testing Tuning Engine...")
        test_results["tuning_engine"] = await test_tuning_engine()
        print()
        
        logger.info("5. Testing Detection Coordinator...")
        test_results["detection_coordinator"] = await test_detection_coordinator()
        print()
        
        logger.info("6. Testing End-to-End Integration...")
        test_results["end_to_end"] = await test_end_to_end_integration()
        print()
        
        # Summary
        logger.info("=" * 60)
        logger.info("DETECTION LOOP TEST RESULTS")
        logger.info("=" * 60)
        
        passed = sum(test_results.values())
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✓ PASSED" if result else "✗ FAILED"
            logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
        
        logger.info("=" * 60)
        logger.info(f"OVERALL: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 All detection loop tests completed successfully!")
            logger.info("Detection loop system is ready for Milestone 6")
        else:
            logger.error("❌ Some tests failed")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
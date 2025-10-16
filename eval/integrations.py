"""Evaluation Integrations - connects evaluation system with detection and red team components."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from eval.framework import EvaluationFramework, EvaluationScenario, EvaluationRun
from eval.scenario_runner import ScenarioRunner
from eval.replay_engine import ReplayEngine
from eval.metrics import EvaluationMetrics
from eval.reporter import EvaluationReporter, ReportConfig

logger = logging.getLogger(__name__)

@dataclass
class IntegrationConfig:
    """Configuration for system integrations."""
    enable_red_team_integration: bool = True
    enable_detection_integration: bool = True
    enable_telemetry_integration: bool = True
    enable_replay_recording: bool = True
    auto_generate_reports: bool = True
    report_formats: List[str] = None
    
    def __post_init__(self):
        if self.report_formats is None:
            self.report_formats = ["html", "json"]

class EvaluationIntegrator:
    """Integrates evaluation system with other CyberSentinel components."""
    
    def __init__(self, config: IntegrationConfig = None):
        self.config = config or IntegrationConfig()
        
        # Core evaluation components
        self.framework = EvaluationFramework()
        self.scenario_runner = ScenarioRunner()
        self.replay_engine = ReplayEngine()
        self.metrics_calculator = EvaluationMetrics()
        self.reporter = EvaluationReporter()
        
        # External system references
        self.red_team_simulator = None
        self.detection_coordinator = None
        self.telemetry_generator = None
        self.storage_clients = {}
        
        # Integration state
        self.active_integrations: Dict[str, Any] = {}
        self.integration_callbacks: Dict[str, List[Callable]] = {
            "detection_triggered": [],
            "alert_generated": [], 
            "technique_executed": [],
            "scenario_completed": []
        }
        
        # Connect components
        self._setup_component_integrations()
        
        logger.info("Evaluation integrator initialized")
    
    def _setup_component_integrations(self):
        """Set up integrations between evaluation components."""
        
        # Connect framework with other components
        self.framework.set_components(
            scenario_runner=self.scenario_runner,
            replay_engine=self.replay_engine,
            metrics_calculator=self.metrics_calculator,
            reporter=self.reporter
        )
        
        # Set up event handlers
        self.framework.add_event_handler(self._handle_evaluation_event)
        self.replay_engine.add_event_handler(self._handle_replay_event)
        
        logger.info("Component integrations established")
    
    async def integrate_red_team_simulator(self, red_team_simulator):
        """Integrate with red team simulator."""
        
        if not self.config.enable_red_team_integration:
            logger.info("Red team integration disabled")
            return
        
        self.red_team_simulator = red_team_simulator
        
        # Set up integrations
        self.scenario_runner.set_integrations(red_team_simulator=red_team_simulator)
        self.replay_engine.set_integrations(red_team_simulator=red_team_simulator)
        
        self.active_integrations["red_team"] = {
            "status": "connected",
            "component": red_team_simulator,
            "connected_at": datetime.now()
        }
        
        logger.info("Red team simulator integration established")
    
    async def integrate_detection_system(self, detection_coordinator):
        """Integrate with detection system."""
        
        if not self.config.enable_detection_integration:
            logger.info("Detection integration disabled")
            return
        
        self.detection_coordinator = detection_coordinator
        
        # Set up integrations
        self.scenario_runner.set_integrations(detection_system=detection_coordinator)
        self.replay_engine.set_integrations(detection_system=detection_coordinator)
        
        # Subscribe to detection events
        if hasattr(detection_coordinator, 'add_event_handler'):
            detection_coordinator.add_event_handler(self._handle_detection_event)
        
        self.active_integrations["detection"] = {
            "status": "connected", 
            "component": detection_coordinator,
            "connected_at": datetime.now()
        }
        
        logger.info("Detection system integration established")
    
    async def integrate_telemetry_system(self, telemetry_generator):
        """Integrate with telemetry generation system."""
        
        if not self.config.enable_telemetry_integration:
            logger.info("Telemetry integration disabled")
            return
        
        self.telemetry_generator = telemetry_generator
        
        # Set up integrations
        self.scenario_runner.set_integrations(telemetry_generator=telemetry_generator)
        self.replay_engine.set_integrations(telemetry_source=telemetry_generator)
        
        self.active_integrations["telemetry"] = {
            "status": "connected",
            "component": telemetry_generator,
            "connected_at": datetime.now()
        }
        
        logger.info("Telemetry system integration established")
    
    async def run_integrated_evaluation(self, scenario_id: str,
                                      configuration: Dict[str, Any] = None) -> str:
        """Run evaluation with full system integration."""
        
        logger.info(f"Starting integrated evaluation for scenario {scenario_id}")
        
        # Start replay recording if enabled
        recording_session_id = None
        if self.config.enable_replay_recording:
            execution_id = f"eval_{scenario_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            recording_session_id = await self.replay_engine.start_recording(
                scenario_id=scenario_id,
                execution_id=execution_id,
                metadata={"integration_mode": True, "configuration": configuration}
            )
            logger.info(f"Started replay recording: {recording_session_id}")
        
        try:
            # Run the evaluation through the framework
            run_id = await self.framework.run_scenario(scenario_id, configuration)
            
            # Wait for completion
            while run_id in self.framework.active_runs:
                await asyncio.sleep(1)
            
            # Get evaluation results
            evaluation_run = self.framework.completed_runs.get(run_id)
            if not evaluation_run:
                raise Exception(f"Evaluation run {run_id} not found in completed runs")
            
            # Generate comprehensive score
            scenario = self.framework.scenarios[scenario_id]
            evaluation_score = await self.metrics_calculator.calculate_comprehensive_score(
                evaluation_run, scenario
            )
            
            # Generate reports if enabled
            if self.config.auto_generate_reports:
                await self._generate_integrated_reports(evaluation_run, scenario, evaluation_score)
            
            # Stop replay recording
            if recording_session_id:
                await self.replay_engine.stop_recording(recording_session_id)
                logger.info(f"Stopped replay recording: {recording_session_id}")
            
            # Fire completion callback
            await self._fire_integration_callback("scenario_completed", {
                "run_id": run_id,
                "scenario_id": scenario_id,
                "evaluation_score": evaluation_score,
                "recording_session_id": recording_session_id
            })
            
            logger.info(f"Integrated evaluation completed: {run_id}")
            return run_id
            
        except Exception as e:
            logger.error(f"Integrated evaluation failed: {e}")
            
            # Stop replay recording on error
            if recording_session_id:
                await self.replay_engine.stop_recording(recording_session_id)
            
            raise
    
    async def run_integrated_suite(self, suite_id: str,
                                 configuration: Dict[str, Any] = None) -> List[str]:
        """Run evaluation suite with full integration."""
        
        logger.info(f"Starting integrated suite evaluation: {suite_id}")
        
        # Run suite through framework
        run_ids = await self.framework.run_suite(suite_id, configuration)
        
        # Generate suite report if enabled
        if self.config.auto_generate_reports and run_ids:
            await self._generate_integrated_suite_report(suite_id, run_ids)
        
        logger.info(f"Integrated suite evaluation completed: {len(run_ids)} runs")
        return run_ids
    
    async def replay_with_detection_monitoring(self, session_id: str,
                                             replay_speed: float = 1.0) -> Dict[str, Any]:
        """Replay session while monitoring detection system responses."""
        
        if not self.detection_coordinator:
            raise Exception("Detection system not integrated")
        
        logger.info(f"Starting replay with detection monitoring: {session_id}")
        
        # Set up detection monitoring
        detection_events = []
        
        async def detection_monitor(event_data):
            if event_data.get("type") in ["detection_triggered", "alert_generated"]:
                detection_events.append({
                    "timestamp": datetime.now().isoformat(),
                    "event": event_data
                })
        
        # Add temporary detection handler
        original_handlers = self.integration_callbacks["detection_triggered"].copy()
        self.integration_callbacks["detection_triggered"].append(detection_monitor)
        
        try:
            # Start replay
            replay_id = await self.replay_engine.replay_session(
                session_id=session_id,
                replay_speed=replay_speed
            )
            
            # Wait for completion
            await asyncio.sleep(2)  # Give some time for events to settle
            
            # Analyze detection effectiveness
            analysis = await self._analyze_detection_effectiveness(detection_events, session_id)
            
            result = {
                "replay_id": replay_id,
                "session_id": session_id,
                "detection_events": len(detection_events),
                "analysis": analysis,
                "events": detection_events
            }
            
            logger.info(f"Replay with detection monitoring completed: {len(detection_events)} events")
            return result
            
        finally:
            # Restore original handlers
            self.integration_callbacks["detection_triggered"] = original_handlers
    
    async def _generate_integrated_reports(self, evaluation_run: EvaluationRun,
                                         scenario: EvaluationScenario,
                                         evaluation_score):
        """Generate reports with integration data."""
        
        for report_format in self.config.report_formats:
            config = ReportConfig(
                title=f"Integrated Evaluation Report: {scenario.name}",
                subtitle=f"Run ID: {evaluation_run.run_id}",
                include_executive_summary=True,
                include_detailed_metrics=True,
                include_recommendations=True,
                include_raw_data=True,
                format=report_format
            )
            
            try:
                report_path = await self.reporter.generate_evaluation_report(
                    evaluation_run, scenario, evaluation_score, config
                )
                logger.info(f"Generated {report_format} report: {report_path}")
            except Exception as e:
                logger.error(f"Failed to generate {report_format} report: {e}")
    
    async def _generate_integrated_suite_report(self, suite_id: str, run_ids: List[str]):
        """Generate suite report with integration data."""
        
        suite = self.framework.suites[suite_id]
        evaluation_runs = [self.framework.completed_runs[rid] for rid in run_ids if rid in self.framework.completed_runs]
        
        # Get scenarios and scores
        scenarios = {}
        evaluation_scores = []
        
        for run in evaluation_runs:
            if run.scenario_id in self.framework.scenarios:
                scenario = self.framework.scenarios[run.scenario_id]
                scenarios[run.scenario_id] = scenario
                
                # Calculate score
                score = await self.metrics_calculator.calculate_comprehensive_score(run, scenario)
                evaluation_scores.append(score)
        
        for report_format in self.config.report_formats:
            config = ReportConfig(
                title=f"Integrated Suite Report: {suite.name}",
                include_executive_summary=True,
                include_detailed_metrics=True,
                include_trend_analysis=True,
                include_recommendations=True,
                format=report_format
            )
            
            try:
                report_path = await self.reporter.generate_suite_report(
                    suite, evaluation_runs, scenarios, evaluation_scores, config
                )
                logger.info(f"Generated suite {report_format} report: {report_path}")
            except Exception as e:
                logger.error(f"Failed to generate suite {report_format} report: {e}")
    
    async def _analyze_detection_effectiveness(self, detection_events: List[Dict],
                                             session_id: str) -> Dict[str, Any]:
        """Analyze detection effectiveness during replay."""
        
        # Load original session for comparison
        session = await self.replay_engine.load_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # Count original events vs detections
        original_events = len(session.events)
        detection_count = len(detection_events)
        
        # Calculate detection rate
        detection_rate = detection_count / max(original_events, 1)
        
        # Analyze timing
        detection_times = []
        for event in detection_events:
            try:
                timestamp = datetime.fromisoformat(event["timestamp"])
                detection_times.append(timestamp)
            except:
                continue
        
        if detection_times:
            # Calculate response time statistics
            detection_times.sort()
            first_detection = detection_times[0]
            last_detection = detection_times[-1]
            
            total_time = (last_detection - first_detection).total_seconds()
            avg_interval = total_time / max(len(detection_times) - 1, 1)
        else:
            total_time = 0
            avg_interval = 0
        
        analysis = {
            "detection_rate": detection_rate,
            "total_detections": detection_count,
            "original_events": original_events,
            "response_time_stats": {
                "total_detection_window_seconds": total_time,
                "average_detection_interval_seconds": avg_interval,
                "first_detection": detection_times[0].isoformat() if detection_times else None,
                "last_detection": detection_times[-1].isoformat() if detection_times else None
            },
            "effectiveness_score": min(1.0, detection_rate),
            "summary": f"Detected {detection_count}/{original_events} events ({detection_rate:.1%})"
        }
        
        return analysis
    
    async def _handle_evaluation_event(self, event_data: Dict[str, Any]):
        """Handle events from evaluation framework."""
        
        event_type = event_data.get("type")
        
        if event_type == "evaluation_started":
            # Record event if replay is active
            if self.config.enable_replay_recording:
                for session_id in self.replay_engine.recording_sessions:
                    await self.replay_engine.record_event(
                        session_id=session_id,
                        event_type="evaluation_started",
                        component="evaluation_framework",
                        data=event_data
                    )
        
        elif event_type == "evaluation_completed":
            # Fire callback
            await self._fire_integration_callback("scenario_completed", event_data)
    
    async def _handle_replay_event(self, event_data: Dict[str, Any]):
        """Handle events from replay engine."""
        
        event_type = event_data.get("type")
        
        if event_type == "event_replayed":
            # Forward to appropriate system
            original_event = event_data.get("original_event", {})
            component = original_event.get("component")
            
            if component == "red_team" and self.red_team_simulator:
                # Would trigger red team simulator
                pass
            elif component == "detection" and self.detection_coordinator:
                # Would trigger detection system
                pass
    
    async def _handle_detection_event(self, event_data: Dict[str, Any]):
        """Handle events from detection system."""
        
        # Record in replay if active
        if self.config.enable_replay_recording:
            for session_id in self.replay_engine.recording_sessions:
                await self.replay_engine.record_event(
                    session_id=session_id,
                    event_type="detection_event",
                    component="detection_system",
                    data=event_data
                )
        
        # Fire callback
        await self._fire_integration_callback("detection_triggered", event_data)
    
    async def _fire_integration_callback(self, callback_type: str, event_data: Dict[str, Any]):
        """Fire integration callbacks."""
        
        if callback_type in self.integration_callbacks:
            for callback in self.integration_callbacks[callback_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data)
                    else:
                        callback(event_data)
                except Exception as e:
                    logger.error(f"Error in integration callback {callback_type}: {e}")
    
    def add_integration_callback(self, callback_type: str, callback: Callable):
        """Add integration callback."""
        
        if callback_type in self.integration_callbacks:
            self.integration_callbacks[callback_type].append(callback)
            logger.info(f"Added integration callback for {callback_type}")
        else:
            logger.warning(f"Unknown callback type: {callback_type}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all integrations."""
        
        status = {
            "config": {
                "red_team_enabled": self.config.enable_red_team_integration,
                "detection_enabled": self.config.enable_detection_integration,
                "telemetry_enabled": self.config.enable_telemetry_integration,
                "replay_enabled": self.config.enable_replay_recording,
                "auto_reports": self.config.auto_generate_reports
            },
            "active_integrations": {},
            "component_status": {
                "framework": "connected",
                "scenario_runner": "connected",
                "replay_engine": "connected",
                "metrics_calculator": "connected",
                "reporter": "connected"
            }
        }
        
        for integration_name, integration_data in self.active_integrations.items():
            status["active_integrations"][integration_name] = {
                "status": integration_data["status"],
                "connected_at": integration_data["connected_at"].isoformat(),
                "component_type": type(integration_data["component"]).__name__
            }
        
        return status
    
    async def run_integration_test(self) -> Dict[str, Any]:
        """Run integration test to verify all components work together."""
        
        logger.info("Starting integration test")
        
        test_results = {
            "test_id": f"integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "start_time": datetime.now().isoformat(),
            "tests": {},
            "overall_status": "pending"
        }
        
        # Test 1: Framework functionality
        try:
            scenarios = self.framework.list_scenarios()
            test_results["tests"]["framework"] = {
                "status": "passed",
                "scenarios_available": len(scenarios)
            }
        except Exception as e:
            test_results["tests"]["framework"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Test 2: Scenario runner
        try:
            step_definitions = self.scenario_runner.get_step_definitions()
            test_results["tests"]["scenario_runner"] = {
                "status": "passed",
                "step_definitions": len(step_definitions)
            }
        except Exception as e:
            test_results["tests"]["scenario_runner"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Test 3: Replay engine
        try:
            sessions = self.replay_engine.list_sessions()
            test_results["tests"]["replay_engine"] = {
                "status": "passed",
                "sessions_available": len(sessions)
            }
        except Exception as e:
            test_results["tests"]["replay_engine"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Test 4: Metrics calculator
        try:
            # Test with dummy data
            from eval.framework import EvaluationRun, EvaluationStatus
            dummy_run = EvaluationRun(
                run_id="test_run",
                scenario_id="test_scenario",
                start_time=datetime.now(),
                status=EvaluationStatus.COMPLETED,
                results={"detections_triggered": 5}
            )
            dummy_scenario = self.framework.scenarios.get("basic_detection_test")
            
            if dummy_scenario:
                metrics = await self.metrics_calculator.calculate_metrics(dummy_run, dummy_scenario)
                test_results["tests"]["metrics_calculator"] = {
                    "status": "passed",
                    "metrics_calculated": len(metrics)
                }
            else:
                test_results["tests"]["metrics_calculator"] = {
                    "status": "skipped",
                    "reason": "No test scenario available"
                }
        except Exception as e:
            test_results["tests"]["metrics_calculator"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Test 5: Reporter
        try:
            reports = self.reporter.list_reports()
            test_results["tests"]["reporter"] = {
                "status": "passed",
                "reports_available": len(reports)
            }
        except Exception as e:
            test_results["tests"]["reporter"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Calculate overall status
        failed_tests = [name for name, result in test_results["tests"].items() if result["status"] == "failed"]
        
        if not failed_tests:
            test_results["overall_status"] = "passed"
        else:
            test_results["overall_status"] = "failed"
            test_results["failed_tests"] = failed_tests
        
        test_results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"Integration test completed: {test_results['overall_status']}")
        return test_results
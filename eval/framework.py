"""Evaluation Framework - core infrastructure for testing detection capabilities."""

import asyncio
import logging
import json
import uuid
import yaml
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

class EvaluationStatus(Enum):
    """Status of evaluation runs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScenarioType(Enum):
    """Types of evaluation scenarios."""
    DETECTION_ACCURACY = "detection_accuracy"
    RESPONSE_TIME = "response_time"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    COVERAGE_ASSESSMENT = "coverage_assessment"
    END_TO_END = "end_to_end"

@dataclass
class EvaluationScenario:
    """Definition of an evaluation scenario."""
    id: str
    name: str
    description: str
    scenario_type: ScenarioType
    seed: int
    duration_minutes: int
    hosts: List[str]
    steps: List[str]
    datasets: List[str]
    tags: List[str]
    expected_detections: List[str] = None
    expected_alerts: int = 0
    max_false_positives: int = 10
    success_criteria: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.expected_detections is None:
            self.expected_detections = []
        if self.success_criteria is None:
            self.success_criteria = {}

@dataclass
class EvaluationRun:
    """Individual evaluation run instance."""
    run_id: str
    scenario_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: EvaluationStatus = EvaluationStatus.PENDING
    configuration: Dict[str, Any] = None
    results: Dict[str, Any] = None
    error_message: Optional[str] = None
    metrics: Dict[str, float] = None
    
    def __post_init__(self):
        if self.configuration is None:
            self.configuration = {}
        if self.results is None:
            self.results = {}
        if self.metrics is None:
            self.metrics = {}

@dataclass
class EvaluationSuite:
    """Collection of related evaluation scenarios."""
    suite_id: str
    name: str
    description: str
    scenarios: List[str]  # Scenario IDs
    parallel_execution: bool = False
    timeout_minutes: int = 120
    retry_failed: bool = True
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class EvaluationFramework:
    """Main evaluation framework for testing detection capabilities."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent
        
        # Core components
        self.scenarios: Dict[str, EvaluationScenario] = {}
        self.suites: Dict[str, EvaluationSuite] = {}
        self.active_runs: Dict[str, EvaluationRun] = {}
        self.completed_runs: Dict[str, EvaluationRun] = {}
        
        # Event handlers
        self.event_handlers: List[Callable] = []
        
        # Integration points
        self.scenario_runner = None
        self.replay_engine = None
        self.metrics_calculator = None
        self.reporter = None
        
        # Load scenarios and suites
        self._load_scenarios()
        self._load_suites()
        
        logger.info(f"Evaluation framework initialized with {len(self.scenarios)} scenarios and {len(self.suites)} suites")
    
    def _load_scenarios(self):
        """Load evaluation scenarios from configuration files."""
        
        scenarios_file = self.data_dir / "suite" / "scenarios.yml"
        if scenarios_file.exists():
            try:
                with open(scenarios_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                for scenario_data in config.get("scenarios", []):
                    scenario = EvaluationScenario(
                        id=scenario_data["id"],
                        name=scenario_data["name"],
                        description=scenario_data["description"],
                        scenario_type=ScenarioType.END_TO_END,  # Default type
                        seed=scenario_data.get("seed", 42),
                        duration_minutes=scenario_data.get("duration_minutes", 15),
                        hosts=scenario_data.get("hosts", []),
                        steps=scenario_data.get("steps", []),
                        datasets=scenario_data.get("datasets", []),
                        tags=scenario_data.get("tags", [])
                    )
                    
                    self.scenarios[scenario.id] = scenario
                
                logger.info(f"Loaded {len(self.scenarios)} scenarios from {scenarios_file}")
                
            except Exception as e:
                logger.error(f"Failed to load scenarios from {scenarios_file}: {e}")
        else:
            logger.warning(f"Scenarios file not found: {scenarios_file}")
            self._create_default_scenarios()
    
    def _create_default_scenarios(self):
        """Create default scenarios if none are loaded."""
        
        default_scenarios = [
            EvaluationScenario(
                id="basic_detection_test",
                name="Basic Detection Test",
                description="Simple test of detection capabilities",
                scenario_type=ScenarioType.DETECTION_ACCURACY,
                seed=42,
                duration_minutes=10,
                hosts=["test-host-01"],
                steps=["reconnaissance", "initial_access", "persistence"],
                datasets=["test_logs"],
                tags=["basic", "detection"]
            ),
            EvaluationScenario(
                id="false_positive_test",
                name="False Positive Assessment",
                description="Test for false positive rates",
                scenario_type=ScenarioType.FALSE_POSITIVE_RATE,
                seed=123,
                duration_minutes=15,
                hosts=["test-host-01", "test-host-02"],
                steps=["normal_activity", "benign_processes"],
                datasets=["normal_logs"],
                tags=["false-positive", "baseline"],
                max_false_positives=2
            )
        ]
        
        for scenario in default_scenarios:
            self.scenarios[scenario.id] = scenario
        
        logger.info(f"Created {len(default_scenarios)} default scenarios")
    
    def _load_suites(self):
        """Load evaluation suites from configuration."""
        
        # Create default suites
        default_suites = [
            EvaluationSuite(
                suite_id="detection_accuracy_suite",
                name="Detection Accuracy Test Suite",
                description="Comprehensive testing of detection accuracy",
                scenarios=list(self.scenarios.keys()),
                parallel_execution=False,
                timeout_minutes=60,
                tags=["accuracy", "detection"]
            ),
            EvaluationSuite(
                suite_id="quick_smoke_test",
                name="Quick Smoke Test",
                description="Fast validation of basic functionality",
                scenarios=[sid for sid in self.scenarios.keys()],
                parallel_execution=True,
                timeout_minutes=30,
                tags=["smoke", "quick"]
            )
        ]
        
        for suite in default_suites:
            self.suites[suite.suite_id] = suite
        
        logger.info(f"Created {len(default_suites)} evaluation suites")
    
    async def run_scenario(self, scenario_id: str, 
                          configuration: Dict[str, Any] = None) -> str:
        """Run a single evaluation scenario."""
        
        if scenario_id not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        
        scenario = self.scenarios[scenario_id]
        run_id = str(uuid.uuid4())
        
        # Create evaluation run
        evaluation_run = EvaluationRun(
            run_id=run_id,
            scenario_id=scenario_id,
            start_time=datetime.now(),
            configuration=configuration or {},
            status=EvaluationStatus.RUNNING
        )
        
        self.active_runs[run_id] = evaluation_run
        
        try:
            logger.info(f"Starting evaluation run {run_id} for scenario {scenario_id}")
            
            # Fire start event
            await self._fire_event({
                "type": "evaluation_started",
                "run_id": run_id,
                "scenario_id": scenario_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Execute the scenario
            if self.scenario_runner:
                results = await self.scenario_runner.execute_scenario(scenario, configuration)
                evaluation_run.results = results
            else:
                # Simulate execution for testing
                await self._simulate_scenario_execution(evaluation_run, scenario)
            
            # Calculate metrics
            if self.metrics_calculator:
                metrics = await self.metrics_calculator.calculate_metrics(evaluation_run, scenario)
                evaluation_run.metrics = metrics
            else:
                evaluation_run.metrics = {"simulated_score": 0.85}
            
            # Mark as completed
            evaluation_run.status = EvaluationStatus.COMPLETED
            evaluation_run.end_time = datetime.now()
            
            # Move to completed runs
            self.completed_runs[run_id] = evaluation_run
            del self.active_runs[run_id]
            
            logger.info(f"Evaluation run {run_id} completed successfully")
            
            # Fire completion event
            await self._fire_event({
                "type": "evaluation_completed",
                "run_id": run_id,
                "scenario_id": scenario_id,
                "status": "success",
                "metrics": evaluation_run.metrics,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Evaluation run {run_id} failed: {e}")
            
            evaluation_run.status = EvaluationStatus.FAILED
            evaluation_run.error_message = str(e)
            evaluation_run.end_time = datetime.now()
            
            # Move to completed runs
            self.completed_runs[run_id] = evaluation_run
            if run_id in self.active_runs:
                del self.active_runs[run_id]
            
            # Fire failure event
            await self._fire_event({
                "type": "evaluation_failed",
                "run_id": run_id,
                "scenario_id": scenario_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        
        return run_id
    
    async def _simulate_scenario_execution(self, evaluation_run: EvaluationRun, 
                                         scenario: EvaluationScenario):
        """Simulate scenario execution for testing purposes."""
        
        logger.info(f"Simulating execution of scenario {scenario.id}")
        
        # Simulate some work
        await asyncio.sleep(2)  # 2 seconds simulation
        
        # Generate simulated results
        evaluation_run.results = {
            "detections_triggered": len(scenario.steps),
            "alerts_generated": scenario.expected_alerts or len(scenario.steps),
            "false_positives": 1,
            "execution_time_seconds": 2,
            "coverage_percentage": 85.0,
            "steps_completed": scenario.steps,
            "datasets_processed": scenario.datasets
        }
    
    async def run_suite(self, suite_id: str, 
                       configuration: Dict[str, Any] = None) -> List[str]:
        """Run an evaluation suite (collection of scenarios)."""
        
        if suite_id not in self.suites:
            raise ValueError(f"Unknown suite: {suite_id}")
        
        suite = self.suites[suite_id]
        run_ids = []
        
        logger.info(f"Starting evaluation suite {suite_id} with {len(suite.scenarios)} scenarios")
        
        try:
            if suite.parallel_execution:
                # Run scenarios in parallel
                tasks = []
                for scenario_id in suite.scenarios:
                    if scenario_id in self.scenarios:
                        task = self.run_scenario(scenario_id, configuration)
                        tasks.append(task)
                
                if tasks:
                    run_ids = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Filter out exceptions
                    run_ids = [rid for rid in run_ids if isinstance(rid, str)]
            else:
                # Run scenarios sequentially
                for scenario_id in suite.scenarios:
                    if scenario_id in self.scenarios:
                        try:
                            run_id = await self.run_scenario(scenario_id, configuration)
                            run_ids.append(run_id)
                        except Exception as e:
                            logger.error(f"Failed to run scenario {scenario_id} in suite {suite_id}: {e}")
                            if not suite.retry_failed:
                                break
            
            logger.info(f"Evaluation suite {suite_id} completed with {len(run_ids)} successful runs")
            
        except Exception as e:
            logger.error(f"Evaluation suite {suite_id} failed: {e}")
        
        return run_ids
    
    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running evaluation."""
        
        if run_id not in self.active_runs:
            return False
        
        evaluation_run = self.active_runs[run_id]
        evaluation_run.status = EvaluationStatus.CANCELLED
        evaluation_run.end_time = datetime.now()
        
        # Move to completed runs
        self.completed_runs[run_id] = evaluation_run
        del self.active_runs[run_id]
        
        logger.info(f"Cancelled evaluation run {run_id}")
        
        # Fire cancellation event
        await self._fire_event({
            "type": "evaluation_cancelled",
            "run_id": run_id,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an evaluation run."""
        
        # Check active runs first
        if run_id in self.active_runs:
            run = self.active_runs[run_id]
        elif run_id in self.completed_runs:
            run = self.completed_runs[run_id]
        else:
            return None
        
        status = {
            "run_id": run_id,
            "scenario_id": run.scenario_id,
            "status": run.status.value,
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat() if run.end_time else None,
            "configuration": run.configuration,
            "results": run.results,
            "metrics": run.metrics,
            "error_message": run.error_message
        }
        
        return status
    
    def list_scenarios(self, tags: List[str] = None) -> List[Dict[str, Any]]:
        """List available scenarios, optionally filtered by tags."""
        
        scenarios = []
        
        for scenario in self.scenarios.values():
            # Filter by tags if specified
            if tags and not any(tag in scenario.tags for tag in tags):
                continue
            
            scenario_info = {
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "type": scenario.scenario_type.value,
                "duration_minutes": scenario.duration_minutes,
                "hosts": len(scenario.hosts),
                "steps": len(scenario.steps),
                "tags": scenario.tags
            }
            scenarios.append(scenario_info)
        
        return scenarios
    
    def list_suites(self) -> List[Dict[str, Any]]:
        """List available evaluation suites."""
        
        suites = []
        
        for suite in self.suites.values():
            suite_info = {
                "suite_id": suite.suite_id,
                "name": suite.name,
                "description": suite.description,
                "scenarios": len(suite.scenarios),
                "parallel_execution": suite.parallel_execution,
                "timeout_minutes": suite.timeout_minutes,
                "tags": suite.tags
            }
            suites.append(suite_info)
        
        return suites
    
    def list_active_runs(self) -> List[str]:
        """List currently running evaluations."""
        return list(self.active_runs.keys())
    
    def list_completed_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List completed evaluation runs."""
        
        runs = []
        
        # Sort by completion time (most recent first)
        sorted_runs = sorted(
            self.completed_runs.values(),
            key=lambda x: x.end_time or datetime.min,
            reverse=True
        )
        
        for run in sorted_runs[:limit]:
            run_info = {
                "run_id": run.run_id,
                "scenario_id": run.scenario_id,
                "status": run.status.value,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "duration_seconds": (run.end_time - run.start_time).total_seconds() if run.end_time else None,
                "metrics": run.metrics
            }
            runs.append(run_info)
        
        return runs
    
    def add_event_handler(self, handler: Callable):
        """Add an event handler for evaluation events."""
        self.event_handlers.append(handler)
    
    async def _fire_event(self, event_data: Dict[str, Any]):
        """Fire an evaluation event to all handlers."""
        
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    def add_scenario(self, scenario: EvaluationScenario):
        """Add a new evaluation scenario."""
        self.scenarios[scenario.id] = scenario
        logger.info(f"Added scenario: {scenario.id}")
    
    def add_suite(self, suite: EvaluationSuite):
        """Add a new evaluation suite."""
        self.suites[suite.suite_id] = suite
        logger.info(f"Added suite: {suite.suite_id}")
    
    def set_components(self, scenario_runner=None, replay_engine=None, 
                      metrics_calculator=None, reporter=None):
        """Set framework components."""
        if scenario_runner:
            self.scenario_runner = scenario_runner
        if replay_engine:
            self.replay_engine = replay_engine
        if metrics_calculator:
            self.metrics_calculator = metrics_calculator
        if reporter:
            self.reporter = reporter
        
        logger.info("Framework components updated")
    
    def export_results(self, run_ids: List[str] = None, 
                      format: str = "json") -> Dict[str, Any]:
        """Export evaluation results."""
        
        if run_ids is None:
            # Export all completed runs
            runs_to_export = list(self.completed_runs.values())
        else:
            # Export specific runs
            runs_to_export = [
                self.completed_runs[rid] for rid in run_ids 
                if rid in self.completed_runs
            ]
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_runs": len(runs_to_export),
            "runs": []
        }
        
        for run in runs_to_export:
            run_data = asdict(run)
            run_data["start_time"] = run.start_time.isoformat()
            run_data["end_time"] = run.end_time.isoformat() if run.end_time else None
            run_data["status"] = run.status.value
            export_data["runs"].append(run_data)
        
        return export_data
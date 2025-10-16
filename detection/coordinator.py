"""Detection Loop Coordinator - orchestrates continuous detection improvements."""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

# Optional storage imports
try:
    from storage.clickhouse_client import ClickHouseClient
except ImportError:
    ClickHouseClient = None

try:
    from storage.neo4j_client import Neo4jClient
except ImportError:
    Neo4jClient = None
from detection.rule_deployment import SigmaRuleDeployer
from detection.feedback_loop import DetectionFeedbackLoop
from detection.performance_monitor import RulePerformanceMonitor
from detection.tuning_engine import ContinuousTuningEngine

logger = logging.getLogger(__name__)

@dataclass
class DetectionCycle:
    """Represents one detection loop cycle."""
    cycle_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    incidents_processed: int = 0
    rules_deployed: int = 0
    rules_tuned: int = 0
    performance_scores: Dict[str, float] = None
    feedback_collected: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.performance_scores is None:
            self.performance_scores = {}
        if self.errors is None:
            self.errors = []

@dataclass
class DetectionLoopConfig:
    """Configuration for the detection loop."""
    cycle_interval_minutes: int = 60  # How often to run detection cycles
    lookback_hours: int = 24  # How far back to look for new incidents
    min_confidence_threshold: float = 0.7  # Minimum confidence for rule deployment
    max_rules_per_cycle: int = 10  # Maximum new rules to deploy per cycle
    performance_window_hours: int = 168  # Week lookback for performance analysis
    tuning_enabled: bool = True
    auto_deployment_enabled: bool = False  # Require manual approval by default
    detection_engines: List[str] = None  # List of target detection engines
    
    def __post_init__(self):
        if self.detection_engines is None:
            self.detection_engines = ["elasticsearch", "splunk", "qradar"]

class DetectionLoopCoordinator:
    """Coordinates the continuous detection improvement loop."""
    
    def __init__(self, 
                 config: DetectionLoopConfig = None,
                 clickhouse_client = None,
                 neo4j_client = None):
        self.config = config or DetectionLoopConfig()
        self.clickhouse = clickhouse_client
        self.neo4j = neo4j_client
        
        # Initialize components
        self.rule_deployer = SigmaRuleDeployer()
        self.feedback_loop = DetectionFeedbackLoop(clickhouse_client)
        self.performance_monitor = RulePerformanceMonitor(clickhouse_client)
        self.tuning_engine = ContinuousTuningEngine()
        
        # State tracking
        self.running = False
        self.current_cycle: Optional[DetectionCycle] = None
        self.cycle_history: List[DetectionCycle] = []
        self.deployed_rules: Set[str] = set()  # Track deployed rule IDs
        
        logger.info(f"Detection loop coordinator initialized with {self.config.cycle_interval_minutes}min cycles")
    
    async def start_loop(self):
        """Start the continuous detection loop."""
        if self.running:
            logger.warning("Detection loop already running")
            return
        
        self.running = True
        logger.info("Starting continuous detection loop")
        
        try:
            while self.running:
                cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                try:
                    await self._run_detection_cycle(cycle_id)
                except Exception as e:
                    logger.error(f"Detection cycle {cycle_id} failed: {e}")
                    if self.current_cycle:
                        self.current_cycle.status = "failed"
                        self.current_cycle.errors.append(str(e))
                        self.current_cycle.end_time = datetime.now()
                
                # Wait for next cycle
                if self.running:
                    logger.info(f"Waiting {self.config.cycle_interval_minutes} minutes for next cycle")
                    await asyncio.sleep(self.config.cycle_interval_minutes * 60)
                    
        except asyncio.CancelledError:
            logger.info("Detection loop cancelled")
        finally:
            self.running = False
            logger.info("Detection loop stopped")
    
    async def stop_loop(self):
        """Stop the detection loop."""
        logger.info("Stopping detection loop")
        self.running = False
    
    async def _run_detection_cycle(self, cycle_id: str):
        """Run a single detection cycle."""
        logger.info(f"Starting detection cycle: {cycle_id}")
        
        cycle = DetectionCycle(
            cycle_id=cycle_id,
            start_time=datetime.now()
        )
        self.current_cycle = cycle
        
        try:
            # Step 1: Collect new incidents and generated rules
            new_incidents, new_rules = await self._collect_new_detections()
            cycle.incidents_processed = len(new_incidents)
            logger.info(f"Found {len(new_incidents)} new incidents, {len(new_rules)} new rules")
            
            # Step 2: Evaluate and deploy new rules
            if new_rules:
                deployed_count = await self._evaluate_and_deploy_rules(new_rules)
                cycle.rules_deployed = deployed_count
                logger.info(f"Deployed {deployed_count} new rules")
            
            # Step 3: Collect feedback on existing rules
            feedback_count = await self._collect_rule_feedback()
            cycle.feedback_collected = feedback_count
            logger.info(f"Collected feedback on {feedback_count} rules")
            
            # Step 4: Monitor rule performance
            performance_scores = await self._monitor_rule_performance()
            cycle.performance_scores = performance_scores
            logger.info(f"Analyzed performance of {len(performance_scores)} rules")
            
            # Step 5: Tune underperforming rules
            if self.config.tuning_enabled:
                tuned_count = await self._tune_rules(performance_scores)
                cycle.rules_tuned = tuned_count
                logger.info(f"Tuned {tuned_count} rules")
            
            # Step 6: Update knowledge graph with findings
            await self._update_knowledge_graph(new_incidents, performance_scores)
            
            cycle.status = "completed"
            cycle.end_time = datetime.now()
            
            duration = (cycle.end_time - cycle.start_time).total_seconds()
            logger.info(f"Detection cycle {cycle_id} completed in {duration:.1f}s")
            
        except Exception as e:
            cycle.status = "failed"
            cycle.errors.append(str(e))
            cycle.end_time = datetime.now()
            logger.error(f"Detection cycle {cycle_id} failed: {e}")
            raise
        finally:
            self.cycle_history.append(cycle)
            self.current_cycle = None
            
            # Keep only last 100 cycles
            if len(self.cycle_history) > 100:
                self.cycle_history = self.cycle_history[-100:]
    
    async def _collect_new_detections(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Collect new incidents and Sigma rules from recent analysis."""
        
        # Time window for collecting new data
        lookback_time = datetime.now() - timedelta(hours=self.config.lookback_hours)
        
        new_incidents = []
        new_rules = []
        
        if self.clickhouse:
            try:
                # Query for recent incidents with generated Sigma rules
                incident_query = """
                SELECT 
                    incident_id,
                    analyst_findings,
                    responder_plan,
                    timestamp,
                    severity
                FROM incidents 
                WHERE timestamp >= %(lookback_time)s
                AND JSONExtractString(analyst_findings, 'sigma_rules') != '[]'
                ORDER BY timestamp DESC
                """
                
                incidents_result = await self.clickhouse.query(
                    incident_query, 
                    {"lookback_time": lookback_time}
                )
                
                for row in incidents_result:
                    incident_data = {
                        "incident_id": row["incident_id"],
                        "analyst_findings": json.loads(row["analyst_findings"]) if row["analyst_findings"] else {},
                        "responder_plan": json.loads(row["responder_plan"]) if row["responder_plan"] else {},
                        "timestamp": row["timestamp"],
                        "severity": row["severity"]
                    }
                    
                    new_incidents.append(incident_data)
                    
                    # Extract Sigma rules from analyst findings
                    analyst_findings = incident_data["analyst_findings"]
                    sigma_rules = analyst_findings.get("sigma_rules", [])
                    
                    for rule in sigma_rules:
                        if rule.get("validation", {}).get("valid", False):
                            rule["source_incident"] = incident_data["incident_id"]
                            rule["generated_at"] = incident_data["timestamp"]
                            rule["incident_severity"] = incident_data["severity"]
                            new_rules.append(rule)
                
                logger.info(f"Collected {len(new_incidents)} incidents with {len(new_rules)} Sigma rules")
                
            except Exception as e:
                logger.error(f"Failed to collect new detections from ClickHouse: {e}")
        
        return new_incidents, new_rules
    
    async def _evaluate_and_deploy_rules(self, new_rules: List[Dict[str, Any]]) -> int:
        """Evaluate new rules and deploy high-quality ones."""
        
        if not new_rules:
            return 0
        
        deployed_count = 0
        deployment_candidates = []
        
        # Filter rules by quality and confidence
        for rule in new_rules:
            rule_id = rule.get("rule_id")
            
            # Skip if already deployed
            if rule_id in self.deployed_rules:
                continue
            
            # Check validation status
            validation = rule.get("validation", {})
            if not validation.get("valid", False):
                logger.debug(f"Skipping invalid rule {rule_id}")
                continue
            
            # Check incident severity/confidence
            incident_severity = rule.get("incident_severity", "medium")
            if incident_severity in ["high", "critical"]:
                deployment_candidates.append(rule)
            
        # Limit deployments per cycle
        deployment_candidates = deployment_candidates[:self.config.max_rules_per_cycle]
        
        # Deploy rules
        for rule in deployment_candidates:
            try:
                success = await self.rule_deployer.deploy_rule(
                    rule, 
                    engines=self.config.detection_engines,
                    auto_deploy=self.config.auto_deployment_enabled
                )
                
                if success:
                    deployed_count += 1
                    self.deployed_rules.add(rule["rule_id"])
                    logger.info(f"Deployed rule {rule['rule_id']}: {rule.get('title', 'Unknown')}")
                
            except Exception as e:
                logger.error(f"Failed to deploy rule {rule.get('rule_id')}: {e}")
        
        return deployed_count
    
    async def _collect_rule_feedback(self) -> int:
        """Collect feedback on deployed rules."""
        
        try:
            feedback_count = await self.feedback_loop.collect_feedback(
                rule_ids=list(self.deployed_rules),
                lookback_hours=self.config.performance_window_hours
            )
            return feedback_count
        except Exception as e:
            logger.error(f"Failed to collect rule feedback: {e}")
            return 0
    
    async def _monitor_rule_performance(self) -> Dict[str, float]:
        """Monitor performance of deployed rules."""
        
        try:
            performance_scores = await self.performance_monitor.analyze_rule_performance(
                rule_ids=list(self.deployed_rules),
                window_hours=self.config.performance_window_hours
            )
            return performance_scores
        except Exception as e:
            logger.error(f"Failed to monitor rule performance: {e}")
            return {}
    
    async def _tune_rules(self, performance_scores: Dict[str, float]) -> int:
        """Tune underperforming rules."""
        
        if not performance_scores:
            return 0
        
        try:
            tuned_count = await self.tuning_engine.tune_rules(
                performance_scores,
                deployed_rules=self.deployed_rules
            )
            return tuned_count
        except Exception as e:
            logger.error(f"Failed to tune rules: {e}")
            return 0
    
    async def _update_knowledge_graph(self, 
                                    new_incidents: List[Dict[str, Any]], 
                                    performance_scores: Dict[str, float]):
        """Update knowledge graph with detection insights."""
        
        if not self.neo4j:
            return
        
        try:
            # Update detection effectiveness relationships
            for incident in new_incidents:
                incident_id = incident["incident_id"]
                
                # Create detection cycle relationship
                await self.neo4j.run_query("""
                MATCH (i:Incident {id: $incident_id})
                CREATE (dc:DetectionCycle {
                    id: $cycle_id,
                    timestamp: datetime(),
                    rules_generated: $rules_count
                })
                CREATE (i)-[:ANALYZED_IN]->(dc)
                """, {
                    "incident_id": incident_id,
                    "cycle_id": self.current_cycle.cycle_id if self.current_cycle else "unknown",
                    "rules_count": len(incident.get("analyst_findings", {}).get("sigma_rules", []))
                })
            
            # Update rule performance relationships
            for rule_id, score in performance_scores.items():
                await self.neo4j.run_query("""
                MERGE (r:SigmaRule {id: $rule_id})
                SET r.performance_score = $score,
                    r.last_evaluated = datetime()
                """, {
                    "rule_id": rule_id,
                    "score": score
                })
            
            logger.debug(f"Updated knowledge graph with {len(new_incidents)} incidents and {len(performance_scores)} rule scores")
            
        except Exception as e:
            logger.error(f"Failed to update knowledge graph: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the detection loop."""
        
        status = {
            "running": self.running,
            "current_cycle": asdict(self.current_cycle) if self.current_cycle else None,
            "total_cycles": len(self.cycle_history),
            "deployed_rules_count": len(self.deployed_rules),
            "config": asdict(self.config)
        }
        
        # Recent performance
        if self.cycle_history:
            recent_cycles = self.cycle_history[-5:]
            status["recent_performance"] = {
                "avg_incidents_per_cycle": sum(c.incidents_processed for c in recent_cycles) / len(recent_cycles),
                "avg_rules_deployed_per_cycle": sum(c.rules_deployed for c in recent_cycles) / len(recent_cycles),
                "success_rate": len([c for c in recent_cycles if c.status == "completed"]) / len(recent_cycles)
            }
        
        return status
    
    def get_cycle_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent cycle history."""
        recent_cycles = self.cycle_history[-limit:] if limit else self.cycle_history
        return [asdict(cycle) for cycle in recent_cycles]
    
    async def run_single_cycle(self) -> DetectionCycle:
        """Run a single detection cycle (for testing/manual execution)."""
        cycle_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        await self._run_detection_cycle(cycle_id)
        return self.cycle_history[-1] if self.cycle_history else None

# Helper function for CLI usage
async def run_detection_loop(config_path: Optional[Path] = None):
    """Run the detection loop with optional config file."""
    
    config = DetectionLoopConfig()
    if config_path and config_path.exists():
        with open(config_path) as f:
            config_data = json.load(f)
        
        # Update config with file values
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    # Initialize storage clients (if available)
    clickhouse_client = None
    neo4j_client = None
    
    try:
        clickhouse_client = ClickHouseClient()
        logger.info("ClickHouse client initialized")
    except Exception as e:
        logger.warning(f"ClickHouse not available: {e}")
    
    try:
        neo4j_client = Neo4jClient()
        logger.info("Neo4j client initialized")
    except Exception as e:
        logger.warning(f"Neo4j not available: {e}")
    
    # Start detection loop
    coordinator = DetectionLoopCoordinator(
        config=config,
        clickhouse_client=clickhouse_client,
        neo4j_client=neo4j_client
    )
    
    try:
        await coordinator.start_loop()
    except KeyboardInterrupt:
        logger.info("Detection loop interrupted by user")
        await coordinator.stop_loop()
"""Campaign Orchestrator - manages end-to-end execution of red team campaigns."""

import asyncio
import logging
import json
import uuid
import random
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from .framework import (
    RedTeamSimulator, CampaignConfiguration, CampaignState, CampaignStatus, 
    CampaignPhase, SimulationMode
)
from .campaign_generator import ATTACKCampaignGenerator, CampaignTemplate
from .telemetry_simulator import TelemetrySimulator, TelemetryEvent
from .adversary_engine import AdversaryBehaviorEngine, TechniqueDecision

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    """Status of technique execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class TechniqueExecution:
    """Details of a technique execution."""
    execution_id: str
    technique_id: str
    campaign_id: str
    phase: CampaignPhase
    start_time: datetime
    end_time: Optional[datetime] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    success: bool = False
    detected: bool = False
    stealth_level: float = 0.5
    telemetry_events: List[str] = None  # Event IDs
    error_message: Optional[str] = None
    impact_score: float = 0.0
    
    def __post_init__(self):
        if self.telemetry_events is None:
            self.telemetry_events = []

@dataclass
class CampaignExecution:
    """Overall execution details for a campaign."""
    campaign_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    current_phase: CampaignPhase = CampaignPhase.RECONNAISSANCE
    techniques_executed: List[TechniqueExecution] = None
    objectives_completed: List[str] = None
    total_telemetry_events: int = 0
    total_alerts_triggered: int = 0
    total_detections: int = 0
    overall_success_rate: float = 0.0
    stealth_effectiveness: float = 0.0
    
    def __post_init__(self):
        if self.techniques_executed is None:
            self.techniques_executed = []
        if self.objectives_completed is None:
            self.objectives_completed = []

class CampaignOrchestrator:
    """Orchestrates complete red team campaign execution."""
    
    def __init__(self, simulator: RedTeamSimulator):
        self.simulator = simulator
        self.campaign_generator = ATTACKCampaignGenerator()
        self.telemetry_simulator = TelemetrySimulator()
        
        # Active campaigns and their components
        self.active_campaigns: Dict[str, CampaignExecution] = {}
        self.behavior_engines: Dict[str, AdversaryBehaviorEngine] = {}
        
        # Execution control
        self.execution_tasks: Dict[str, asyncio.Task] = {}
        self.event_handlers: List[Callable] = []
        
        # Performance tracking
        self.execution_metrics: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Campaign orchestrator initialized")
    
    async def start_campaign(self, campaign_id: str, 
                           real_time: bool = True,
                           speed_multiplier: float = 1.0) -> bool:
        """Start executing a campaign."""
        
        if campaign_id not in self.simulator.campaign_configs:
            logger.error(f"Campaign {campaign_id} not found")
            return False
        
        if campaign_id in self.active_campaigns:
            logger.warning(f"Campaign {campaign_id} is already running")
            return False
        
        config = self.simulator.campaign_configs[campaign_id]
        
        # Initialize campaign execution
        execution = CampaignExecution(
            campaign_id=campaign_id,
            start_time=datetime.now()
        )
        self.active_campaigns[campaign_id] = execution
        
        # Generate campaign plan
        campaign_plan = await self._generate_campaign_plan(config)
        if not campaign_plan:
            logger.error(f"Failed to generate plan for campaign {campaign_id}")
            return False
        
        # Initialize behavior engine
        behavior_engine = AdversaryBehaviorEngine(
            adversary_profile=config.adversary_profile,
            target_environment=config.target_environment,
            available_techniques=self.campaign_generator.techniques
        )
        self.behavior_engines[campaign_id] = behavior_engine
        
        # Start campaign execution task
        if real_time:
            execution_task = asyncio.create_task(
                self._execute_campaign_realtime(campaign_id, campaign_plan, speed_multiplier)
            )
        else:
            execution_task = asyncio.create_task(
                self._execute_campaign_batch(campaign_id, campaign_plan)
            )
        
        self.execution_tasks[campaign_id] = execution_task
        
        # Update simulator state
        await self.simulator.start_campaign(campaign_id)
        
        logger.info(f"Started campaign {campaign_id} execution")
        return True
    
    async def _generate_campaign_plan(self, config: CampaignConfiguration) -> Optional[Dict[str, Any]]:
        """Generate a detailed campaign plan."""
        
        try:
            # Generate campaign using the campaign generator
            campaign_plan = self.campaign_generator.generate_campaign(
                adversary_profile=config.adversary_profile,
                target_environment=config.target_environment,
                objectives=config.objectives,
                duration_hours=config.duration.total_seconds() / 3600,
                stealth_requirement=config.detection_avoidance
            )
            
            phases = campaign_plan.get("phases", [])
            sequences = campaign_plan.get("technique_sequences", {})
            logger.info(f"Generated campaign plan with {len(phases)} phases and {len(sequences)} technique sequences")
            return campaign_plan
            
        except Exception as e:
            logger.error(f"Failed to generate campaign plan: {e}")
            return None
    
    async def _execute_campaign_realtime(self, campaign_id: str, 
                                       campaign_plan: Dict[str, Any],
                                       speed_multiplier: float):
        """Execute campaign in real-time mode."""
        
        execution = self.active_campaigns[campaign_id]
        behavior_engine = self.behavior_engines[campaign_id]
        
        try:
            phases = campaign_plan.get("phases", [])
            technique_sequences = campaign_plan.get("technique_sequences", {})
            
            for phase_data in phases:
                phase_name = phase_data.get("name", "unknown")
                execution.current_phase = CampaignPhase(phase_name.lower().replace(" ", "_"))
                
                logger.info(f"Campaign {campaign_id} entering phase: {phase_name}")
                
                # Get techniques for this phase
                phase_techniques = phase_data.get("techniques", [])
                
                for technique_id in phase_techniques:
                    # Check if campaign is still active
                    if campaign_id not in self.active_campaigns:
                        logger.info(f"Campaign {campaign_id} was stopped")
                        return
                    
                    # Let behavior engine decide on technique execution
                    decision = await behavior_engine.select_next_technique(
                        current_phase=execution.current_phase,
                        available_techniques=[technique_id],
                        campaign_context=self._get_campaign_context(campaign_id)
                    )
                    
                    if decision:
                        # Wait for execution delay
                        if decision.execution_delay:
                            await asyncio.sleep(decision.execution_delay.total_seconds() / speed_multiplier)
                        
                        # Execute the technique
                        await self._execute_technique(campaign_id, decision, None)
                
                # Small delay between phases
                await asyncio.sleep(10 / speed_multiplier)  # 10 seconds between phases
            
            # Campaign completed
            await self._complete_campaign(campaign_id)
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign_id}: {e}")
            await self._fail_campaign(campaign_id, str(e))
    
    async def _execute_campaign_batch(self, campaign_id: str, campaign_plan: Dict[str, Any]):
        """Execute campaign in batch mode (no time delays)."""
        
        execution = self.active_campaigns[campaign_id]
        behavior_engine = self.behavior_engines[campaign_id]
        
        try:
            phases = campaign_plan.get("phases", [])
            
            for phase_data in phases:
                phase_name = phase_data.get("name", "unknown")
                execution.current_phase = CampaignPhase(phase_name.lower().replace(" ", "_"))
                
                logger.info(f"Campaign {campaign_id} executing phase: {phase_name}")
                
                # Get techniques for this phase
                phase_techniques = phase_data.get("techniques", [])
                
                for technique_id in phase_techniques:
                    # Check if campaign is still active
                    if campaign_id not in self.active_campaigns:
                        return
                    
                    # Get behavior engine decision
                    decision = await behavior_engine.select_next_technique(
                        current_phase=execution.current_phase,
                        available_techniques=[technique_id],
                        campaign_context=self._get_campaign_context(campaign_id)
                    )
                    
                    if decision:
                        await self._execute_technique(campaign_id, decision, None)
            
            # Campaign completed
            await self._complete_campaign(campaign_id)
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign_id}: {e}")
            await self._fail_campaign(campaign_id, str(e))
    
    async def _execute_technique(self, campaign_id: str, decision: TechniqueDecision, technique_step):
        """Execute a single technique."""
        
        execution = self.active_campaigns[campaign_id]
        behavior_engine = self.behavior_engines[campaign_id]
        
        # Create technique execution record
        tech_execution = TechniqueExecution(
            execution_id=str(uuid.uuid4()),
            technique_id=decision.technique_id,
            campaign_id=campaign_id,
            phase=execution.current_phase,
            start_time=datetime.now(),
            status=ExecutionStatus.EXECUTING,
            stealth_level=decision.stealth_level
        )
        
        execution.techniques_executed.append(tech_execution)
        
        try:
            logger.info(f"Executing technique {decision.technique_id} for campaign {campaign_id}")
            
            # Simulate technique execution
            success, detected, impact = await self._simulate_technique_execution(
                technique_id=decision.technique_id,
                stealth_level=decision.stealth_level,
                campaign_id=campaign_id
            )
            
            # Update execution record
            tech_execution.end_time = datetime.now()
            tech_execution.status = ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED
            tech_execution.success = success
            tech_execution.detected = detected
            tech_execution.impact_score = impact
            
            # Generate telemetry events
            telemetry_events = await self.telemetry_simulator.generate_technique_telemetry(
                technique_id=decision.technique_id,
                duration_minutes=60,  # 1 hour of telemetry
                stealth_level=decision.stealth_level
            )
            
            # Store event IDs
            tech_execution.telemetry_events = [event.event_id for event in telemetry_events]
            execution.total_telemetry_events += len(telemetry_events)
            
            if detected:
                execution.total_detections += 1
                execution.total_alerts_triggered += 1
            
            # Notify behavior engine of result
            await behavior_engine.process_technique_result(
                technique_id=decision.technique_id,
                success=success,
                detected=detected,
                impact=impact
            )
            
            # Fire event handlers
            await self._fire_technique_completed_event(campaign_id, tech_execution, telemetry_events)
            
            logger.info(f"Technique {decision.technique_id} completed: success={success}, detected={detected}, impact={impact:.2f}")
            
        except Exception as e:
            tech_execution.status = ExecutionStatus.FAILED
            tech_execution.error_message = str(e)
            tech_execution.end_time = datetime.now()
            
            logger.error(f"Technique {decision.technique_id} failed: {e}")
    
    async def _simulate_technique_execution(self, technique_id: str, stealth_level: float, 
                                          campaign_id: str) -> tuple[bool, bool, float]:
        """Simulate the execution of a technique and return (success, detected, impact)."""
        
        # Get technique details
        technique = self.campaign_generator.techniques.get(technique_id)
        if not technique:
            return False, False, 0.0
        
        # Get campaign configuration for environment context
        config = self.simulator.campaign_configs[campaign_id]
        environment = config.target_environment
        
        # Calculate success probability
        base_success_rate = 0.7  # Base 70% success rate
        
        # Adjust for technique difficulty
        success_rate = base_success_rate * (1.0 - technique.difficulty * 0.3)
        
        # Adjust for environment security
        security_levels = {"basic": 0.8, "intermediate": 0.6, "advanced": 0.4, "expert": 0.2}
        env_resistance = security_levels.get(environment.security_maturity, 0.6)
        success_rate *= (1.0 + env_resistance)
        
        # Random success determination
        success = random.random() < success_rate
        
        # Calculate detection probability
        base_detection_rate = 1.0 - technique.stealth_rating
        
        # Adjust for stealth level
        detection_rate = base_detection_rate * (1.0 - stealth_level * 0.6)
        
        # Adjust for environment detection capability
        security_multiplier = {"basic": 0.3, "intermediate": 0.6, "advanced": 0.9, "expert": 1.2}
        detection_multiplier = security_multiplier.get(environment.security_maturity, 0.6)
        detection_rate *= detection_multiplier
        
        # Random detection determination
        detected = random.random() < detection_rate
        
        # Calculate impact
        impact = technique.impact_rating * (1.0 if success else 0.0)
        
        return success, detected, impact
    
    def _get_campaign_context(self, campaign_id: str) -> Dict[str, Any]:
        """Get current campaign context for behavior engine."""
        
        execution = self.active_campaigns.get(campaign_id)
        if not execution:
            return {}
        
        # Calculate campaign metrics
        total_techniques = len(execution.techniques_executed)
        successful_techniques = sum(1 for t in execution.techniques_executed if t.success)
        
        success_rate = successful_techniques / max(total_techniques, 1)
        detection_rate = execution.total_detections / max(total_techniques, 1)
        
        campaign_duration = datetime.now() - execution.start_time
        campaign_duration_hours = campaign_duration.total_seconds() / 3600
        
        # Calculate progress based on techniques executed vs planned
        config = self.simulator.campaign_configs[campaign_id]
        planned_duration = config.duration.total_seconds() / 3600
        progress = min(1.0, campaign_duration_hours / planned_duration)
        
        return {
            "campaign_duration_hours": campaign_duration_hours,
            "campaign_progress": progress,
            "recent_success_rate": success_rate,
            "recent_detection_rate": detection_rate,
            "recent_detections": execution.total_detections,
            "last_technique_success": execution.techniques_executed[-1].success if execution.techniques_executed else False,
            "last_technique_failure": not execution.techniques_executed[-1].success if execution.techniques_executed else False,
            "campaign_start": total_techniques == 0
        }
    
    async def _complete_campaign(self, campaign_id: str):
        """Mark campaign as completed."""
        
        execution = self.active_campaigns[campaign_id]
        execution.end_time = datetime.now()
        
        # Calculate final metrics
        total_techniques = len(execution.techniques_executed)
        successful_techniques = sum(1 for t in execution.techniques_executed if t.success)
        
        execution.overall_success_rate = successful_techniques / max(total_techniques, 1)
        
        # Calculate stealth effectiveness
        undetected_techniques = sum(1 for t in execution.techniques_executed if not t.detected)
        execution.stealth_effectiveness = undetected_techniques / max(total_techniques, 1)
        
        # Update simulator state
        simulator_state = self.simulator.active_campaigns[campaign_id]
        simulator_state.status = CampaignStatus.COMPLETED
        simulator_state.end_time = execution.end_time
        simulator_state.techniques_executed = [t.technique_id for t in execution.techniques_executed]
        simulator_state.telemetry_generated = execution.total_telemetry_events
        simulator_state.alerts_triggered = execution.total_alerts_triggered
        
        logger.info(f"Campaign {campaign_id} completed with {execution.overall_success_rate:.1%} success rate")
        
        # Fire completion event
        await self._fire_campaign_completed_event(campaign_id)
    
    async def _fail_campaign(self, campaign_id: str, error_message: str):
        """Mark campaign as failed."""
        
        execution = self.active_campaigns[campaign_id]
        execution.end_time = datetime.now()
        
        # Update simulator state
        simulator_state = self.simulator.active_campaigns[campaign_id]
        simulator_state.status = CampaignStatus.FAILED
        simulator_state.end_time = execution.end_time
        
        logger.error(f"Campaign {campaign_id} failed: {error_message}")
        
        # Fire failure event
        await self._fire_campaign_failed_event(campaign_id, error_message)
    
    async def stop_campaign(self, campaign_id: str) -> bool:
        """Stop a running campaign."""
        
        if campaign_id not in self.active_campaigns:
            return False
        
        # Cancel execution task
        if campaign_id in self.execution_tasks:
            self.execution_tasks[campaign_id].cancel()
            del self.execution_tasks[campaign_id]
        
        # Clean up resources
        if campaign_id in self.behavior_engines:
            del self.behavior_engines[campaign_id]
        
        # Update state
        execution = self.active_campaigns[campaign_id]
        execution.end_time = datetime.now()
        
        await self.simulator.stop_campaign(campaign_id)
        
        del self.active_campaigns[campaign_id]
        
        logger.info(f"Stopped campaign {campaign_id}")
        return True
    
    async def pause_campaign(self, campaign_id: str) -> bool:
        """Pause a running campaign."""
        
        if campaign_id not in self.active_campaigns:
            return False
        
        # Cancel current execution task
        if campaign_id in self.execution_tasks:
            self.execution_tasks[campaign_id].cancel()
        
        await self.simulator.pause_campaign(campaign_id)
        
        logger.info(f"Paused campaign {campaign_id}")
        return True
    
    def get_campaign_execution_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed execution status for a campaign."""
        
        if campaign_id not in self.active_campaigns:
            return None
        
        execution = self.active_campaigns[campaign_id]
        behavior_engine = self.behavior_engines.get(campaign_id)
        
        # Calculate metrics
        total_techniques = len(execution.techniques_executed)
        successful_techniques = sum(1 for t in execution.techniques_executed if t.success)
        detected_techniques = sum(1 for t in execution.techniques_executed if t.detected)
        
        status = {
            "campaign_id": campaign_id,
            "start_time": execution.start_time.isoformat(),
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "current_phase": execution.current_phase.value,
            "techniques_executed": total_techniques,
            "techniques_successful": successful_techniques,
            "techniques_detected": detected_techniques,
            "success_rate": successful_techniques / max(total_techniques, 1),
            "detection_rate": detected_techniques / max(total_techniques, 1),
            "stealth_effectiveness": execution.stealth_effectiveness,
            "total_telemetry_events": execution.total_telemetry_events,
            "total_alerts_triggered": execution.total_alerts_triggered,
            "objectives_completed": len(execution.objectives_completed),
            "adversary_status": behavior_engine.get_adversary_status() if behavior_engine else None
        }
        
        return status
    
    def list_active_campaigns(self) -> List[str]:
        """List all active campaign IDs."""
        return list(self.active_campaigns.keys())
    
    def add_event_handler(self, handler: Callable):
        """Add an event handler for campaign events."""
        self.event_handlers.append(handler)
    
    async def _fire_technique_completed_event(self, campaign_id: str, 
                                            technique_execution: TechniqueExecution,
                                            telemetry_events: List[TelemetryEvent]):
        """Fire event when technique completes."""
        
        event_data = {
            "type": "technique_completed",
            "campaign_id": campaign_id,
            "technique_execution": asdict(technique_execution),
            "telemetry_events": [asdict(event) for event in telemetry_events]
        }
        
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    async def _fire_campaign_completed_event(self, campaign_id: str):
        """Fire event when campaign completes."""
        
        event_data = {
            "type": "campaign_completed",
            "campaign_id": campaign_id,
            "execution_summary": self.get_campaign_execution_status(campaign_id)
        }
        
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    async def _fire_campaign_failed_event(self, campaign_id: str, error_message: str):
        """Fire event when campaign fails."""
        
        event_data = {
            "type": "campaign_failed",
            "campaign_id": campaign_id,
            "error_message": error_message,
            "execution_summary": self.get_campaign_execution_status(campaign_id)
        }
        
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    def export_campaign_report(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Export comprehensive campaign report."""
        
        if campaign_id not in self.active_campaigns:
            return None
        
        execution = self.active_campaigns[campaign_id]
        config = self.simulator.campaign_configs[campaign_id]
        behavior_engine = self.behavior_engines.get(campaign_id)
        
        # Collect all telemetry events
        all_telemetry = []
        for tech_exec in execution.techniques_executed:
            # Would need to retrieve actual telemetry events by ID
            # For now, just include event IDs
            all_telemetry.extend(tech_exec.telemetry_events)
        
        report = {
            "campaign_info": {
                "campaign_id": campaign_id,
                "name": config.name,
                "adversary_profile": config.adversary_profile.name,
                "target_environment": config.target_environment.name,
                "start_time": execution.start_time.isoformat(),
                "end_time": execution.end_time.isoformat() if execution.end_time else None,
                "duration_planned": str(config.duration),
                "duration_actual": str(execution.end_time - execution.start_time) if execution.end_time else None
            },
            "execution_summary": {
                "phases_completed": list(set(t.phase.value for t in execution.techniques_executed)),
                "techniques_executed": len(execution.techniques_executed),
                "techniques_successful": sum(1 for t in execution.techniques_executed if t.success),
                "techniques_detected": sum(1 for t in execution.techniques_executed if t.detected),
                "success_rate": execution.overall_success_rate,
                "stealth_effectiveness": execution.stealth_effectiveness,
                "objectives_completed": execution.objectives_completed
            },
            "technique_details": [asdict(t) for t in execution.techniques_executed],
            "telemetry_summary": {
                "total_events": execution.total_telemetry_events,
                "alerts_triggered": execution.total_alerts_triggered,
                "detection_opportunities": len([t for t in execution.techniques_executed if t.detected])
            },
            "adversary_behavior": behavior_engine.export_behavior_log() if behavior_engine else [],
            "lessons_learned": self._generate_lessons_learned(execution),
            "recommendations": self._generate_recommendations(execution)
        }
        
        return report
    
    def _generate_lessons_learned(self, execution: CampaignExecution) -> List[str]:
        """Generate lessons learned from campaign execution."""
        
        lessons = []
        
        # Success rate analysis
        if execution.overall_success_rate > 0.8:
            lessons.append("High technique success rate indicates environment may be under-protected")
        elif execution.overall_success_rate < 0.3:
            lessons.append("Low success rate suggests strong defensive posture or skilled adversary required")
        
        # Detection analysis
        if execution.stealth_effectiveness > 0.8:
            lessons.append("High stealth effectiveness indicates detection capabilities may need improvement")
        elif execution.stealth_effectiveness < 0.3:
            lessons.append("Low stealth effectiveness shows good detection coverage")
        
        # Phase analysis
        phases_attempted = set(t.phase.value for t in execution.techniques_executed)
        if CampaignPhase.INITIAL_ACCESS.value not in phases_attempted:
            lessons.append("Campaign did not achieve initial access - perimeter defenses effective")
        
        return lessons
    
    def _generate_recommendations(self, execution: CampaignExecution) -> List[str]:
        """Generate recommendations based on campaign results."""
        
        recommendations = []
        
        # Detection improvements
        undetected_techniques = [t for t in execution.techniques_executed if t.success and not t.detected]
        if undetected_techniques:
            techniques = set(t.technique_id for t in undetected_techniques)
            recommendations.append(f"Improve detection for techniques: {', '.join(techniques)}")
        
        # High-impact techniques
        high_impact_techniques = [t for t in execution.techniques_executed if t.impact_score > 0.7]
        if high_impact_techniques:
            recommendations.append("Focus protection on high-impact attack vectors")
        
        # Common failure points
        failed_techniques = [t for t in execution.techniques_executed if not t.success]
        if len(failed_techniques) > len(execution.techniques_executed) * 0.5:
            recommendations.append("Current defenses are effective - maintain security posture")
        
        return recommendations
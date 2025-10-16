"""Adversary Behavior Engine - simulates realistic adversary decision-making and behavior patterns."""

import asyncio
import logging
import json
import random
import math
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from .framework import AdversaryProfile, TargetEnvironment, CampaignPhase, CampaignState
from .campaign_generator import ATTACKTechnique

logger = logging.getLogger(__name__)

class AdversaryMood(Enum):
    """Current mood/state of the adversary affecting decision making."""
    CAUTIOUS = "cautious"
    AGGRESSIVE = "aggressive"
    OPPORTUNISTIC = "opportunistic"
    DESPERATE = "desperate"
    METHODICAL = "methodical"

class DecisionFactor(Enum):
    """Factors that influence adversary decisions."""
    DETECTION_RISK = "detection_risk"
    OPERATIONAL_SECURITY = "operational_security"
    TIME_PRESSURE = "time_pressure"
    RESOURCE_AVAILABILITY = "resource_availability"
    TARGET_VALUE = "target_value"
    SUCCESS_PROBABILITY = "success_probability"

@dataclass
class AdversaryState:
    """Current state of the adversary during campaign execution."""
    current_position: Dict[str, Any]  # Current network position, access, etc.
    compromised_assets: List[str]
    acquired_credentials: List[Dict[str, Any]]
    discovered_assets: List[str]
    failed_attempts: List[str]  # Failed technique attempts
    detection_events: List[str]  # Times when adversary was detected
    mood: AdversaryMood
    fatigue_level: float  # 0.0 to 1.0, affects performance
    paranoia_level: float  # 0.0 to 1.0, affects risk tolerance
    confidence_level: float  # 0.0 to 1.0, affects boldness
    time_pressure: float  # 0.0 to 1.0, affects decision making
    
@dataclass
class TechniqueDecision:
    """Decision to execute a specific technique."""
    technique_id: str
    confidence: float  # How confident adversary is in this choice
    risk_assessment: float  # Perceived risk of detection
    expected_value: float  # Expected value/benefit
    execution_delay: timedelta  # How long to wait before executing
    stealth_level: float  # How stealthily to execute
    fallback_techniques: List[str]  # Backup options if this fails
    preconditions: List[str]  # What needs to be true to execute
    
@dataclass
class BehaviorPattern:
    """Behavioral pattern that influences adversary actions."""
    pattern_id: str
    name: str
    description: str
    trigger_conditions: List[str]
    behavioral_changes: Dict[str, float]  # Attribute -> change amount
    duration_hours: Optional[float] = None
    priority: int = 1  # Higher numbers = higher priority

class AdversaryBehaviorEngine:
    """Engine that simulates realistic adversary behavior and decision-making."""
    
    def __init__(self, adversary_profile: AdversaryProfile, 
                 target_environment: TargetEnvironment,
                 available_techniques: Dict[str, ATTACKTechnique]):
        self.profile = adversary_profile
        self.environment = target_environment
        self.available_techniques = available_techniques
        
        # Current state
        self.state = AdversaryState(
            current_position={"segment": "external", "access_level": "none"},
            compromised_assets=[],
            acquired_credentials=[],
            discovered_assets=[],
            failed_attempts=[],
            detection_events=[],
            mood=AdversaryMood.METHODICAL,
            fatigue_level=0.0,
            paranoia_level=self.profile.stealth_preference,
            confidence_level=self._calculate_initial_confidence(),
            time_pressure=0.0
        )
        
        # Behavior patterns
        self.behavior_patterns: List[BehaviorPattern] = []
        self.active_patterns: List[BehaviorPattern] = []
        
        # Decision weights based on profile
        self.decision_weights = {
            DecisionFactor.DETECTION_RISK: self.profile.stealth_preference,
            DecisionFactor.OPERATIONAL_SECURITY: self.profile.stealth_preference,
            DecisionFactor.TIME_PRESSURE: self.profile.speed_preference,
            DecisionFactor.RESOURCE_AVAILABILITY: self._get_resource_weight(),
            DecisionFactor.TARGET_VALUE: 0.8,
            DecisionFactor.SUCCESS_PROBABILITY: 0.7
        }
        
        self._initialize_behavior_patterns()
        logger.info(f"Adversary behavior engine initialized for {self.profile.name}")
    
    def _calculate_initial_confidence(self) -> float:
        """Calculate initial confidence based on profile."""
        skill_levels = {"low": 0.3, "medium": 0.5, "high": 0.7, "expert": 0.9}
        resource_levels = {"limited": 0.3, "moderate": 0.6, "extensive": 0.9}
        
        skill_conf = skill_levels.get(self.profile.skill_level, 0.5)
        resource_conf = resource_levels.get(self.profile.resources, 0.5)
        
        return (skill_conf + resource_conf) / 2.0
    
    def _get_resource_weight(self) -> float:
        """Get weight for resource availability factor."""
        resource_levels = {"limited": 0.9, "moderate": 0.6, "extensive": 0.3}
        return resource_levels.get(self.profile.resources, 0.6)
    
    def _initialize_behavior_patterns(self):
        """Initialize behavioral patterns based on adversary profile."""
        
        # APT-style patterns
        if self.profile.motivation == "espionage":
            self.behavior_patterns.extend([
                BehaviorPattern(
                    pattern_id="apt_patience",
                    name="Patient Infiltration",
                    description="Take time to avoid detection, prioritize stealth over speed",
                    trigger_conditions=["campaign_start", "detection_event"],
                    behavioral_changes={"paranoia_level": 0.2, "time_pressure": -0.3},
                    duration_hours=24.0,
                    priority=2
                ),
                BehaviorPattern(
                    pattern_id="apt_reconnaissance",
                    name="Thorough Reconnaissance",
                    description="Spend extra time on discovery and reconnaissance",
                    trigger_conditions=["initial_access", "new_network_segment"],
                    behavioral_changes={"confidence_level": 0.1},
                    duration_hours=8.0,
                    priority=1
                )
            ])
        
        # Ransomware patterns
        if self.profile.motivation == "financial" and "ransomware" in self.profile.name.lower():
            self.behavior_patterns.extend([
                BehaviorPattern(
                    pattern_id="ransomware_speed",
                    name="Rapid Deployment",
                    description="Move quickly to maximize damage before detection",
                    trigger_conditions=["initial_access", "domain_admin"],
                    behavioral_changes={"time_pressure": 0.4, "paranoia_level": -0.2},
                    duration_hours=12.0,
                    priority=3
                ),
                BehaviorPattern(
                    pattern_id="ransomware_spread",
                    name="Aggressive Lateral Movement",
                    description="Aggressively spread to as many systems as possible",
                    trigger_conditions=["lateral_movement_success"],
                    behavioral_changes={"confidence_level": 0.3, "fatigue_level": 0.1},
                    duration_hours=6.0,
                    priority=2
                )
            ])
        
        # Insider threat patterns
        if "insider" in self.profile.name.lower():
            self.behavior_patterns.extend([
                BehaviorPattern(
                    pattern_id="insider_opportunistic",
                    name="Opportunistic Access",
                    description="Take advantage of legitimate access windows",
                    trigger_conditions=["business_hours", "high_privilege_access"],
                    behavioral_changes={"confidence_level": 0.2, "paranoia_level": -0.1},
                    duration_hours=4.0,
                    priority=1
                ),
                BehaviorPattern(
                    pattern_id="insider_cautious",
                    name="Insider Caution",
                    description="Be extra careful to avoid suspicion from colleagues",
                    trigger_conditions=["detection_risk", "colleague_nearby"],
                    behavioral_changes={"paranoia_level": 0.3, "time_pressure": -0.2},
                    duration_hours=2.0,
                    priority=2
                )
            ])
        
        # General patterns
        self.behavior_patterns.extend([
            BehaviorPattern(
                pattern_id="detection_response",
                name="Detection Response",
                description="Respond to being detected by increasing caution",
                trigger_conditions=["detection_event"],
                behavioral_changes={"paranoia_level": 0.4, "confidence_level": -0.2, "time_pressure": 0.1},
                duration_hours=6.0,
                priority=3
            ),
            BehaviorPattern(
                pattern_id="success_boost",
                name="Success Confidence",
                description="Gain confidence from successful operations",
                trigger_conditions=["technique_success", "objective_complete"],
                behavioral_changes={"confidence_level": 0.1, "fatigue_level": -0.1},
                duration_hours=4.0,
                priority=1
            ),
            BehaviorPattern(
                pattern_id="failure_adaptation",
                name="Failure Adaptation", 
                description="Adapt approach after failures",
                trigger_conditions=["technique_failure", "multiple_failures"],
                behavioral_changes={"paranoia_level": 0.2, "time_pressure": 0.1, "confidence_level": -0.1},
                duration_hours=2.0,
                priority=2
            )
        ])
    
    async def select_next_technique(self, current_phase: CampaignPhase,
                                  available_techniques: List[str],
                                  campaign_context: Dict[str, Any]) -> Optional[TechniqueDecision]:
        """Select the next technique to execute based on adversary behavior."""
        
        if not available_techniques:
            return None
        
        # Update adversary state based on context
        await self._update_adversary_state(campaign_context)
        
        # Evaluate all available techniques
        technique_scores = {}
        for technique_id in available_techniques:
            if technique_id in self.available_techniques:
                score = await self._evaluate_technique(technique_id, current_phase, campaign_context)
                technique_scores[technique_id] = score
        
        if not technique_scores:
            return None
        
        # Select technique based on scores and behavior
        selected_technique = self._select_technique_by_behavior(technique_scores)
        
        if selected_technique:
            decision = await self._create_technique_decision(selected_technique, campaign_context)
            logger.info(f"Adversary selected technique {selected_technique} with confidence {decision.confidence:.3f}")
            return decision
        
        return None
    
    async def _update_adversary_state(self, context: Dict[str, Any]):
        """Update adversary state based on campaign context."""
        
        # Update mood based on recent events
        self._update_mood(context)
        
        # Update fatigue based on campaign duration
        campaign_duration = context.get("campaign_duration_hours", 0)
        self.state.fatigue_level = min(1.0, campaign_duration / 48.0)  # Max fatigue after 48 hours
        
        # Update time pressure based on campaign progress
        campaign_progress = context.get("campaign_progress", 0.0)
        if campaign_progress > 0.7:  # Near end of campaign
            self.state.time_pressure = min(1.0, self.state.time_pressure + 0.3)
        
        # Update paranoia based on recent detections
        recent_detections = context.get("recent_detections", 0)
        if recent_detections > 0:
            self.state.paranoia_level = min(1.0, self.state.paranoia_level + (recent_detections * 0.1))
        
        # Apply active behavior patterns
        await self._apply_behavior_patterns(context)
    
    def _update_mood(self, context: Dict[str, Any]):
        """Update adversary mood based on recent events."""
        
        success_rate = context.get("recent_success_rate", 0.5)
        detection_rate = context.get("recent_detection_rate", 0.0)
        
        if detection_rate > 0.3:
            self.state.mood = AdversaryMood.CAUTIOUS
        elif success_rate > 0.8 and detection_rate < 0.1:
            self.state.mood = AdversaryMood.AGGRESSIVE
        elif context.get("campaign_progress", 0.0) > 0.8:
            self.state.mood = AdversaryMood.DESPERATE
        elif success_rate < 0.3:
            self.state.mood = AdversaryMood.OPPORTUNISTIC
        else:
            self.state.mood = AdversaryMood.METHODICAL
    
    async def _apply_behavior_patterns(self, context: Dict[str, Any]):
        """Apply behavioral patterns that match current conditions."""
        
        # Check for new patterns to activate
        for pattern in self.behavior_patterns:
            if pattern not in self.active_patterns:
                if self._pattern_triggered(pattern, context):
                    self.active_patterns.append(pattern)
                    logger.debug(f"Activated behavior pattern: {pattern.name}")
        
        # Apply effects of active patterns
        for pattern in self.active_patterns[:]:  # Copy list to allow removal
            # Apply behavioral changes
            for attribute, change in pattern.behavioral_changes.items():
                current_value = getattr(self.state, attribute, 0.0)
                new_value = max(0.0, min(1.0, current_value + change))
                setattr(self.state, attribute, new_value)
            
            # Check if pattern should expire
            if pattern.duration_hours and context.get("pattern_start_time"):
                elapsed = datetime.now() - context["pattern_start_time"]
                if elapsed.total_seconds() / 3600 > pattern.duration_hours:
                    self.active_patterns.remove(pattern)
                    logger.debug(f"Expired behavior pattern: {pattern.name}")
    
    def _pattern_triggered(self, pattern: BehaviorPattern, context: Dict[str, Any]) -> bool:
        """Check if a behavior pattern should be triggered."""
        
        for condition in pattern.trigger_conditions:
            if condition == "campaign_start" and context.get("campaign_start", False):
                return True
            elif condition == "detection_event" and context.get("recent_detections", 0) > 0:
                return True
            elif condition == "initial_access" and "initial_access" in self.state.current_position:
                return True
            elif condition == "technique_success" and context.get("last_technique_success", False):
                return True
            elif condition == "technique_failure" and context.get("last_technique_failure", False):
                return True
            elif condition == "multiple_failures" and len(self.state.failed_attempts) >= 3:
                return True
        
        return False
    
    async def _evaluate_technique(self, technique_id: str, current_phase: CampaignPhase,
                                context: Dict[str, Any]) -> float:
        """Evaluate a technique and return a score for selection."""
        
        technique = self.available_techniques[technique_id]
        
        # Base score from technique characteristics
        base_score = 0.5
        
        # Adjust for adversary preferences
        if technique_id in self.profile.preferred_techniques:
            base_score += 0.3
        elif technique_id in self.profile.avoided_techniques:
            base_score -= 0.5
        
        # Adjust for difficulty vs skill level
        skill_levels = {"low": 0.3, "medium": 0.5, "high": 0.7, "expert": 0.9}
        adversary_skill = skill_levels.get(self.profile.skill_level, 0.5)
        
        if technique.difficulty > adversary_skill:
            base_score -= (technique.difficulty - adversary_skill) * 0.5
        else:
            base_score += (adversary_skill - technique.difficulty) * 0.2
        
        # Adjust for stealth requirements
        stealth_mismatch = abs(technique.stealth_rating - self.profile.stealth_preference)
        base_score -= stealth_mismatch * 0.3
        
        # Apply decision factors
        detection_risk = self._calculate_detection_risk(technique, context)
        base_score -= detection_risk * self.decision_weights[DecisionFactor.DETECTION_RISK]
        
        success_probability = self._calculate_success_probability(technique, context)
        base_score += success_probability * self.decision_weights[DecisionFactor.SUCCESS_PROBABILITY]
        
        # Adjust for current mood
        mood_adjustment = self._get_mood_adjustment(technique)
        base_score += mood_adjustment
        
        # Adjust for current adversary state
        state_adjustment = self._get_state_adjustment(technique)
        base_score += state_adjustment
        
        return max(0.0, min(1.0, base_score))
    
    def _calculate_detection_risk(self, technique: ATTACKTechnique, context: Dict[str, Any]) -> float:
        """Calculate risk of detection for a technique."""
        
        # Base risk from technique stealth rating
        base_risk = 1.0 - technique.stealth_rating
        
        # Adjust for environment security maturity
        security_levels = {"basic": 0.3, "intermediate": 0.6, "advanced": 0.8, "expert": 0.9}
        env_detection_capability = security_levels.get(self.environment.security_maturity, 0.5)
        
        detection_risk = base_risk * env_detection_capability
        
        # Adjust for recent detection events
        recent_detections = context.get("recent_detections", 0)
        if recent_detections > 0:
            detection_risk += recent_detections * 0.1
        
        # Adjust for current paranoia level
        detection_risk *= (1.0 + self.state.paranoia_level * 0.5)
        
        return min(1.0, detection_risk)
    
    def _calculate_success_probability(self, technique: ATTACKTechnique, context: Dict[str, Any]) -> float:
        """Calculate probability of technique success."""
        
        # Base success rate
        base_success = 0.7
        
        # Adjust for adversary skill vs technique difficulty
        skill_levels = {"low": 0.3, "medium": 0.5, "high": 0.7, "expert": 0.9}
        adversary_skill = skill_levels.get(self.profile.skill_level, 0.5)
        
        if adversary_skill >= technique.difficulty:
            success_rate = base_success + ((adversary_skill - technique.difficulty) * 0.3)
        else:
            success_rate = base_success - ((technique.difficulty - adversary_skill) * 0.4)
        
        # Adjust for fatigue
        success_rate *= (1.0 - self.state.fatigue_level * 0.3)
        
        # Adjust for confidence
        success_rate *= (0.7 + self.state.confidence_level * 0.3)
        
        # Adjust for environment factors
        if technique.required_privileges == "admin" and "admin_access" not in self.state.current_position:
            success_rate *= 0.3  # Much harder without required privileges
        
        return max(0.1, min(1.0, success_rate))
    
    def _get_mood_adjustment(self, technique: ATTACKTechnique) -> float:
        """Get score adjustment based on current mood."""
        
        if self.state.mood == AdversaryMood.AGGRESSIVE:
            # Prefer high-impact, fast techniques
            return technique.impact_rating * 0.2 - technique.stealth_rating * 0.1
        
        elif self.state.mood == AdversaryMood.CAUTIOUS:
            # Prefer stealthy, low-risk techniques  
            return technique.stealth_rating * 0.3 - technique.impact_rating * 0.1
        
        elif self.state.mood == AdversaryMood.DESPERATE:
            # Prefer any technique that might work quickly
            return technique.frequency_of_use * 0.2
        
        elif self.state.mood == AdversaryMood.OPPORTUNISTIC:
            # Prefer techniques with high success probability
            return technique.frequency_of_use * 0.1
        
        else:  # METHODICAL
            # Balanced approach
            return 0.0
    
    def _get_state_adjustment(self, technique: ATTACKTechnique) -> float:
        """Get score adjustment based on current adversary state."""
        
        adjustment = 0.0
        
        # Time pressure adjustment
        if self.state.time_pressure > 0.5:
            # Prefer faster techniques under time pressure
            if technique.difficulty < 0.5:  # Easier = faster
                adjustment += 0.2
        
        # Paranoia adjustment
        if self.state.paranoia_level > 0.7:
            # Strongly prefer stealthy techniques when paranoid
            adjustment += technique.stealth_rating * 0.3
        
        # Confidence adjustment
        if self.state.confidence_level > 0.7:
            # More willing to try difficult techniques when confident
            adjustment += technique.difficulty * 0.1
        elif self.state.confidence_level < 0.3:
            # Prefer easier techniques when not confident
            adjustment -= technique.difficulty * 0.2
        
        return adjustment
    
    def _select_technique_by_behavior(self, technique_scores: Dict[str, float]) -> Optional[str]:
        """Select technique based on scores and behavioral factors."""
        
        if not technique_scores:
            return None
        
        # Sort by score
        sorted_techniques = sorted(technique_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Apply behavioral selection logic
        if self.state.mood == AdversaryMood.METHODICAL:
            # Choose highest scoring technique
            return sorted_techniques[0][0]
        
        elif self.state.mood == AdversaryMood.AGGRESSIVE:
            # Choose from top 3, biased toward higher scores
            top_techniques = sorted_techniques[:3]
            weights = [0.6, 0.3, 0.1]
            return random.choices([t[0] for t in top_techniques], weights=weights)[0]
        
        elif self.state.mood == AdversaryMood.OPPORTUNISTIC:
            # Weighted random selection from all techniques
            techniques = [t[0] for t in sorted_techniques]
            weights = [t[1] for t in sorted_techniques]
            return random.choices(techniques, weights=weights)[0]
        
        elif self.state.mood == AdversaryMood.CAUTIOUS:
            # Choose from top half, but with some randomness
            top_half = sorted_techniques[:len(sorted_techniques)//2 + 1]
            return random.choice(top_half)[0]
        
        else:  # DESPERATE
            # Might choose any technique, even low-scoring ones
            return random.choice(list(technique_scores.keys()))
    
    async def _create_technique_decision(self, technique_id: str, 
                                       context: Dict[str, Any]) -> TechniqueDecision:
        """Create a detailed decision for executing a technique."""
        
        technique = self.available_techniques[technique_id]
        
        # Calculate confidence in this decision
        base_confidence = self.state.confidence_level
        if technique_id in self.profile.preferred_techniques:
            confidence = min(1.0, base_confidence + 0.2)
        else:
            confidence = base_confidence
        
        # Calculate risk assessment
        risk_assessment = self._calculate_detection_risk(technique, context)
        
        # Calculate expected value
        success_prob = self._calculate_success_probability(technique, context)
        expected_value = technique.impact_rating * success_prob
        
        # Calculate execution delay based on mood and paranoia
        base_delay_minutes = 5  # Minimum delay
        
        if self.state.mood == AdversaryMood.CAUTIOUS:
            delay_minutes = base_delay_minutes * (1 + self.state.paranoia_level * 3)
        elif self.state.mood == AdversaryMood.AGGRESSIVE:
            delay_minutes = base_delay_minutes * 0.5
        else:
            delay_minutes = base_delay_minutes * (1 + self.state.paranoia_level)
        
        execution_delay = timedelta(minutes=delay_minutes)
        
        # Determine stealth level
        stealth_level = min(1.0, technique.stealth_rating + self.state.paranoia_level * 0.3)
        
        # Select fallback techniques
        fallback_techniques = [
            tid for tid, t in self.available_techniques.items()
            if t.tactic == technique.tactic and tid != technique_id
        ][:2]  # Max 2 fallbacks
        
        # Determine preconditions
        preconditions = technique.prerequisites.copy()
        
        decision = TechniqueDecision(
            technique_id=technique_id,
            confidence=confidence,
            risk_assessment=risk_assessment,
            expected_value=expected_value,
            execution_delay=execution_delay,
            stealth_level=stealth_level,
            fallback_techniques=fallback_techniques,
            preconditions=preconditions
        )
        
        return decision
    
    async def process_technique_result(self, technique_id: str, success: bool,
                                     detected: bool, impact: float = 0.0):
        """Process the result of a technique execution."""
        
        if success:
            # Update confidence and reduce fatigue on success
            self.state.confidence_level = min(1.0, self.state.confidence_level + 0.05)
            self.state.fatigue_level = max(0.0, self.state.fatigue_level - 0.02)
            
            # Update current position based on technique
            await self._update_position_from_technique(technique_id, success)
            
            logger.debug(f"Technique {technique_id} succeeded, confidence now {self.state.confidence_level:.3f}")
        else:
            # Reduce confidence and increase fatigue on failure
            self.state.confidence_level = max(0.0, self.state.confidence_level - 0.1)
            self.state.fatigue_level = min(1.0, self.state.fatigue_level + 0.05)
            self.state.failed_attempts.append(technique_id)
            
            logger.debug(f"Technique {technique_id} failed, confidence now {self.state.confidence_level:.3f}")
        
        if detected:
            # Increase paranoia on detection
            self.state.paranoia_level = min(1.0, self.state.paranoia_level + 0.15)
            self.state.detection_events.append(technique_id)
            
            # Might trigger cautious behavior
            if len(self.state.detection_events) >= 2:
                self.state.mood = AdversaryMood.CAUTIOUS
            
            logger.warning(f"Technique {technique_id} was detected, paranoia now {self.state.paranoia_level:.3f}")
    
    async def _update_position_from_technique(self, technique_id: str, success: bool):
        """Update adversary position based on successful technique execution."""
        
        technique = self.available_techniques.get(technique_id)
        if not technique or not success:
            return
        
        # Update position based on technique type
        if technique.tactic == "initial-access":
            self.state.current_position["access_level"] = "user"
            self.state.current_position["segment"] = "internal"
        
        elif technique.tactic == "privilege-escalation":
            self.state.current_position["access_level"] = "admin"
        
        elif technique.tactic == "lateral-movement":
            # Add new compromised host
            new_host = f"HOST_{len(self.state.compromised_assets) + 1:03d}"
            self.state.compromised_assets.append(new_host)
        
        elif technique.tactic == "credential-access":
            # Add acquired credentials
            cred = {
                "type": "password",
                "username": f"user_{random.randint(1, 100)}",
                "domain": random.choice(self.environment.network_topology.get("segments", ["domain"])),
                "acquired_at": datetime.now().isoformat()
            }
            self.state.acquired_credentials.append(cred)
        
        elif technique.tactic == "discovery":
            # Add discovered assets
            for _ in range(random.randint(1, 3)):
                asset = f"ASSET_{len(self.state.discovered_assets) + 1:03d}"
                self.state.discovered_assets.append(asset)
    
    def get_adversary_status(self) -> Dict[str, Any]:
        """Get current status of the adversary."""
        
        return {
            "profile_name": self.profile.name,
            "current_mood": self.state.mood.value,
            "confidence_level": self.state.confidence_level,
            "paranoia_level": self.state.paranoia_level,
            "fatigue_level": self.state.fatigue_level,
            "time_pressure": self.state.time_pressure,
            "current_position": self.state.current_position,
            "compromised_assets": len(self.state.compromised_assets),
            "acquired_credentials": len(self.state.acquired_credentials),
            "discovered_assets": len(self.state.discovered_assets),
            "failed_attempts": len(self.state.failed_attempts),
            "detection_events": len(self.state.detection_events),
            "active_patterns": [p.name for p in self.active_patterns]
        }
    
    def export_behavior_log(self) -> List[Dict[str, Any]]:
        """Export detailed behavior log for analysis."""
        
        log_entries = []
        
        # Current state
        log_entries.append({
            "timestamp": datetime.now().isoformat(),
            "type": "state_snapshot",
            "data": asdict(self.state)
        })
        
        # Active patterns
        for pattern in self.active_patterns:
            log_entries.append({
                "timestamp": datetime.now().isoformat(),
                "type": "active_pattern",
                "data": asdict(pattern)
            })
        
        return log_entries
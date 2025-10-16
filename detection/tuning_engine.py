"""Continuous Tuning Engine - automatically optimizes detection rules based on performance feedback."""

import asyncio
import logging
import json
import yaml
import copy
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod

from agents.analyst.sigma_gen import generate_sigma_rule, validate_sigma_rule
from detection.feedback_loop import DetectionFeedbackLoop, FeedbackType
from detection.performance_monitor import RulePerformanceMonitor

logger = logging.getLogger(__name__)

class TuningStrategy(Enum):
    """Available tuning strategies."""
    THRESHOLD_ADJUSTMENT = "threshold_adjustment"
    FIELD_REFINEMENT = "field_refinement"
    TIMEFRAME_OPTIMIZATION = "timeframe_optimization"
    CONDITION_SIMPLIFICATION = "condition_simplification"
    CORRELATION_ENHANCEMENT = "correlation_enhancement"
    NOISE_REDUCTION = "noise_reduction"

class TuningAction(Enum):
    """Types of tuning actions."""
    MODIFY_RULE = "modify_rule"
    DISABLE_RULE = "disable_rule"
    CREATE_VARIANT = "create_variant"
    ADD_WHITELIST = "add_whitelist"
    ADJUST_SEVERITY = "adjust_severity"

@dataclass
class TuningRecommendation:
    """Recommendation for rule tuning."""
    rule_id: str
    strategy: TuningStrategy
    action: TuningAction
    confidence: float  # 0.0 to 1.0
    description: str
    rationale: str
    proposed_changes: Dict[str, Any]
    estimated_impact: Dict[str, float]  # Expected changes in metrics
    risk_assessment: str  # low, medium, high
    requires_approval: bool = True
    
@dataclass
class TuningResult:
    """Result of applying a tuning recommendation."""
    rule_id: str
    recommendation_id: str
    action_taken: TuningAction
    success: bool
    new_rule_id: Optional[str] = None
    applied_changes: Dict[str, Any] = None
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.applied_changes is None:
            self.applied_changes = {}

class TuningOptimizer(ABC):
    """Abstract base class for tuning optimizers."""
    
    @abstractmethod
    def analyze_rule(self, rule_data: Dict[str, Any], 
                    performance_metrics: Dict[str, float],
                    feedback_data: List[Dict[str, Any]]) -> List[TuningRecommendation]:
        """Analyze a rule and generate tuning recommendations."""
        pass
    
    @abstractmethod
    def apply_recommendation(self, rule_data: Dict[str, Any], 
                           recommendation: TuningRecommendation) -> TuningResult:
        """Apply a tuning recommendation to a rule."""
        pass

class SigmaRuleTuningOptimizer(TuningOptimizer):
    """Optimizer for Sigma detection rules."""
    
    def analyze_rule(self, rule_data: Dict[str, Any], 
                    performance_metrics: Dict[str, float],
                    feedback_data: List[Dict[str, Any]]) -> List[TuningRecommendation]:
        """Analyze Sigma rule and generate tuning recommendations."""
        
        recommendations = []
        rule_id = rule_data.get("rule_id", "unknown")
        
        # Parse Sigma rule
        try:
            sigma_yaml = rule_data.get("rule_yaml", "")
            if not sigma_yaml:
                return recommendations
            
            sigma_rule = yaml.safe_load(sigma_yaml)
        except Exception as e:
            logger.error(f"Failed to parse Sigma rule {rule_id}: {e}")
            return recommendations
        
        # Analyze performance issues
        false_positive_rate = performance_metrics.get("false_positive_rate", 0.0)
        alert_frequency = performance_metrics.get("alert_frequency", 0.0)
        performance_score = performance_metrics.get("performance_score", 0.5)
        
        # High false positive rate - recommend noise reduction
        if false_positive_rate > 0.3:
            recommendations.append(self._recommend_noise_reduction(
                rule_id, sigma_rule, false_positive_rate, feedback_data
            ))
        
        # High alert frequency - recommend threshold adjustment
        if alert_frequency > 10.0:
            recommendations.append(self._recommend_threshold_adjustment(
                rule_id, sigma_rule, alert_frequency
            ))
        
        # Low performance - recommend field refinement
        if performance_score < 0.5:
            recommendations.append(self._recommend_field_refinement(
                rule_id, sigma_rule, performance_score, feedback_data
            ))
        
        # Analyze feedback patterns for specific optimizations
        fp_feedback = [f for f in feedback_data if f.get("feedback_type") == "false_positive"]
        if len(fp_feedback) > 5:  # Enough false positive data
            recommendations.extend(self._analyze_false_positive_patterns(
                rule_id, sigma_rule, fp_feedback
            ))
        
        return recommendations
    
    def _recommend_noise_reduction(self, rule_id: str, sigma_rule: Dict[str, Any], 
                                 fp_rate: float, feedback_data: List[Dict[str, Any]]) -> TuningRecommendation:
        """Recommend noise reduction strategies."""
        
        # Analyze common false positive patterns
        fp_patterns = self._extract_fp_patterns(feedback_data)
        
        proposed_changes = {}
        
        # Add exclusions for common false positive patterns
        if fp_patterns:
            exclusions = []
            for pattern in fp_patterns[:3]:  # Top 3 patterns
                if "process.name" in pattern:
                    exclusions.append(f"NOT process.name:\"{pattern['process.name']}\"")
                elif "source.ip" in pattern:
                    exclusions.append(f"NOT source.ip:\"{pattern['source.ip']}\"")
            
            if exclusions:
                proposed_changes["exclusions"] = exclusions
        
        # Increase specificity by adding more conditions
        detection = sigma_rule.get("detection", {})
        selection = detection.get("selection", {})
        
        # Suggest adding event category filter if not present
        if "event.category" not in selection:
            proposed_changes["add_event_category"] = True
        
        return TuningRecommendation(
            rule_id=rule_id,
            strategy=TuningStrategy.NOISE_REDUCTION,
            action=TuningAction.MODIFY_RULE,
            confidence=0.8,
            description=f"Reduce false positive rate from {fp_rate:.3f}",
            rationale=f"High false positive rate ({fp_rate:.3f}) causing alert fatigue",
            proposed_changes=proposed_changes,
            estimated_impact={
                "false_positive_rate": -0.3,  # Expected reduction
                "alert_frequency": -0.2,
                "precision": 0.2
            },
            risk_assessment="low",
            requires_approval=False
        )
    
    def _recommend_threshold_adjustment(self, rule_id: str, sigma_rule: Dict[str, Any], 
                                      alert_freq: float) -> TuningRecommendation:
        """Recommend threshold adjustments for high-frequency rules."""
        
        detection = sigma_rule.get("detection", {})
        condition = detection.get("condition", "selection")
        
        proposed_changes = {}
        
        # If using count condition, increase threshold
        if "count()" in condition:
            # Extract current threshold
            import re
            count_match = re.search(r'count\(\)\s*>\s*(\d+)', condition)
            if count_match:
                current_threshold = int(count_match.group(1))
                new_threshold = min(current_threshold * 2, 20)  # Double, but cap at 20
                proposed_changes["count_threshold"] = new_threshold
            else:
                # Add count condition if not present
                proposed_changes["add_count_condition"] = {"threshold": 5, "timeframe": "5m"}
        else:
            # Add timeframe aggregation
            proposed_changes["add_timeframe"] = "5m"
            proposed_changes["add_count_condition"] = {"threshold": 3, "timeframe": "5m"}
        
        return TuningRecommendation(
            rule_id=rule_id,
            strategy=TuningStrategy.THRESHOLD_ADJUSTMENT,
            action=TuningAction.MODIFY_RULE,
            confidence=0.9,
            description=f"Reduce alert frequency from {alert_freq:.1f}/hour",
            rationale=f"High alert frequency ({alert_freq:.1f}/hour) causing alert overload",
            proposed_changes=proposed_changes,
            estimated_impact={
                "alert_frequency": -0.5,  # Expected 50% reduction
                "false_positive_rate": -0.1,
                "precision": 0.1
            },
            risk_assessment="low",
            requires_approval=False
        )
    
    def _recommend_field_refinement(self, rule_id: str, sigma_rule: Dict[str, Any], 
                                   perf_score: float, feedback_data: List[Dict[str, Any]]) -> TuningRecommendation:
        """Recommend field refinements to improve detection accuracy."""
        
        detection = sigma_rule.get("detection", {})
        selection = detection.get("selection", {})
        
        proposed_changes = {}
        
        # Analyze true positive patterns to identify missing fields
        tp_feedback = [f for f in feedback_data if f.get("feedback_type") == "true_positive"]
        
        if tp_feedback:
            # Look for common fields in true positives that aren't in the rule
            tp_patterns = self._extract_tp_patterns(tp_feedback)
            
            for pattern in tp_patterns:
                for field, value in pattern.items():
                    if field not in selection and field.startswith(("process.", "network.", "file.")):
                        # Suggest adding this field
                        if "additional_conditions" not in proposed_changes:
                            proposed_changes["additional_conditions"] = {}
                        proposed_changes["additional_conditions"][field] = value
        
        # Suggest more specific value matching
        for field, value in selection.items():
            if isinstance(value, str) and "*" in value:
                # Make wildcard more specific
                proposed_changes[f"refine_{field}"] = value.replace("*", "")
        
        return TuningRecommendation(
            rule_id=rule_id,
            strategy=TuningStrategy.FIELD_REFINEMENT,
            action=TuningAction.MODIFY_RULE,
            confidence=0.7,
            description=f"Improve performance score from {perf_score:.3f}",
            rationale=f"Low performance score ({perf_score:.3f}) suggests rule needs refinement",
            proposed_changes=proposed_changes,
            estimated_impact={
                "performance_score": 0.2,
                "precision": 0.15,
                "false_positive_rate": -0.1
            },
            risk_assessment="medium",
            requires_approval=True
        )
    
    def _analyze_false_positive_patterns(self, rule_id: str, sigma_rule: Dict[str, Any], 
                                       fp_feedback: List[Dict[str, Any]]) -> List[TuningRecommendation]:
        """Analyze false positive patterns for specific tuning recommendations."""
        
        recommendations = []
        
        # Group false positives by common characteristics
        patterns = self._extract_fp_patterns(fp_feedback)
        
        for i, pattern in enumerate(patterns[:2]):  # Top 2 patterns
            # Create whitelist recommendation for this pattern
            recommendations.append(TuningRecommendation(
                rule_id=rule_id,
                strategy=TuningStrategy.NOISE_REDUCTION,
                action=TuningAction.ADD_WHITELIST,
                confidence=0.8,
                description=f"Add whitelist for false positive pattern #{i+1}",
                rationale=f"Pattern appears in {pattern.get('count', 0)} false positives",
                proposed_changes={"whitelist_pattern": pattern},
                estimated_impact={
                    "false_positive_rate": -0.2,
                    "precision": 0.15
                },
                risk_assessment="low",
                requires_approval=False
            ))
        
        return recommendations
    
    def _extract_fp_patterns(self, fp_feedback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract common patterns from false positive feedback."""
        
        patterns = []
        
        # Simple pattern extraction - in practice would be more sophisticated
        for feedback in fp_feedback:
            details = feedback.get("details", {})
            if "alert_data" in details:
                alert_data = details["alert_data"]
                pattern = {}
                
                # Extract common fields that might be causing false positives
                for field in ["process.name", "source.ip", "user.name", "host.name"]:
                    if field in alert_data:
                        pattern[field] = alert_data[field]
                
                if pattern:
                    pattern["count"] = 1
                    patterns.append(pattern)
        
        # Group similar patterns (simplified)
        grouped_patterns = []
        for pattern in patterns:
            # Find existing similar pattern
            found = False
            for gp in grouped_patterns:
                if self._patterns_similar(pattern, gp):
                    gp["count"] += 1
                    found = True
                    break
            
            if not found:
                grouped_patterns.append(pattern)
        
        # Sort by frequency
        grouped_patterns.sort(key=lambda x: x.get("count", 0), reverse=True)
        
        return grouped_patterns[:5]  # Top 5 patterns
    
    def _extract_tp_patterns(self, tp_feedback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract common patterns from true positive feedback."""
        
        patterns = []
        
        for feedback in tp_feedback:
            details = feedback.get("details", {})
            if "alert_data" in details:
                alert_data = details["alert_data"]
                pattern = {}
                
                # Extract fields that might improve detection
                for field in ["event.category", "event.action", "network.protocol"]:
                    if field in alert_data:
                        pattern[field] = alert_data[field]
                
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    def _patterns_similar(self, pattern1: Dict[str, Any], pattern2: Dict[str, Any]) -> bool:
        """Check if two patterns are similar."""
        
        # Simple similarity check
        common_fields = set(pattern1.keys()) & set(pattern2.keys())
        if len(common_fields) == 0:
            return False
        
        matches = 0
        for field in common_fields:
            if pattern1[field] == pattern2[field]:
                matches += 1
        
        similarity = matches / len(common_fields)
        return similarity > 0.7
    
    def apply_recommendation(self, rule_data: Dict[str, Any], 
                           recommendation: TuningRecommendation) -> TuningResult:
        """Apply a tuning recommendation to a Sigma rule."""
        
        rule_id = rule_data.get("rule_id")
        
        try:
            if recommendation.action == TuningAction.MODIFY_RULE:
                return self._modify_sigma_rule(rule_data, recommendation)
            elif recommendation.action == TuningAction.CREATE_VARIANT:
                return self._create_rule_variant(rule_data, recommendation)
            elif recommendation.action == TuningAction.ADD_WHITELIST:
                return self._add_whitelist(rule_data, recommendation)
            elif recommendation.action == TuningAction.DISABLE_RULE:
                return self._disable_rule(rule_data, recommendation)
            else:
                return TuningResult(
                    rule_id=rule_id,
                    recommendation_id=f"{rule_id}_{recommendation.strategy.value}",
                    action_taken=recommendation.action,
                    success=False,
                    error_message=f"Unsupported action: {recommendation.action}"
                )
        
        except Exception as e:
            return TuningResult(
                rule_id=rule_id,
                recommendation_id=f"{rule_id}_{recommendation.strategy.value}",
                action_taken=recommendation.action,
                success=False,
                error_message=str(e)
            )
    
    def _modify_sigma_rule(self, rule_data: Dict[str, Any], 
                         recommendation: TuningRecommendation) -> TuningResult:
        """Modify a Sigma rule based on recommendation."""
        
        rule_id = rule_data.get("rule_id")
        sigma_yaml = rule_data.get("rule_yaml", "")
        
        # Parse original rule
        sigma_rule = yaml.safe_load(sigma_yaml)
        modified_rule = copy.deepcopy(sigma_rule)
        
        # Apply changes based on proposed changes
        changes = recommendation.proposed_changes
        applied_changes = {}
        
        # Handle different types of modifications
        if "exclusions" in changes:
            # Add exclusions to detection condition
            detection = modified_rule.setdefault("detection", {})
            condition = detection.get("condition", "selection")
            
            exclusions = " AND ".join([f"NOT ({exc})" for exc in changes["exclusions"]])
            detection["condition"] = f"({condition}) AND {exclusions}"
            applied_changes["added_exclusions"] = changes["exclusions"]
        
        if "count_threshold" in changes:
            # Modify count threshold in condition
            detection = modified_rule.setdefault("detection", {})
            new_threshold = changes["count_threshold"]
            detection["condition"] = f"selection | count() > {new_threshold}"
            applied_changes["count_threshold"] = new_threshold
        
        if "add_count_condition" in changes:
            # Add count condition
            detection = modified_rule.setdefault("detection", {})
            count_config = changes["add_count_condition"]
            detection["condition"] = f"selection | count() > {count_config['threshold']}"
            detection["timeframe"] = count_config["timeframe"]
            applied_changes["added_count_condition"] = count_config
        
        if "additional_conditions" in changes:
            # Add additional selection conditions
            detection = modified_rule.setdefault("detection", {})
            selection = detection.setdefault("selection", {})
            
            for field, value in changes["additional_conditions"].items():
                selection[field] = value
                applied_changes[f"added_{field}"] = value
        
        # Generate new rule YAML
        new_yaml = yaml.dump(modified_rule, default_flow_style=False, sort_keys=False)
        
        # Validate the modified rule
        validation = validate_sigma_rule(new_yaml)
        
        if not validation.get("valid", False):
            return TuningResult(
                rule_id=rule_id,
                recommendation_id=f"{rule_id}_{recommendation.strategy.value}",
                action_taken=recommendation.action,
                success=False,
                error_message=f"Modified rule validation failed: {validation.get('errors', [])}"
            )
        
        # Create updated rule data
        updated_rule_data = copy.deepcopy(rule_data)
        updated_rule_data["rule_yaml"] = new_yaml
        updated_rule_data["title"] = modified_rule.get("title", "") + " (Tuned)"
        updated_rule_data["generated_at"] = datetime.now().isoformat()
        
        return TuningResult(
            rule_id=rule_id,
            recommendation_id=f"{rule_id}_{recommendation.strategy.value}",
            action_taken=recommendation.action,
            success=True,
            new_rule_id=rule_id,  # Same rule, modified
            applied_changes=applied_changes
        )
    
    def _create_rule_variant(self, rule_data: Dict[str, Any], 
                           recommendation: TuningRecommendation) -> TuningResult:
        """Create a variant of the rule with modifications."""
        
        # Similar to modify, but creates new rule with new ID
        result = self._modify_sigma_rule(rule_data, recommendation)
        
        if result.success:
            # Generate new rule ID for variant
            original_id = rule_data.get("rule_id", "unknown")
            variant_id = f"{original_id}_variant_{recommendation.strategy.value}"
            result.new_rule_id = variant_id
            result.action_taken = TuningAction.CREATE_VARIANT
        
        return result
    
    def _add_whitelist(self, rule_data: Dict[str, Any], 
                     recommendation: TuningRecommendation) -> TuningResult:
        """Add whitelist conditions to reduce false positives."""
        
        rule_id = rule_data.get("rule_id")
        
        # This would typically involve creating a separate whitelist rule
        # or modifying the rule to exclude whitelist patterns
        
        whitelist_pattern = recommendation.proposed_changes.get("whitelist_pattern", {})
        
        applied_changes = {
            "whitelist_added": True,
            "whitelist_pattern": whitelist_pattern
        }
        
        return TuningResult(
            rule_id=rule_id,
            recommendation_id=f"{rule_id}_whitelist",
            action_taken=TuningAction.ADD_WHITELIST,
            success=True,
            applied_changes=applied_changes
        )
    
    def _disable_rule(self, rule_data: Dict[str, Any], 
                    recommendation: TuningRecommendation) -> TuningResult:
        """Disable a rule."""
        
        rule_id = rule_data.get("rule_id")
        
        return TuningResult(
            rule_id=rule_id,
            recommendation_id=f"{rule_id}_disable",
            action_taken=TuningAction.DISABLE_RULE,
            success=True,
            applied_changes={"disabled": True}
        )

class ContinuousTuningEngine:
    """Main engine for continuous rule tuning."""
    
    def __init__(self):
        self.optimizers: Dict[str, TuningOptimizer] = {
            "sigma": SigmaRuleTuningOptimizer()
        }
        
        self.tuning_history: List[TuningResult] = []
        self.pending_recommendations: Dict[str, List[TuningRecommendation]] = {}
        
        # Tuning configuration
        self.config = {
            "auto_apply_low_risk": True,
            "require_approval_medium_risk": True,
            "require_approval_high_risk": True,
            "max_recommendations_per_rule": 3,
            "min_feedback_samples": 10
        }
        
        logger.info("Continuous tuning engine initialized")
    
    async def tune_rules(self, performance_scores: Dict[str, float], 
                        deployed_rules: Set[str] = None) -> int:
        """Analyze and tune rules based on performance scores."""
        
        if not performance_scores:
            return 0
        
        tuned_count = 0
        
        # Filter to deployed rules if specified
        if deployed_rules:
            performance_scores = {
                rule_id: score for rule_id, score in performance_scores.items()
                if rule_id in deployed_rules
            }
        
        # Identify rules that need tuning
        rules_to_tune = [
            rule_id for rule_id, score in performance_scores.items()
            if score < 0.7  # Threshold for tuning consideration
        ]
        
        logger.info(f"Analyzing {len(rules_to_tune)} rules for tuning opportunities")
        
        for rule_id in rules_to_tune:
            try:
                recommendations = await self._analyze_rule_for_tuning(
                    rule_id, performance_scores[rule_id]
                )
                
                if recommendations:
                    self.pending_recommendations[rule_id] = recommendations
                    
                    # Auto-apply low-risk recommendations
                    auto_applied = await self._auto_apply_recommendations(
                        rule_id, recommendations
                    )
                    
                    tuned_count += auto_applied
                    
            except Exception as e:
                logger.error(f"Failed to analyze rule {rule_id} for tuning: {e}")
        
        logger.info(f"Generated tuning recommendations for {len(self.pending_recommendations)} rules")
        logger.info(f"Auto-applied {tuned_count} low-risk tuning actions")
        
        return tuned_count
    
    async def _analyze_rule_for_tuning(self, rule_id: str, 
                                     performance_score: float) -> List[TuningRecommendation]:
        """Analyze a specific rule for tuning opportunities."""
        
        # In a real implementation, this would fetch rule data and feedback
        # For now, simulate with mock data
        
        rule_data = await self._fetch_rule_data(rule_id)
        if not rule_data:
            return []
        
        performance_metrics = await self._fetch_performance_metrics(rule_id)
        feedback_data = await self._fetch_feedback_data(rule_id)
        
        # Skip if insufficient feedback data
        if len(feedback_data) < self.config["min_feedback_samples"]:
            logger.debug(f"Insufficient feedback data for rule {rule_id}")
            return []
        
        # Determine rule type and use appropriate optimizer
        rule_type = self._determine_rule_type(rule_data)
        optimizer = self.optimizers.get(rule_type)
        
        if not optimizer:
            logger.warning(f"No optimizer available for rule type: {rule_type}")
            return []
        
        # Generate recommendations
        recommendations = optimizer.analyze_rule(
            rule_data, performance_metrics, feedback_data
        )
        
        # Limit number of recommendations per rule
        max_recommendations = self.config["max_recommendations_per_rule"]
        recommendations = recommendations[:max_recommendations]
        
        logger.info(f"Generated {len(recommendations)} tuning recommendations for rule {rule_id}")
        
        return recommendations
    
    async def _auto_apply_recommendations(self, rule_id: str, 
                                        recommendations: List[TuningRecommendation]) -> int:
        """Auto-apply low-risk recommendations."""
        
        applied_count = 0
        
        for recommendation in recommendations:
            # Check if auto-application is allowed
            if not self._should_auto_apply(recommendation):
                continue
            
            try:
                result = await self._apply_recommendation(rule_id, recommendation)
                
                if result.success:
                    applied_count += 1
                    self.tuning_history.append(result)
                    logger.info(f"Auto-applied tuning: {recommendation.description}")
                else:
                    logger.error(f"Failed to apply tuning: {result.error_message}")
                    
            except Exception as e:
                logger.error(f"Error applying recommendation: {e}")
        
        return applied_count
    
    def _should_auto_apply(self, recommendation: TuningRecommendation) -> bool:
        """Determine if a recommendation should be auto-applied."""
        
        # Check configuration
        if recommendation.risk_assessment == "low" and self.config["auto_apply_low_risk"]:
            return not recommendation.requires_approval
        
        return False
    
    async def _apply_recommendation(self, rule_id: str, 
                                  recommendation: TuningRecommendation) -> TuningResult:
        """Apply a tuning recommendation."""
        
        # Fetch rule data
        rule_data = await self._fetch_rule_data(rule_id)
        if not rule_data:
            return TuningResult(
                rule_id=rule_id,
                recommendation_id=f"{rule_id}_{recommendation.strategy.value}",
                action_taken=recommendation.action,
                success=False,
                error_message="Rule data not found"
            )
        
        # Determine rule type and get optimizer
        rule_type = self._determine_rule_type(rule_data)
        optimizer = self.optimizers.get(rule_type)
        
        if not optimizer:
            return TuningResult(
                rule_id=rule_id,
                recommendation_id=f"{rule_id}_{recommendation.strategy.value}",
                action_taken=recommendation.action,
                success=False,
                error_message=f"No optimizer for rule type: {rule_type}"
            )
        
        # Apply recommendation
        result = optimizer.apply_recommendation(rule_data, recommendation)
        
        return result
    
    async def _fetch_rule_data(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Fetch rule data (mock implementation)."""
        
        # In practice, this would query from a rule repository
        # For now, return mock data
        
        mock_rule_data = {
            "rule_id": rule_id,
            "rule_yaml": f"""
title: Mock Rule {rule_id}
id: {rule_id}
status: experimental
description: Mock rule for testing
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
level: medium
            """.strip(),
            "title": f"Mock Rule {rule_id}",
            "generated_at": datetime.now().isoformat()
        }
        
        return mock_rule_data
    
    async def _fetch_performance_metrics(self, rule_id: str) -> Dict[str, float]:
        """Fetch performance metrics for a rule (mock implementation)."""
        
        # Mock performance data
        return {
            "performance_score": 0.6,
            "false_positive_rate": 0.4,
            "alert_frequency": 12.0,
            "precision": 0.6,
            "recall": 0.7
        }
    
    async def _fetch_feedback_data(self, rule_id: str) -> List[Dict[str, Any]]:
        """Fetch feedback data for a rule (mock implementation)."""
        
        # Mock feedback data
        feedback = []
        
        for i in range(15):  # Generate 15 mock feedback items
            feedback.append({
                "feedback_id": f"fb_{rule_id}_{i}",
                "rule_id": rule_id,
                "feedback_type": "false_positive" if i % 3 == 0 else "true_positive",
                "timestamp": datetime.now() - timedelta(hours=i),
                "source": "analyst",
                "confidence": 0.8,
                "details": {
                    "alert_data": {
                        "process.name": f"process_{i}",
                        "source.ip": f"192.168.1.{100 + i}",
                        "event.category": "process"
                    }
                }
            })
        
        return feedback
    
    def _determine_rule_type(self, rule_data: Dict[str, Any]) -> str:
        """Determine the type of rule for optimizer selection."""
        
        if "rule_yaml" in rule_data:
            return "sigma"
        elif "query" in rule_data:
            return "elastic"
        else:
            return "unknown"
    
    def get_pending_recommendations(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all pending tuning recommendations."""
        
        pending = {}
        
        for rule_id, recommendations in self.pending_recommendations.items():
            pending[rule_id] = [asdict(rec) for rec in recommendations]
        
        return pending
    
    def get_tuning_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get tuning history."""
        
        recent_history = self.tuning_history[-limit:] if limit else self.tuning_history
        return [asdict(result) for result in recent_history]
    
    async def approve_recommendation(self, rule_id: str, recommendation_id: str) -> bool:
        """Approve and apply a pending recommendation."""
        
        if rule_id not in self.pending_recommendations:
            return False
        
        recommendations = self.pending_recommendations[rule_id]
        
        # Find the specific recommendation
        target_rec = None
        for rec in recommendations:
            if f"{rule_id}_{rec.strategy.value}" == recommendation_id:
                target_rec = rec
                break
        
        if not target_rec:
            return False
        
        try:
            result = await self._apply_recommendation(rule_id, target_rec)
            
            if result.success:
                self.tuning_history.append(result)
                
                # Remove from pending
                self.pending_recommendations[rule_id] = [
                    r for r in recommendations if f"{rule_id}_{r.strategy.value}" != recommendation_id
                ]
                
                logger.info(f"Applied approved recommendation: {target_rec.description}")
                return True
            else:
                logger.error(f"Failed to apply approved recommendation: {result.error_message}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying approved recommendation: {e}")
            return False
    
    def get_tuning_statistics(self) -> Dict[str, Any]:
        """Get tuning engine statistics."""
        
        total_recommendations = sum(len(recs) for recs in self.pending_recommendations.values())
        total_applied = len(self.tuning_history)
        
        # Count by strategy
        strategy_counts = {}
        for result in self.tuning_history:
            strategy = result.recommendation_id.split("_")[-1]
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Success rate
        successful = len([r for r in self.tuning_history if r.success])
        success_rate = successful / max(total_applied, 1)
        
        return {
            "total_pending_recommendations": total_recommendations,
            "total_applied_tunings": total_applied,
            "success_rate": success_rate,
            "tuning_by_strategy": strategy_counts,
            "rules_with_pending_recommendations": len(self.pending_recommendations),
            "config": self.config
        }
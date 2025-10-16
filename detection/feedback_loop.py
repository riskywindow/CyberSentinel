"""Detection Feedback Loop - collects and analyzes detection rule performance feedback."""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
from enum import Enum

# Optional storage import
try:
    from storage.clickhouse_client import ClickHouseClient
except ImportError:
    ClickHouseClient = None

logger = logging.getLogger(__name__)

class FeedbackType(Enum):
    """Types of feedback for detection rules."""
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    BENIGN_POSITIVE = "benign_positive"  # Triggered but not malicious
    MISSED_DETECTION = "missed_detection"
    PERFORMANCE_ISSUE = "performance_issue"

@dataclass
class RuleFeedback:
    """Individual feedback item for a detection rule."""
    feedback_id: str
    rule_id: str
    feedback_type: FeedbackType
    timestamp: datetime
    source: str  # analyst, automated, user, etc.
    confidence: float  # 0.0 to 1.0
    alert_id: Optional[str] = None
    incident_id: Optional[str] = None
    details: Dict[str, Any] = None
    analyst_notes: Optional[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}

@dataclass
class RulePerformanceMetrics:
    """Performance metrics for a detection rule."""
    rule_id: str
    evaluation_period: timedelta
    total_alerts: int
    true_positives: int
    false_positives: int
    benign_positives: int
    missed_detections: int
    precision: float
    recall: float
    f1_score: float
    alert_volume_score: float  # Based on alert frequency
    performance_score: float  # Overall score
    last_updated: datetime
    feedback_sources: Dict[str, int] = None
    
    def __post_init__(self):
        if self.feedback_sources is None:
            self.feedback_sources = {}

class DetectionFeedbackLoop:
    """Collects and analyzes feedback on detection rule performance."""
    
    def __init__(self, clickhouse_client = None):
        self.clickhouse = clickhouse_client
        self.feedback_cache: Dict[str, List[RuleFeedback]] = defaultdict(list)
        self.performance_cache: Dict[str, RulePerformanceMetrics] = {}
        
        logger.info("Detection feedback loop initialized")
    
    async def collect_feedback(self, rule_ids: List[str] = None, 
                             lookback_hours: int = 168) -> int:
        """Collect feedback for specified rules or all rules."""
        
        if not self.clickhouse:
            logger.warning("No ClickHouse client available for feedback collection")
            return 0
        
        try:
            # Time window for feedback collection
            lookback_time = datetime.now() - timedelta(hours=lookback_hours)
            
            # Build query for alert feedback
            if rule_ids:
                rule_list = ','.join([f"'{r}'" for r in rule_ids])
                rule_filter = f"AND rule_id IN ({rule_list})"
            else:
                rule_filter = ""
            
            feedback_query = f"""
            SELECT 
                alert_id,
                rule_id,
                feedback_type,
                timestamp,
                source,
                confidence,
                incident_id,
                analyst_notes,
                details
            FROM alert_feedback 
            WHERE timestamp >= '{lookback_time.isoformat()}'
            {rule_filter}
            ORDER BY timestamp DESC
            """
            
            feedback_results = await self.clickhouse.query(feedback_query)
            
            feedback_count = 0
            for row in feedback_results:
                try:
                    feedback = RuleFeedback(
                        feedback_id=f"{row['alert_id']}_{row['timestamp'].isoformat()}",
                        rule_id=row["rule_id"],
                        feedback_type=FeedbackType(row["feedback_type"]),
                        timestamp=row["timestamp"],
                        source=row["source"],
                        confidence=float(row["confidence"]),
                        alert_id=row["alert_id"],
                        incident_id=row.get("incident_id"),
                        details=json.loads(row["details"]) if row.get("details") else {},
                        analyst_notes=row.get("analyst_notes")
                    )
                    
                    self.feedback_cache[feedback.rule_id].append(feedback)
                    feedback_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to parse feedback row: {e}")
            
            logger.info(f"Collected {feedback_count} feedback items for {len(rule_ids or [])} rules")
            return feedback_count
            
        except Exception as e:
            logger.error(f"Failed to collect feedback from ClickHouse: {e}")
            return 0
    
    async def analyze_rule_performance(self, rule_id: str, 
                                     evaluation_hours: int = 168) -> Optional[RulePerformanceMetrics]:
        """Analyze performance metrics for a specific rule."""
        
        evaluation_period = timedelta(hours=evaluation_hours)
        cutoff_time = datetime.now() - evaluation_period
        
        # Get feedback for this rule
        rule_feedback = [
            fb for fb in self.feedback_cache.get(rule_id, [])
            if fb.timestamp >= cutoff_time
        ]
        
        if not rule_feedback:
            logger.debug(f"No feedback found for rule {rule_id}")
            return None
        
        # Count feedback types
        feedback_counts = defaultdict(int)
        feedback_sources = defaultdict(int)
        
        for feedback in rule_feedback:
            feedback_counts[feedback.feedback_type] += 1
            feedback_sources[feedback.source] += 1
        
        # Calculate metrics
        true_positives = feedback_counts[FeedbackType.TRUE_POSITIVE]
        false_positives = feedback_counts[FeedbackType.FALSE_POSITIVE]
        benign_positives = feedback_counts[FeedbackType.BENIGN_POSITIVE]
        missed_detections = feedback_counts[FeedbackType.MISSED_DETECTION]
        
        total_alerts = true_positives + false_positives + benign_positives
        
        # Calculate precision, recall, F1
        precision = true_positives / max(total_alerts, 1)
        
        # For recall, we need to estimate total actual positives
        # This is challenging without ground truth, so we use a heuristic
        estimated_actual_positives = true_positives + missed_detections
        recall = true_positives / max(estimated_actual_positives, 1) if estimated_actual_positives > 0 else 0.0
        
        f1_score = (2 * precision * recall) / max(precision + recall, 0.001)
        
        # Alert volume score (penalize too many or too few alerts)
        alert_volume_per_day = total_alerts / max(evaluation_hours / 24, 1)
        if alert_volume_per_day < 0.1:  # Too few alerts
            alert_volume_score = alert_volume_per_day * 10  # Score 0-1
        elif alert_volume_per_day > 50:  # Too many alerts
            alert_volume_score = max(0.1, 50 / alert_volume_per_day)
        else:
            alert_volume_score = 1.0  # Good volume
        
        # Overall performance score
        performance_score = (
            precision * 0.4 +          # 40% weight on precision
            recall * 0.3 +             # 30% weight on recall  
            f1_score * 0.2 +           # 20% weight on F1
            alert_volume_score * 0.1   # 10% weight on volume
        )
        
        metrics = RulePerformanceMetrics(
            rule_id=rule_id,
            evaluation_period=evaluation_period,
            total_alerts=total_alerts,
            true_positives=true_positives,
            false_positives=false_positives,
            benign_positives=benign_positives,
            missed_detections=missed_detections,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            alert_volume_score=alert_volume_score,
            performance_score=performance_score,
            last_updated=datetime.now(),
            feedback_sources=dict(feedback_sources)
        )
        
        self.performance_cache[rule_id] = metrics
        
        logger.debug(f"Rule {rule_id} performance: {performance_score:.3f} "
                    f"(P: {precision:.3f}, R: {recall:.3f}, F1: {f1_score:.3f})")
        
        return metrics
    
    async def analyze_multiple_rules(self, rule_ids: List[str], 
                                   evaluation_hours: int = 168) -> Dict[str, RulePerformanceMetrics]:
        """Analyze performance for multiple rules."""
        
        results = {}
        
        # Analyze rules in parallel
        tasks = [
            self.analyze_rule_performance(rule_id, evaluation_hours)
            for rule_id in rule_ids
        ]
        
        metrics_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(metrics_results):
            rule_id = rule_ids[i]
            if isinstance(result, RulePerformanceMetrics):
                results[rule_id] = result
            elif isinstance(result, Exception):
                logger.error(f"Failed to analyze rule {rule_id}: {result}")
        
        return results
    
    async def identify_problematic_rules(self, 
                                       min_performance_score: float = 0.5,
                                       min_alerts: int = 5) -> List[str]:
        """Identify rules that need attention based on performance."""
        
        problematic_rules = []
        
        for rule_id, metrics in self.performance_cache.items():
            # Skip rules with insufficient data
            if metrics.total_alerts < min_alerts:
                continue
            
            # Check performance thresholds
            if metrics.performance_score < min_performance_score:
                problematic_rules.append(rule_id)
                logger.info(f"Problematic rule identified: {rule_id} "
                           f"(score: {metrics.performance_score:.3f})")
        
        return problematic_rules
    
    async def generate_feedback_report(self, rule_ids: List[str] = None) -> Dict[str, Any]:
        """Generate comprehensive feedback report."""
        
        if rule_ids is None:
            rule_ids = list(self.performance_cache.keys())
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "evaluation_period_hours": 168,
            "total_rules_analyzed": len(rule_ids),
            "rules": {},
            "summary": {
                "avg_performance_score": 0.0,
                "high_performers": [],  # Score > 0.8
                "poor_performers": [],  # Score < 0.5
                "total_feedback_items": 0,
                "feedback_by_type": defaultdict(int),
                "feedback_by_source": defaultdict(int)
            }
        }
        
        total_score = 0.0
        total_feedback = 0
        
        for rule_id in rule_ids:
            if rule_id in self.performance_cache:
                metrics = self.performance_cache[rule_id]
                
                rule_report = {
                    "performance_score": metrics.performance_score,
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1_score": metrics.f1_score,
                    "total_alerts": metrics.total_alerts,
                    "true_positives": metrics.true_positives,
                    "false_positives": metrics.false_positives,
                    "alert_volume_score": metrics.alert_volume_score,
                    "feedback_sources": metrics.feedback_sources,
                    "last_updated": metrics.last_updated.isoformat()
                }
                
                report["rules"][rule_id] = rule_report
                
                # Update summary statistics
                total_score += metrics.performance_score
                total_feedback += len(self.feedback_cache.get(rule_id, []))
                
                if metrics.performance_score > 0.8:
                    report["summary"]["high_performers"].append(rule_id)
                elif metrics.performance_score < 0.5:
                    report["summary"]["poor_performers"].append(rule_id)
                
                # Aggregate feedback types
                for feedback in self.feedback_cache.get(rule_id, []):
                    report["summary"]["feedback_by_type"][feedback.feedback_type.value] += 1
                    report["summary"]["feedback_by_source"][feedback.source] += 1
        
        # Calculate averages
        if rule_ids:
            report["summary"]["avg_performance_score"] = total_score / len(rule_ids)
        
        report["summary"]["total_feedback_items"] = total_feedback
        
        logger.info(f"Generated feedback report for {len(rule_ids)} rules")
        logger.info(f"Average performance score: {report['summary']['avg_performance_score']:.3f}")
        logger.info(f"High performers: {len(report['summary']['high_performers'])}")
        logger.info(f"Poor performers: {len(report['summary']['poor_performers'])}")
        
        return report
    
    async def submit_feedback(self, rule_id: str, alert_id: str, 
                            feedback_type: FeedbackType, 
                            source: str = "analyst",
                            confidence: float = 1.0,
                            incident_id: str = None,
                            analyst_notes: str = None,
                            details: Dict[str, Any] = None) -> bool:
        """Submit feedback for a detection rule."""
        
        try:
            feedback = RuleFeedback(
                feedback_id=f"{alert_id}_{datetime.now().isoformat()}",
                rule_id=rule_id,
                feedback_type=feedback_type,
                timestamp=datetime.now(),
                source=source,
                confidence=confidence,
                alert_id=alert_id,
                incident_id=incident_id,
                analyst_notes=analyst_notes,
                details=details or {}
            )
            
            # Add to cache
            self.feedback_cache[rule_id].append(feedback)
            
            # Store in ClickHouse if available
            if self.clickhouse:
                await self._store_feedback_in_clickhouse(feedback)
            
            logger.info(f"Feedback submitted for rule {rule_id}: {feedback_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            return False
    
    async def _store_feedback_in_clickhouse(self, feedback: RuleFeedback):
        """Store feedback in ClickHouse."""
        
        try:
            insert_query = """
            INSERT INTO alert_feedback (
                feedback_id, rule_id, feedback_type, timestamp, source, 
                confidence, alert_id, incident_id, analyst_notes, details
            ) VALUES (
                %(feedback_id)s, %(rule_id)s, %(feedback_type)s, %(timestamp)s, 
                %(source)s, %(confidence)s, %(alert_id)s, %(incident_id)s, 
                %(analyst_notes)s, %(details)s
            )
            """
            
            await self.clickhouse.insert(insert_query, {
                "feedback_id": feedback.feedback_id,
                "rule_id": feedback.rule_id,
                "feedback_type": feedback.feedback_type.value,
                "timestamp": feedback.timestamp,
                "source": feedback.source,
                "confidence": feedback.confidence,
                "alert_id": feedback.alert_id,
                "incident_id": feedback.incident_id,
                "analyst_notes": feedback.analyst_notes,
                "details": json.dumps(feedback.details)
            })
            
        except Exception as e:
            logger.error(f"Failed to store feedback in ClickHouse: {e}")
    
    def get_rule_feedback_summary(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get feedback summary for a specific rule."""
        
        if rule_id not in self.feedback_cache:
            return None
        
        feedback_list = self.feedback_cache[rule_id]
        
        if not feedback_list:
            return None
        
        # Count feedback types
        type_counts = defaultdict(int)
        source_counts = defaultdict(int)
        
        for feedback in feedback_list:
            type_counts[feedback.feedback_type.value] += 1
            source_counts[feedback.source] += 1
        
        # Get performance metrics if available
        performance = None
        if rule_id in self.performance_cache:
            metrics = self.performance_cache[rule_id]
            performance = {
                "performance_score": metrics.performance_score,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score
            }
        
        return {
            "rule_id": rule_id,
            "total_feedback_items": len(feedback_list),
            "feedback_by_type": dict(type_counts),
            "feedback_by_source": dict(source_counts),
            "latest_feedback": feedback_list[-1].timestamp.isoformat() if feedback_list else None,
            "performance": performance
        }
    
    def clear_cache(self):
        """Clear feedback and performance caches."""
        self.feedback_cache.clear()
        self.performance_cache.clear()
        logger.info("Feedback cache cleared")

# Helper functions for common feedback scenarios
async def submit_false_positive_feedback(feedback_loop: DetectionFeedbackLoop,
                                       rule_id: str, alert_id: str,
                                       analyst_notes: str = None) -> bool:
    """Convenience function for submitting false positive feedback."""
    return await feedback_loop.submit_feedback(
        rule_id=rule_id,
        alert_id=alert_id,
        feedback_type=FeedbackType.FALSE_POSITIVE,
        source="analyst",
        analyst_notes=analyst_notes
    )

async def submit_true_positive_feedback(feedback_loop: DetectionFeedbackLoop,
                                      rule_id: str, alert_id: str,
                                      incident_id: str = None,
                                      analyst_notes: str = None) -> bool:
    """Convenience function for submitting true positive feedback."""
    return await feedback_loop.submit_feedback(
        rule_id=rule_id,
        alert_id=alert_id,
        feedback_type=FeedbackType.TRUE_POSITIVE,
        source="analyst",
        incident_id=incident_id,
        analyst_notes=analyst_notes
    )
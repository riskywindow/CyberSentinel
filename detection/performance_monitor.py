"""Rule Performance Monitor - advanced monitoring and analysis of detection rule effectiveness."""

import asyncio
import logging
import json
import math
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum

# Optional storage import
try:
    from storage.clickhouse_client import ClickHouseClient
except ImportError:
    ClickHouseClient = None

logger = logging.getLogger(__name__)

class PerformanceTrend(Enum):
    """Performance trend indicators."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"

class AlertSeverity(Enum):
    """Alert severity levels for performance issues."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class TimeSeriesPoint:
    """Single point in performance time series."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class PerformanceTrendAnalysis:
    """Analysis of performance trends over time."""
    rule_id: str
    metric_name: str
    trend: PerformanceTrend
    trend_strength: float  # 0.0 to 1.0
    current_value: float
    change_rate: float  # Rate of change per day
    volatility: float  # Standard deviation of values
    time_series: List[TimeSeriesPoint]
    analysis_period: timedelta
    confidence: float
    alerts: List[str] = None
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = []

@dataclass
class RuleHealthMetrics:
    """Comprehensive health metrics for a detection rule."""
    rule_id: str
    overall_health_score: float  # 0.0 to 1.0
    performance_score: float
    reliability_score: float
    efficiency_score: float
    coverage_score: float
    
    # Detailed metrics
    alert_frequency: float  # Alerts per hour
    false_positive_rate: float
    true_positive_rate: float
    mean_time_to_detection: float  # Seconds
    resource_usage_score: float
    
    # Trend analysis
    performance_trend: PerformanceTrend
    trend_confidence: float
    
    # Alert conditions
    health_alerts: List[Dict[str, Any]]
    
    last_updated: datetime
    evaluation_period: timedelta

class RulePerformanceMonitor:
    """Advanced monitoring system for detection rule performance."""
    
    def __init__(self, clickhouse_client = None):
        self.clickhouse = clickhouse_client
        self.performance_history: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        self.health_cache: Dict[str, RuleHealthMetrics] = {}
        self.trend_cache: Dict[str, Dict[str, PerformanceTrendAnalysis]] = defaultdict(dict)
        
        # Performance thresholds
        self.thresholds = {
            "min_performance_score": 0.6,
            "max_false_positive_rate": 0.2,
            "min_true_positive_rate": 0.8,
            "max_alert_frequency": 10.0,  # per hour
            "min_reliability_score": 0.7,
            "max_volatility": 0.3
        }
        
        logger.info("Rule performance monitor initialized")
    
    async def analyze_rule_performance(self, rule_ids: List[str], 
                                     window_hours: int = 168) -> Dict[str, float]:
        """Analyze performance for multiple rules and return performance scores."""
        
        if not self.clickhouse:
            logger.warning("No ClickHouse client available for performance analysis")
            return {}
        
        results = {}
        
        try:
            # Collect performance data for all rules
            await self._collect_performance_data(rule_ids, window_hours)
            
            # Analyze each rule
            for rule_id in rule_ids:
                health_metrics = await self._analyze_rule_health(rule_id, window_hours)
                if health_metrics:
                    results[rule_id] = health_metrics.overall_health_score
                    self.health_cache[rule_id] = health_metrics
            
            logger.info(f"Analyzed performance for {len(results)} rules")
            
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
        
        return results
    
    async def _collect_performance_data(self, rule_ids: List[str], window_hours: int):
        """Collect performance data from ClickHouse."""
        
        lookback_time = datetime.now() - timedelta(hours=window_hours)
        
        # Query for alert metrics
        alert_query = f"""
        SELECT 
            rule_id,
            toStartOfHour(timestamp) as hour_bucket,
            count() as alert_count,
            countIf(feedback_type = 'true_positive') as true_positives,
            countIf(feedback_type = 'false_positive') as false_positives,
            avg(confidence) as avg_confidence,
            avg(processing_time_ms) as avg_processing_time
        FROM alerts a
        LEFT JOIN alert_feedback af ON a.alert_id = af.alert_id
        WHERE a.timestamp >= '{lookback_time.isoformat()}'
        AND rule_id IN ({','.join([f"'{r}'" for r in rule_ids])})
        GROUP BY rule_id, hour_bucket
        ORDER BY rule_id, hour_bucket
        """
        
        alert_results = await self.clickhouse.query(alert_query)
        
        # Organize data by rule
        for row in alert_results:
            rule_id = row["rule_id"]
            hour_bucket = row["hour_bucket"]
            
            # Store alert frequency
            self.performance_history[rule_id]["alert_frequency"].append(
                TimeSeriesPoint(
                    timestamp=hour_bucket,
                    value=float(row["alert_count"]),
                    metadata={"avg_confidence": row["avg_confidence"]}
                )
            )
            
            # Store accuracy metrics
            total_classified = row["true_positives"] + row["false_positives"]
            if total_classified > 0:
                precision = row["true_positives"] / total_classified
                self.performance_history[rule_id]["precision"].append(
                    TimeSeriesPoint(
                        timestamp=hour_bucket,
                        value=precision,
                        metadata={
                            "true_positives": row["true_positives"],
                            "false_positives": row["false_positives"]
                        }
                    )
                )
            
            # Store performance metrics
            if row["avg_processing_time"]:
                self.performance_history[rule_id]["processing_time"].append(
                    TimeSeriesPoint(
                        timestamp=hour_bucket,
                        value=float(row["avg_processing_time"]),
                        metadata={}
                    )
                )
        
        # Collect resource usage data if available
        await self._collect_resource_metrics(rule_ids, lookback_time)
    
    async def _collect_resource_metrics(self, rule_ids: List[str], lookback_time: datetime):
        """Collect resource usage metrics for rules."""
        
        try:
            resource_query = f"""
            SELECT 
                rule_id,
                toStartOfHour(timestamp) as hour_bucket,
                avg(cpu_usage_percent) as avg_cpu,
                avg(memory_usage_mb) as avg_memory,
                avg(query_duration_ms) as avg_query_duration
            FROM rule_resource_usage
            WHERE timestamp >= '{lookback_time.isoformat()}'
            AND rule_id IN ({','.join([f"'{r}'" for r in rule_ids])})
            GROUP BY rule_id, hour_bucket
            ORDER BY rule_id, hour_bucket
            """
            
            resource_results = await self.clickhouse.query(resource_query)
            
            for row in resource_results:
                rule_id = row["rule_id"]
                hour_bucket = row["hour_bucket"]
                
                # Combine CPU and memory into efficiency score
                cpu_score = max(0, 1.0 - (row["avg_cpu"] / 100.0))  # Lower CPU is better
                memory_score = max(0, 1.0 - (row["avg_memory"] / 1000.0))  # Lower memory is better
                efficiency = (cpu_score + memory_score) / 2.0
                
                self.performance_history[rule_id]["efficiency"].append(
                    TimeSeriesPoint(
                        timestamp=hour_bucket,
                        value=efficiency,
                        metadata={
                            "cpu_usage": row["avg_cpu"],
                            "memory_usage": row["avg_memory"],
                            "query_duration": row["avg_query_duration"]
                        }
                    )
                )
        
        except Exception as e:
            logger.debug(f"Resource metrics not available: {e}")
    
    async def _analyze_rule_health(self, rule_id: str, window_hours: int) -> Optional[RuleHealthMetrics]:
        """Analyze comprehensive health metrics for a rule."""
        
        if rule_id not in self.performance_history:
            return None
        
        rule_data = self.performance_history[rule_id]
        evaluation_period = timedelta(hours=window_hours)
        
        # Calculate component scores
        performance_score = self._calculate_performance_score(rule_data)
        reliability_score = self._calculate_reliability_score(rule_data)
        efficiency_score = self._calculate_efficiency_score(rule_data)
        coverage_score = self._calculate_coverage_score(rule_data)
        
        # Calculate detailed metrics
        alert_frequency = self._calculate_alert_frequency(rule_data["alert_frequency"])
        false_positive_rate = self._calculate_false_positive_rate(rule_data["precision"])
        true_positive_rate = self._calculate_true_positive_rate(rule_data["precision"])
        mean_time_to_detection = self._calculate_mtd(rule_data)
        resource_usage_score = efficiency_score
        
        # Analyze trends
        performance_trend_analysis = await self._analyze_performance_trend(rule_id, rule_data)
        
        # Overall health score (weighted combination)
        overall_health_score = (
            performance_score * 0.3 +
            reliability_score * 0.25 +
            efficiency_score * 0.2 +
            coverage_score * 0.25
        )
        
        # Generate health alerts
        health_alerts = self._generate_health_alerts(
            rule_id, performance_score, reliability_score, 
            efficiency_score, false_positive_rate, alert_frequency
        )
        
        health_metrics = RuleHealthMetrics(
            rule_id=rule_id,
            overall_health_score=overall_health_score,
            performance_score=performance_score,
            reliability_score=reliability_score,
            efficiency_score=efficiency_score,
            coverage_score=coverage_score,
            alert_frequency=alert_frequency,
            false_positive_rate=false_positive_rate,
            true_positive_rate=true_positive_rate,
            mean_time_to_detection=mean_time_to_detection,
            resource_usage_score=resource_usage_score,
            performance_trend=performance_trend_analysis.trend if performance_trend_analysis else PerformanceTrend.STABLE,
            trend_confidence=performance_trend_analysis.confidence if performance_trend_analysis else 0.0,
            health_alerts=health_alerts,
            last_updated=datetime.now(),
            evaluation_period=evaluation_period
        )
        
        return health_metrics
    
    def _calculate_performance_score(self, rule_data: Dict[str, deque]) -> float:
        """Calculate overall performance score."""
        
        precision_data = rule_data.get("precision", deque())
        if not precision_data:
            return 0.5  # Neutral score if no data
        
        # Recent performance weighted more heavily
        recent_points = list(precision_data)[-24:]  # Last 24 hours
        if not recent_points:
            return 0.5
        
        recent_avg = sum(p.value for p in recent_points) / len(recent_points)
        return min(1.0, max(0.0, recent_avg))
    
    def _calculate_reliability_score(self, rule_data: Dict[str, deque]) -> float:
        """Calculate reliability score based on consistency."""
        
        precision_data = rule_data.get("precision", deque())
        if len(precision_data) < 5:
            return 0.5  # Need minimum data for reliability assessment
        
        values = [p.value for p in precision_data]
        
        # Calculate variance (lower variance = higher reliability)
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        
        # Convert to reliability score (0 std dev = 1.0 reliability)
        reliability = max(0.0, 1.0 - (std_dev * 2))  # Scale factor
        return min(1.0, reliability)
    
    def _calculate_efficiency_score(self, rule_data: Dict[str, deque]) -> float:
        """Calculate efficiency score based on resource usage."""
        
        efficiency_data = rule_data.get("efficiency", deque())
        if not efficiency_data:
            return 0.8  # Assume good efficiency if no data
        
        recent_points = list(efficiency_data)[-24:]  # Last 24 hours
        if not recent_points:
            return 0.8
        
        avg_efficiency = sum(p.value for p in recent_points) / len(recent_points)
        return min(1.0, max(0.0, avg_efficiency))
    
    def _calculate_coverage_score(self, rule_data: Dict[str, deque]) -> float:
        """Calculate coverage score based on alert patterns."""
        
        alert_freq_data = rule_data.get("alert_frequency", deque())
        if not alert_freq_data:
            return 0.5
        
        # Coverage is about having appropriate alert frequency
        # Too few alerts = poor coverage, too many = noise
        recent_points = list(alert_freq_data)[-24:]
        if not recent_points:
            return 0.5
        
        avg_frequency = sum(p.value for p in recent_points) / len(recent_points)
        
        # Optimal range: 0.5 - 5 alerts per hour
        if 0.5 <= avg_frequency <= 5.0:
            coverage = 1.0
        elif avg_frequency < 0.5:
            coverage = avg_frequency / 0.5  # Scale down for low frequency
        else:
            coverage = max(0.1, 5.0 / avg_frequency)  # Scale down for high frequency
        
        return min(1.0, max(0.0, coverage))
    
    def _calculate_alert_frequency(self, alert_freq_data: deque) -> float:
        """Calculate average alert frequency per hour."""
        
        if not alert_freq_data:
            return 0.0
        
        total_alerts = sum(p.value for p in alert_freq_data)
        total_hours = len(alert_freq_data)
        
        return total_alerts / max(total_hours, 1)
    
    def _calculate_false_positive_rate(self, precision_data: deque) -> float:
        """Calculate false positive rate."""
        
        if not precision_data:
            return 0.0
        
        # False positive rate = 1 - precision
        recent_precision = sum(p.value for p in list(precision_data)[-24:])
        recent_count = len(list(precision_data)[-24:])
        
        if recent_count == 0:
            return 0.0
        
        avg_precision = recent_precision / recent_count
        return max(0.0, 1.0 - avg_precision)
    
    def _calculate_true_positive_rate(self, precision_data: deque) -> float:
        """Calculate true positive rate (approximation)."""
        
        if not precision_data:
            return 0.0
        
        # For simplicity, use precision as proxy for TPR
        # In practice, would need additional data
        recent_precision = sum(p.value for p in list(precision_data)[-24:])
        recent_count = len(list(precision_data)[-24:])
        
        if recent_count == 0:
            return 0.0
        
        return recent_precision / recent_count
    
    def _calculate_mtd(self, rule_data: Dict[str, deque]) -> float:
        """Calculate mean time to detection."""
        
        processing_time_data = rule_data.get("processing_time", deque())
        if not processing_time_data:
            return 300.0  # Default 5 minutes
        
        recent_times = [p.value for p in list(processing_time_data)[-24:]]
        if not recent_times:
            return 300.0
        
        # Convert from milliseconds to seconds
        return (sum(recent_times) / len(recent_times)) / 1000.0
    
    async def _analyze_performance_trend(self, rule_id: str, 
                                       rule_data: Dict[str, deque]) -> Optional[PerformanceTrendAnalysis]:
        """Analyze performance trends over time."""
        
        precision_data = rule_data.get("precision", deque())
        if len(precision_data) < 10:  # Need minimum data points
            return None
        
        time_series = list(precision_data)[-72:]  # Last 72 hours
        if len(time_series) < 10:
            return None
        
        values = [p.value for p in time_series]
        timestamps = [p.timestamp for p in time_series]
        
        # Calculate trend using linear regression
        n = len(values)
        x_values = list(range(n))
        
        # Calculate slope
        sum_x = sum(x_values)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_values, values))
        sum_x2 = sum(x * x for x in x_values)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Calculate volatility (standard deviation)
        mean_val = sum_y / n
        variance = sum((v - mean_val) ** 2 for v in values) / n
        volatility = math.sqrt(variance)
        
        # Determine trend
        if abs(slope) < 0.001:  # Very small slope
            trend = PerformanceTrend.STABLE
        elif volatility > 0.2:  # High volatility
            trend = PerformanceTrend.VOLATILE
        elif slope > 0.001:
            trend = PerformanceTrend.IMPROVING
        else:
            trend = PerformanceTrend.DECLINING
        
        # Calculate trend strength
        trend_strength = min(1.0, abs(slope) * 100)  # Scale slope to 0-1
        
        # Calculate confidence based on data consistency
        confidence = max(0.0, 1.0 - (volatility * 2))
        
        # Convert daily change rate
        hours_per_point = 1.0  # Assuming hourly data
        change_rate = slope * 24 / hours_per_point  # Per day
        
        analysis = PerformanceTrendAnalysis(
            rule_id=rule_id,
            metric_name="precision",
            trend=trend,
            trend_strength=trend_strength,
            current_value=values[-1],
            change_rate=change_rate,
            volatility=volatility,
            time_series=time_series,
            analysis_period=timedelta(hours=len(time_series)),
            confidence=confidence
        )
        
        self.trend_cache[rule_id]["precision"] = analysis
        
        return analysis
    
    def _generate_health_alerts(self, rule_id: str, performance_score: float,
                              reliability_score: float, efficiency_score: float,
                              false_positive_rate: float, alert_frequency: float) -> List[Dict[str, Any]]:
        """Generate health alerts based on thresholds."""
        
        alerts = []
        
        # Performance alerts
        if performance_score < self.thresholds["min_performance_score"]:
            alerts.append({
                "severity": AlertSeverity.HIGH.value,
                "type": "low_performance",
                "message": f"Rule performance score ({performance_score:.3f}) below threshold ({self.thresholds['min_performance_score']})",
                "metric": "performance_score",
                "value": performance_score,
                "threshold": self.thresholds["min_performance_score"]
            })
        
        # False positive alerts
        if false_positive_rate > self.thresholds["max_false_positive_rate"]:
            alerts.append({
                "severity": AlertSeverity.MEDIUM.value,
                "type": "high_false_positives",
                "message": f"False positive rate ({false_positive_rate:.3f}) above threshold ({self.thresholds['max_false_positive_rate']})",
                "metric": "false_positive_rate",
                "value": false_positive_rate,
                "threshold": self.thresholds["max_false_positive_rate"]
            })
        
        # Alert frequency alerts
        if alert_frequency > self.thresholds["max_alert_frequency"]:
            alerts.append({
                "severity": AlertSeverity.MEDIUM.value,
                "type": "high_alert_frequency",
                "message": f"Alert frequency ({alert_frequency:.1f}/hour) above threshold ({self.thresholds['max_alert_frequency']})",
                "metric": "alert_frequency",
                "value": alert_frequency,
                "threshold": self.thresholds["max_alert_frequency"]
            })
        
        # Reliability alerts
        if reliability_score < self.thresholds["min_reliability_score"]:
            alerts.append({
                "severity": AlertSeverity.LOW.value,
                "type": "low_reliability",
                "message": f"Reliability score ({reliability_score:.3f}) below threshold ({self.thresholds['min_reliability_score']})",
                "metric": "reliability_score",
                "value": reliability_score,
                "threshold": self.thresholds["min_reliability_score"]
            })
        
        return alerts
    
    async def get_rule_health_report(self, rule_ids: List[str] = None) -> Dict[str, Any]:
        """Generate comprehensive health report for rules."""
        
        if rule_ids is None:
            rule_ids = list(self.health_cache.keys())
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_rules": len(rule_ids),
            "rules": {},
            "summary": {
                "healthy_rules": 0,
                "warning_rules": 0,
                "critical_rules": 0,
                "avg_health_score": 0.0,
                "total_alerts": 0
            }
        }
        
        total_health_score = 0.0
        
        for rule_id in rule_ids:
            if rule_id in self.health_cache:
                health = self.health_cache[rule_id]
                
                rule_report = asdict(health)
                rule_report["last_updated"] = health.last_updated.isoformat()
                rule_report["evaluation_period"] = str(health.evaluation_period)
                
                report["rules"][rule_id] = rule_report
                
                # Update summary
                total_health_score += health.overall_health_score
                report["summary"]["total_alerts"] += len(health.health_alerts)
                
                if health.overall_health_score >= 0.8:
                    report["summary"]["healthy_rules"] += 1
                elif health.overall_health_score >= 0.6:
                    report["summary"]["warning_rules"] += 1
                else:
                    report["summary"]["critical_rules"] += 1
        
        if rule_ids:
            report["summary"]["avg_health_score"] = total_health_score / len(rule_ids)
        
        return report
    
    def get_performance_thresholds(self) -> Dict[str, float]:
        """Get current performance thresholds."""
        return self.thresholds.copy()
    
    def update_performance_thresholds(self, new_thresholds: Dict[str, float]):
        """Update performance thresholds."""
        self.thresholds.update(new_thresholds)
        logger.info(f"Updated performance thresholds: {new_thresholds}")
    
    def clear_caches(self):
        """Clear all performance caches."""
        self.performance_history.clear()
        self.health_cache.clear()
        self.trend_cache.clear()
        logger.info("Performance monitor caches cleared")
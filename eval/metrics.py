"""Evaluation Metrics - comprehensive scoring and analysis for detection effectiveness."""

import asyncio
import logging
import math
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
import statistics

from eval.framework import EvaluationRun, EvaluationScenario

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of evaluation metrics."""
    DETECTION_ACCURACY = "detection_accuracy"
    RESPONSE_TIME = "response_time"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    COVERAGE = "coverage"
    EFFICIENCY = "efficiency"
    RELIABILITY = "reliability"

@dataclass
class MetricResult:
    """Result of a single metric calculation."""
    metric_name: str
    metric_type: MetricType
    value: float
    max_value: float
    normalized_score: float  # 0.0 to 1.0
    unit: str
    description: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}

@dataclass
class EvaluationScore:
    """Comprehensive evaluation score."""
    overall_score: float
    category_scores: Dict[str, float]
    metric_results: List[MetricResult]
    grade: str  # A, B, C, D, F
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    timestamp: datetime
    
@dataclass
class BenchmarkResult:
    """Result comparing performance against benchmarks."""
    metric_name: str
    current_value: float
    benchmark_value: float
    percentile: float  # 0-100
    comparison: str  # "above", "below", "at" benchmark
    improvement_needed: float

class EvaluationMetrics:
    """Calculates comprehensive metrics for evaluation results."""
    
    def __init__(self):
        # Metric calculators
        self.metric_calculators = {
            MetricType.DETECTION_ACCURACY: self._calculate_detection_accuracy,
            MetricType.RESPONSE_TIME: self._calculate_response_time,
            MetricType.FALSE_POSITIVE_RATE: self._calculate_false_positive_rate,
            MetricType.COVERAGE: self._calculate_coverage,
            MetricType.EFFICIENCY: self._calculate_efficiency,
            MetricType.RELIABILITY: self._calculate_reliability
        }
        
        # Scoring weights for overall score
        self.metric_weights = {
            MetricType.DETECTION_ACCURACY: 0.25,
            MetricType.RESPONSE_TIME: 0.20,
            MetricType.FALSE_POSITIVE_RATE: 0.20,
            MetricType.COVERAGE: 0.15,
            MetricType.EFFICIENCY: 0.10,
            MetricType.RELIABILITY: 0.10
        }
        
        # Benchmark values (industry standards)
        self.benchmarks = {
            "detection_accuracy": 0.85,    # 85% detection rate
            "response_time_seconds": 300,   # 5 minutes
            "false_positive_rate": 0.05,   # 5% false positive rate
            "coverage_percentage": 0.80,   # 80% technique coverage
            "efficiency_score": 0.75,      # 75% efficiency
            "reliability_score": 0.90      # 90% reliability
        }
        
        logger.info("Evaluation metrics calculator initialized")
    
    async def calculate_metrics(self, evaluation_run: EvaluationRun, 
                              scenario: EvaluationScenario) -> Dict[str, float]:
        """Calculate all metrics for an evaluation run."""
        
        metrics = {}
        
        try:
            # Calculate each metric type
            for metric_type in MetricType:
                if metric_type in self.metric_calculators:
                    calculator = self.metric_calculators[metric_type]
                    result = await calculator(evaluation_run, scenario)
                    metrics[metric_type.value] = result.normalized_score
            
            logger.info(f"Calculated {len(metrics)} metrics for run {evaluation_run.run_id}")
            
        except Exception as e:
            logger.error(f"Failed to calculate metrics: {e}")
            # Return default metrics on failure
            metrics = {metric_type.value: 0.0 for metric_type in MetricType}
        
        return metrics
    
    async def calculate_comprehensive_score(self, evaluation_run: EvaluationRun,
                                          scenario: EvaluationScenario) -> EvaluationScore:
        """Calculate comprehensive evaluation score with detailed analysis."""
        
        metric_results = []
        
        # Calculate all metrics
        for metric_type in MetricType:
            if metric_type in self.metric_calculators:
                calculator = self.metric_calculators[metric_type]
                result = await calculator(evaluation_run, scenario)
                metric_results.append(result)
        
        # Calculate category scores
        category_scores = {}
        for metric_result in metric_results:
            category = metric_result.metric_type.value
            category_scores[category] = metric_result.normalized_score
        
        # Calculate overall score (weighted average)
        overall_score = 0.0
        total_weight = 0.0
        
        for metric_result in metric_results:
            weight = self.metric_weights.get(metric_result.metric_type, 0.1)
            overall_score += metric_result.normalized_score * weight
            total_weight += weight
        
        if total_weight > 0:
            overall_score /= total_weight
        
        # Determine grade
        grade = self._calculate_grade(overall_score)
        
        # Analyze strengths and weaknesses
        strengths, weaknesses = self._analyze_performance(metric_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metric_results, scenario)
        
        score = EvaluationScore(
            overall_score=overall_score,
            category_scores=category_scores,
            metric_results=metric_results,
            grade=grade,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
        
        logger.info(f"Calculated comprehensive score: {overall_score:.3f} (Grade: {grade})")
        
        return score
    
    async def _calculate_detection_accuracy(self, evaluation_run: EvaluationRun,
                                          scenario: EvaluationScenario) -> MetricResult:
        """Calculate detection accuracy metrics."""
        
        results = evaluation_run.results or {}
        
        # Extract detection data
        detections_triggered = results.get("detections_triggered", 0)
        expected_detections = len(scenario.expected_detections) if scenario.expected_detections else len(scenario.steps)
        
        # Calculate accuracy
        if expected_detections > 0:
            accuracy = detections_triggered / expected_detections
        else:
            accuracy = 1.0  # Perfect score if no detections expected
        
        # Normalize to 0-1 scale
        normalized_score = min(1.0, accuracy)
        
        return MetricResult(
            metric_name="Detection Accuracy",
            metric_type=MetricType.DETECTION_ACCURACY,
            value=accuracy,
            max_value=1.0,
            normalized_score=normalized_score,
            unit="ratio",
            description="Ratio of triggered detections to expected detections",
            details={
                "detections_triggered": detections_triggered,
                "expected_detections": expected_detections,
                "detection_rate": accuracy
            }
        )
    
    async def _calculate_response_time(self, evaluation_run: EvaluationRun,
                                     scenario: EvaluationScenario) -> MetricResult:
        """Calculate response time metrics."""
        
        results = evaluation_run.results or {}
        
        # Get execution time
        execution_time = results.get("execution_time_seconds", 0)
        
        # Target response time (5 minutes for most scenarios)
        target_time = 300  # 5 minutes
        
        # Calculate response time score (inverse relationship)
        if execution_time <= target_time:
            response_score = 1.0
        else:
            # Diminishing returns for longer times
            response_score = target_time / execution_time
        
        normalized_score = max(0.0, min(1.0, response_score))
        
        return MetricResult(
            metric_name="Response Time",
            metric_type=MetricType.RESPONSE_TIME,
            value=execution_time,
            max_value=target_time,
            normalized_score=normalized_score,
            unit="seconds",
            description="Time to complete detection and response",
            details={
                "execution_time_seconds": execution_time,
                "target_time_seconds": target_time,
                "response_score": response_score
            }
        )
    
    async def _calculate_false_positive_rate(self, evaluation_run: EvaluationRun,
                                           scenario: EvaluationScenario) -> MetricResult:
        """Calculate false positive rate."""
        
        results = evaluation_run.results or {}
        
        # Extract false positive data
        false_positives = results.get("false_positives", 0)
        total_alerts = results.get("alerts_generated", 1)
        
        # Calculate false positive rate
        fp_rate = false_positives / max(total_alerts, 1)
        
        # Score is inverse of FP rate (lower is better)
        fp_score = 1.0 - fp_rate
        normalized_score = max(0.0, min(1.0, fp_score))
        
        return MetricResult(
            metric_name="False Positive Rate",
            metric_type=MetricType.FALSE_POSITIVE_RATE,
            value=fp_rate,
            max_value=1.0,
            normalized_score=normalized_score,
            unit="ratio",
            description="Ratio of false positive alerts to total alerts",
            details={
                "false_positives": false_positives,
                "total_alerts": total_alerts,
                "false_positive_rate": fp_rate
            }
        )
    
    async def _calculate_coverage(self, evaluation_run: EvaluationRun,
                                scenario: EvaluationScenario) -> MetricResult:
        """Calculate technique/attack coverage."""
        
        results = evaluation_run.results or {}
        
        # Extract coverage data
        coverage_percentage = results.get("coverage_percentage", 0) / 100.0
        steps_completed = len(results.get("steps_completed", []))
        total_steps = len(scenario.steps)
        
        # Calculate step completion coverage
        step_coverage = steps_completed / max(total_steps, 1)
        
        # Use the better of the two coverage metrics
        final_coverage = max(coverage_percentage, step_coverage)
        normalized_score = min(1.0, final_coverage)
        
        return MetricResult(
            metric_name="Coverage",
            metric_type=MetricType.COVERAGE,
            value=final_coverage,
            max_value=1.0,
            normalized_score=normalized_score,
            unit="ratio",
            description="Coverage of attack techniques and scenarios",
            details={
                "coverage_percentage": coverage_percentage,
                "steps_completed": steps_completed,
                "total_steps": total_steps,
                "step_coverage": step_coverage
            }
        )
    
    async def _calculate_efficiency(self, evaluation_run: EvaluationRun,
                                  scenario: EvaluationScenario) -> MetricResult:
        """Calculate detection efficiency."""
        
        results = evaluation_run.results or {}
        
        # Calculate efficiency based on resource usage and time
        execution_time = results.get("execution_time_seconds", 1)
        detections_triggered = results.get("detections_triggered", 0)
        
        # Efficiency: detections per unit time
        detection_rate = detections_triggered / max(execution_time, 1)
        
        # Normalize based on expected rate (1 detection per 60 seconds is good)
        target_rate = 1.0 / 60.0  # 1 detection per minute
        efficiency_score = min(1.0, detection_rate / target_rate)
        
        normalized_score = max(0.0, efficiency_score)
        
        return MetricResult(
            metric_name="Efficiency",
            metric_type=MetricType.EFFICIENCY,
            value=detection_rate,
            max_value=target_rate,
            normalized_score=normalized_score,
            unit="detections/second",
            description="Efficiency of detection system (detections per unit time)",
            details={
                "detection_rate": detection_rate,
                "target_rate": target_rate,
                "execution_time": execution_time,
                "detections_triggered": detections_triggered
            }
        )
    
    async def _calculate_reliability(self, evaluation_run: EvaluationRun,
                                   scenario: EvaluationScenario) -> MetricResult:
        """Calculate detection reliability."""
        
        results = evaluation_run.results or {}
        
        # Calculate reliability based on consistency and error rate
        steps_completed = len(results.get("steps_completed", []))
        total_steps = len(scenario.steps)
        
        # Basic reliability: successful completion rate
        completion_rate = steps_completed / max(total_steps, 1)
        
        # Adjust for errors
        error_count = len([step for step in results.get("step_details", []) if step.get("error")])
        error_rate = error_count / max(total_steps, 1)
        
        # Reliability score
        reliability_score = completion_rate * (1.0 - error_rate * 0.5)
        normalized_score = max(0.0, min(1.0, reliability_score))
        
        return MetricResult(
            metric_name="Reliability",
            metric_type=MetricType.RELIABILITY,
            value=reliability_score,
            max_value=1.0,
            normalized_score=normalized_score,
            unit="ratio",
            description="Reliability and consistency of detection system",
            details={
                "completion_rate": completion_rate,
                "error_rate": error_rate,
                "steps_completed": steps_completed,
                "total_steps": total_steps,
                "error_count": error_count
            }
        )
    
    def _calculate_grade(self, overall_score: float) -> str:
        """Calculate letter grade from overall score."""
        
        if overall_score >= 0.90:
            return "A"
        elif overall_score >= 0.80:
            return "B"
        elif overall_score >= 0.70:
            return "C"
        elif overall_score >= 0.60:
            return "D"
        else:
            return "F"
    
    def _analyze_performance(self, metric_results: List[MetricResult]) -> Tuple[List[str], List[str]]:
        """Analyze performance to identify strengths and weaknesses."""
        
        strengths = []
        weaknesses = []
        
        for metric in metric_results:
            if metric.normalized_score >= 0.85:
                strengths.append(f"Excellent {metric.metric_name.lower()} ({metric.normalized_score:.1%})")
            elif metric.normalized_score >= 0.70:
                strengths.append(f"Good {metric.metric_name.lower()} ({metric.normalized_score:.1%})")
            elif metric.normalized_score <= 0.50:
                weaknesses.append(f"Poor {metric.metric_name.lower()} ({metric.normalized_score:.1%})")
            elif metric.normalized_score <= 0.70:
                weaknesses.append(f"Below average {metric.metric_name.lower()} ({metric.normalized_score:.1%})")
        
        return strengths, weaknesses
    
    def _generate_recommendations(self, metric_results: List[MetricResult],
                                scenario: EvaluationScenario) -> List[str]:
        """Generate recommendations for improvement."""
        
        recommendations = []
        
        for metric in metric_results:
            if metric.normalized_score < 0.70:
                if metric.metric_type == MetricType.DETECTION_ACCURACY:
                    recommendations.append("Improve detection rule sensitivity and coverage")
                    recommendations.append("Review and tune detection thresholds")
                elif metric.metric_type == MetricType.RESPONSE_TIME:
                    recommendations.append("Optimize detection pipeline performance")
                    recommendations.append("Implement automated response workflows")
                elif metric.metric_type == MetricType.FALSE_POSITIVE_RATE:
                    recommendations.append("Refine detection rules to reduce false positives")
                    recommendations.append("Implement better context-aware filtering")
                elif metric.metric_type == MetricType.COVERAGE:
                    recommendations.append("Expand detection rule coverage for additional techniques")
                    recommendations.append("Review and update detection strategy")
                elif metric.metric_type == MetricType.EFFICIENCY:
                    recommendations.append("Optimize resource usage and processing efficiency")
                    recommendations.append("Implement performance monitoring and alerting")
                elif metric.metric_type == MetricType.RELIABILITY:
                    recommendations.append("Improve system stability and error handling")
                    recommendations.append("Implement redundancy and failover mechanisms")
        
        # Add general recommendations
        if len([m for m in metric_results if m.normalized_score < 0.70]) > 2:
            recommendations.append("Consider comprehensive security architecture review")
            recommendations.append("Implement continuous testing and validation processes")
        
        return list(set(recommendations))  # Remove duplicates
    
    async def compare_to_benchmarks(self, evaluation_score: EvaluationScore) -> List[BenchmarkResult]:
        """Compare results to industry benchmarks."""
        
        benchmark_results = []
        
        for metric in evaluation_score.metric_results:
            # Get benchmark value for this metric
            benchmark_key = f"{metric.metric_type.value}_{metric.unit}" if metric.unit != "ratio" else metric.metric_type.value
            if benchmark_key not in self.benchmarks:
                benchmark_key = metric.metric_type.value
            
            if benchmark_key in self.benchmarks:
                benchmark_value = self.benchmarks[benchmark_key]
                current_value = metric.value
                
                # Calculate percentile (simplified)
                if metric.metric_type in [MetricType.FALSE_POSITIVE_RATE]:
                    # Lower is better
                    percentile = max(0, 100 * (1 - current_value / benchmark_value))
                    comparison = "above" if current_value < benchmark_value else "below"
                else:
                    # Higher is better
                    percentile = min(100, 100 * current_value / benchmark_value)
                    comparison = "above" if current_value > benchmark_value else "below"
                
                if abs(current_value - benchmark_value) / benchmark_value < 0.05:
                    comparison = "at"
                
                # Calculate improvement needed
                if comparison == "below":
                    improvement_needed = benchmark_value - current_value
                else:
                    improvement_needed = 0.0
                
                result = BenchmarkResult(
                    metric_name=metric.metric_name,
                    current_value=current_value,
                    benchmark_value=benchmark_value,
                    percentile=percentile,
                    comparison=comparison,
                    improvement_needed=improvement_needed
                )
                
                benchmark_results.append(result)
        
        return benchmark_results
    
    async def calculate_trend_analysis(self, evaluation_runs: List[EvaluationRun],
                                     scenarios: Dict[str, EvaluationScenario]) -> Dict[str, Any]:
        """Calculate trend analysis across multiple evaluation runs."""
        
        if len(evaluation_runs) < 2:
            return {"error": "Need at least 2 evaluation runs for trend analysis"}
        
        # Sort runs by start time
        sorted_runs = sorted(evaluation_runs, key=lambda x: x.start_time)
        
        # Calculate metrics for each run
        metric_trends = defaultdict(list)
        
        for run in sorted_runs:
            scenario = scenarios.get(run.scenario_id)
            if scenario:
                metrics = await self.calculate_metrics(run, scenario)
                
                for metric_name, value in metrics.items():
                    metric_trends[metric_name].append({
                        "timestamp": run.start_time.isoformat(),
                        "value": value,
                        "run_id": run.run_id
                    })
        
        # Calculate trends
        trend_analysis = {}
        
        for metric_name, values in metric_trends.items():
            if len(values) >= 2:
                # Calculate trend direction and strength
                y_values = [point["value"] for point in values]
                x_values = list(range(len(y_values)))
                
                # Simple linear regression
                n = len(values)
                sum_x = sum(x_values)
                sum_y = sum(y_values)
                sum_xy = sum(x * y for x, y in zip(x_values, y_values))
                sum_x2 = sum(x * x for x in x_values)
                
                if n * sum_x2 - sum_x * sum_x != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                    
                    # Determine trend
                    if abs(slope) < 0.01:
                        trend = "stable"
                    elif slope > 0:
                        trend = "improving"
                    else:
                        trend = "declining"
                    
                    # Calculate statistics
                    avg_value = statistics.mean(y_values)
                    std_dev = statistics.stdev(y_values) if len(y_values) > 1 else 0
                    
                    trend_analysis[metric_name] = {
                        "trend": trend,
                        "slope": slope,
                        "average": avg_value,
                        "std_deviation": std_dev,
                        "min_value": min(y_values),
                        "max_value": max(y_values),
                        "latest_value": y_values[-1],
                        "data_points": values
                    }
        
        return trend_analysis
    
    def set_benchmarks(self, new_benchmarks: Dict[str, float]):
        """Update benchmark values."""
        self.benchmarks.update(new_benchmarks)
        logger.info(f"Updated benchmarks: {new_benchmarks}")
    
    def set_metric_weights(self, new_weights: Dict[MetricType, float]):
        """Update metric weights for overall scoring."""
        self.metric_weights.update(new_weights)
        logger.info(f"Updated metric weights: {new_weights}")
    
    def export_metrics_summary(self, evaluation_scores: List[EvaluationScore]) -> Dict[str, Any]:
        """Export summary of multiple evaluation scores."""
        
        if not evaluation_scores:
            return {"error": "No evaluation scores provided"}
        
        # Calculate aggregate statistics
        overall_scores = [score.overall_score for score in evaluation_scores]
        grades = [score.grade for score in evaluation_scores]
        
        # Grade distribution
        grade_counts = defaultdict(int)
        for grade in grades:
            grade_counts[grade] += 1
        
        # Category averages
        category_averages = defaultdict(list)
        for score in evaluation_scores:
            for category, value in score.category_scores.items():
                category_averages[category].append(value)
        
        avg_category_scores = {
            category: statistics.mean(values)
            for category, values in category_averages.items()
        }
        
        summary = {
            "total_evaluations": len(evaluation_scores),
            "average_overall_score": statistics.mean(overall_scores),
            "median_overall_score": statistics.median(overall_scores),
            "score_std_deviation": statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0,
            "min_score": min(overall_scores),
            "max_score": max(overall_scores),
            "grade_distribution": dict(grade_counts),
            "category_averages": avg_category_scores,
            "evaluation_period": {
                "start": min(score.timestamp for score in evaluation_scores).isoformat(),
                "end": max(score.timestamp for score in evaluation_scores).isoformat()
            }
        }
        
        return summary
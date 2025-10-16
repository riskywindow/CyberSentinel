"""CyberSentinel Evaluation Harness Module.

This module implements a comprehensive evaluation framework for testing detection capabilities:
1. Scenario runner for standardized attack simulations
2. Replay engine for repeatable evaluations  
3. Metrics calculation and scoring
4. Integration with detection and red team systems
5. Report generation and analytics
"""

from eval.framework import EvaluationFramework
from eval.scenario_runner import ScenarioRunner
from eval.replay_engine import ReplayEngine
from eval.metrics import EvaluationMetrics
from eval.reporter import EvaluationReporter

__all__ = [
    "EvaluationFramework",
    "ScenarioRunner", 
    "ReplayEngine",
    "EvaluationMetrics",
    "EvaluationReporter"
]
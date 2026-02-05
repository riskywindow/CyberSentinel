"""
Detector adapter for RL environment.

Provides detection signals from either the real evaluation harness or a fast stub.
"""

import time
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path


class DetectorAdapter:
    """
    Adapter to provide detection signals to the RL environment.

    Supports two modes:
    - Stub mode: Fast, deterministic detection based on technique metadata
    - Real mode: Calls into the evaluation harness for actual detection
    """

    # Technique detection rules (stub mode)
    # Maps technique_id -> base detection probability
    DETECTION_RULES: Dict[str, float] = {
        "T1566.001": 0.4,   # Spearphishing - medium detection
        "T1190": 0.5,       # Exploit public app - medium-high
        "T1059.003": 0.6,   # Command shell - high (noisy)
        "T1053.005": 0.3,   # Scheduled task - lower
        "T1055": 0.2,       # Process injection - stealthy
        "T1003.001": 0.5,   # LSASS dump - medium (well-known)
        "T1083": 0.2,       # File discovery - low
        "T1135": 0.3,       # Network share discovery - medium-low
        "T1021.001": 0.4,   # RDP - medium
        "T1021.004": 0.3,   # SSH - lower
        "T1005": 0.2,       # Data from local - low
        "T1041": 0.4,       # Exfil over C2 - medium
    }

    # Simulated latency ranges (ms) per technique
    LATENCY_RANGES: Dict[str, tuple] = {
        "T1566.001": (50, 200),
        "T1190": (100, 500),
        "T1059.003": (10, 50),
        "T1053.005": (20, 100),
        "T1055": (5, 30),
        "T1003.001": (30, 150),
        "T1083": (5, 20),
        "T1135": (20, 80),
        "T1021.001": (50, 200),
        "T1021.004": (30, 100),
        "T1005": (10, 50),
        "T1041": (100, 500),
    }

    def __init__(self, use_real: bool = False, seed: Optional[int] = None):
        """
        Initialize detector adapter.

        Args:
            use_real: If True, use real evaluation harness. If False, use stub.
            seed: Random seed for deterministic stub behavior.
        """
        self.use_real = use_real
        self._seed = seed
        self._call_count = 0
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Initialize real detector if needed
        self._real_detector = None
        if use_real:
            self._init_real_detector()

    def _init_real_detector(self):
        """Initialize the real evaluation harness."""
        try:
            # Try to import evaluation harness
            from eval.harness import EvaluationHarness
            self._real_detector = EvaluationHarness()
        except ImportError:
            # Fallback to stub if harness not available
            self.use_real = False
            self._real_detector = None

    def evaluate(self, technique_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether a technique execution is detected.

        Args:
            technique_id: ATT&CK technique ID (e.g., "T1566.001")
            context: Execution context with keys like:
                - step: Current step number
                - phase: Current campaign phase
                - stealth_score: Agent's stealth level
                - security_level: Target's security maturity

        Returns:
            Dict with keys:
                - detected: bool - Whether the technique was detected
                - latency_ms: int - Detection latency in milliseconds
                - extra: dict - Additional detection metadata
        """
        self._call_count += 1

        # Check cache for repeated evaluations
        cache_key = self._make_cache_key(technique_id, context)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.use_real and self._real_detector is not None:
            result = self._evaluate_real(technique_id, context)
        else:
            result = self._evaluate_stub(technique_id, context)

        # Cache result
        self._cache[cache_key] = result
        return result

    def _make_cache_key(self, technique_id: str, context: Dict[str, Any]) -> str:
        """Create cache key from technique and context."""
        # Include relevant context fields that affect detection
        key_parts = [
            technique_id,
            str(context.get("step", 0)),
            str(context.get("phase", 0)),
            f"{context.get('security_level', 0.5):.2f}",
        ]
        return "|".join(key_parts)

    def _evaluate_stub(self, technique_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fast stub detection based on rules."""
        # Get base detection probability
        base_prob = self.DETECTION_RULES.get(technique_id, 0.3)

        # Adjust for context
        security_level = context.get("security_level", 0.5)
        stealth_score = context.get("stealth_score", 1.0)
        step = context.get("step", 0)

        # Detection probability increases with security level
        adjusted_prob = base_prob * (0.5 + security_level)

        # Stealth score reduces detection
        adjusted_prob *= (1.0 - stealth_score * 0.3)

        # Later steps slightly more likely to be detected
        adjusted_prob *= (1.0 + step * 0.02)

        # Cap probability
        adjusted_prob = min(0.95, max(0.05, adjusted_prob))

        # Deterministic detection based on seed and call count
        if self._seed is not None:
            # Create deterministic hash
            hash_input = f"{self._seed}:{technique_id}:{self._call_count}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
            random_val = (hash_val % 10000) / 10000.0
        else:
            import random
            random_val = random.random()

        detected = random_val < adjusted_prob

        # Calculate latency
        latency_range = self.LATENCY_RANGES.get(technique_id, (10, 100))
        if self._seed is not None:
            hash_input = f"{self._seed}:latency:{technique_id}:{self._call_count}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
            latency_frac = (hash_val % 10000) / 10000.0
        else:
            import random
            latency_frac = random.random()

        latency_ms = int(latency_range[0] + latency_frac * (latency_range[1] - latency_range[0]))

        return {
            "detected": detected,
            "latency_ms": latency_ms,
            "extra": {
                "detection_prob": adjusted_prob,
                "rule_matched": f"rule_{technique_id}" if detected else None,
                "stub_mode": True,
            }
        }

    def _evaluate_real(self, technique_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate using real detection harness."""
        start_time = time.time()

        try:
            # Call into evaluation harness
            # This would need to be adapted to your actual harness interface
            result = self._real_detector.detect_technique(
                technique_id=technique_id,
                context=context
            )

            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "detected": result.get("detected", False),
                "latency_ms": latency_ms,
                "extra": {
                    "rule_matched": result.get("rule_id"),
                    "confidence": result.get("confidence", 0.0),
                    "stub_mode": False,
                }
            }
        except Exception as e:
            # Fallback to stub on error
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "detected": False,
                "latency_ms": latency_ms,
                "extra": {
                    "error": str(e),
                    "stub_mode": True,
                }
            }

    def reset(self, seed: Optional[int] = None):
        """Reset adapter state for new episode."""
        if seed is not None:
            self._seed = seed
        self._call_count = 0
        self._cache.clear()

    @property
    def call_count(self) -> int:
        """Number of evaluate() calls since last reset."""
        return self._call_count

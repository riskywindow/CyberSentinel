"""
Gym-like RL environment for training adversary agents.

Provides a simplified attack simulation environment where an agent selects
ATT&CK techniques to progress through a campaign while avoiding detection.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

from .detector_adapter import DetectorAdapter


class Phase(IntEnum):
    """Campaign phases mapped to integers for observation space."""
    INITIAL_ACCESS = 0
    EXECUTION = 1
    PERSISTENCE = 2
    PRIVILEGE_ESCALATION = 3
    CREDENTIAL_ACCESS = 4
    DISCOVERY = 5
    LATERAL_MOVEMENT = 6
    COLLECTION = 7
    EXFILTRATION = 8
    IMPACT = 9


@dataclass
class EnvConfig:
    """Configuration for the attack environment."""
    # Action space: subset of ATT&CK techniques for fast training
    techniques: List[str] = field(default_factory=lambda: [
        "T1566.001",  # Spearphishing Attachment (initial-access)
        "T1190",      # Exploit Public-Facing Application (initial-access)
        "T1059.003",  # Windows Command Shell (execution)
        "T1053.005",  # Scheduled Task (persistence)
        "T1055",      # Process Injection (privilege-escalation)
        "T1003.001",  # LSASS Memory (credential-access)
        "T1083",      # File and Directory Discovery (discovery)
        "T1135",      # Network Share Discovery (discovery)
        "T1021.001",  # RDP (lateral-movement)
        "T1021.004",  # SSH (lateral-movement)
        "T1005",      # Data from Local System (collection)
        "T1041",      # Exfiltration Over C2 (exfiltration)
    ])

    # Technique metadata: phase, difficulty, stealth, impact
    technique_meta: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "T1566.001": {"phase": 0, "difficulty": 0.4, "stealth": 0.6, "impact": 0.8},
        "T1190":     {"phase": 0, "difficulty": 0.6, "stealth": 0.5, "impact": 0.9},
        "T1059.003": {"phase": 1, "difficulty": 0.2, "stealth": 0.3, "impact": 0.7},
        "T1053.005": {"phase": 2, "difficulty": 0.4, "stealth": 0.7, "impact": 0.6},
        "T1055":     {"phase": 3, "difficulty": 0.7, "stealth": 0.8, "impact": 0.8},
        "T1003.001": {"phase": 4, "difficulty": 0.6, "stealth": 0.5, "impact": 0.9},
        "T1083":     {"phase": 5, "difficulty": 0.2, "stealth": 0.6, "impact": 0.3},
        "T1135":     {"phase": 5, "difficulty": 0.3, "stealth": 0.5, "impact": 0.4},
        "T1021.001": {"phase": 6, "difficulty": 0.4, "stealth": 0.4, "impact": 0.8},
        "T1021.004": {"phase": 6, "difficulty": 0.3, "stealth": 0.6, "impact": 0.8},
        "T1005":     {"phase": 7, "difficulty": 0.3, "stealth": 0.7, "impact": 0.8},
        "T1041":     {"phase": 8, "difficulty": 0.4, "stealth": 0.7, "impact": 0.9},
    })

    # Environment parameters
    max_steps: int = 12
    detection_threshold: float = 3.0  # Cumulative detection score before lockout
    security_level: float = 0.5  # Target environment security maturity [0,1]

    # Reward shaping (updated for detector-based rewards)
    advance_no_detect_reward: float = 3.0   # Step advances campaign without detection
    objective_complete_reward: float = 6.0  # Objective completes undetected
    detected_stealth_reward: float = 2.0    # Detected while aiming for stealth (failure record)
    step_cost: float = -0.1                 # Small negative per step
    wasted_action_penalty: float = -0.5     # Action that doesn't advance state
    lockout_penalty: float = -5.0           # Terminal penalty for lockout

    # Legacy rewards (kept for backwards compatibility)
    objective_reward: float = 10.0
    detection_penalty: float = -1.0
    progress_reward: float = 0.5
    stealth_bonus: float = 0.2

    # Detector settings
    use_real_detector: bool = False


class AttackEnv:
    """
    Gym-like environment for training adversary agents.

    State space (9 dimensions):
        - current_phase: int [0-9]
        - steps_taken: int [0-max_steps]
        - detection_score: float [0-threshold]
        - has_initial_access: bool
        - has_persistence: bool
        - has_credentials: bool
        - has_lateral_access: bool
        - has_collected_data: bool
        - stealth_score: float [0-1]

    Action space: discrete, len(techniques)

    Rewards (detector-based):
        - +3 for step that advances without detection
        - +6 for objective completion without detection
        - +2 if detected while aiming for stealth (recorded as failure)
        - -0.1 step cost
        - -0.5 for wasted actions
        - -5.0 for lockout
    """

    def __init__(self, config: Optional[EnvConfig] = None):
        self.config = config or EnvConfig()
        self.techniques = self.config.techniques
        self.n_actions = len(self.techniques)
        self.obs_dim = 9

        # Initialize detector
        self._detector = DetectorAdapter(
            use_real=self.config.use_real_detector,
            seed=None  # Will be set on reset
        )

        # Internal state
        self._rng: Optional[np.random.Generator] = None
        self._seed: Optional[int] = None
        self._current_phase: int = 0
        self._steps_taken: int = 0
        self._detection_score: float = 0.0
        self._has_initial_access: bool = False
        self._has_persistence: bool = False
        self._has_credentials: bool = False
        self._has_lateral_access: bool = False
        self._has_collected_data: bool = False
        self._stealth_score: float = 1.0
        self._done: bool = False
        self._executed_techniques: List[str] = []
        self._last_detection_latency: int = 0

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset the environment to initial state.

        Args:
            seed: Random seed for reproducibility

        Returns:
            Tuple of (initial observation, info dict with action mask)
        """
        if seed is not None:
            self._seed = seed
            self._rng = np.random.default_rng(seed)
        elif self._rng is None:
            self._rng = np.random.default_rng()

        # Reset detector with seed
        self._detector.reset(seed=self._seed)

        self._current_phase = Phase.INITIAL_ACCESS
        self._steps_taken = 0
        self._detection_score = 0.0
        self._has_initial_access = False
        self._has_persistence = False
        self._has_credentials = False
        self._has_lateral_access = False
        self._has_collected_data = False
        self._stealth_score = 1.0
        self._done = False
        self._executed_techniques = []
        self._last_detection_latency = 0

        obs = self._get_obs()
        info = {
            "action_mask": self.get_action_mask(),
            "phase": int(self._current_phase),
        }
        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.

        Args:
            action: Index into techniques list

        Returns:
            Tuple of (observation, reward, done, info)
        """
        if self._done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")

        if action < 0 or action >= self.n_actions:
            raise ValueError(f"Invalid action {action}. Must be in [0, {self.n_actions})")

        technique_id = self.techniques[action]
        meta = self.config.technique_meta[technique_id]
        mask = self.get_action_mask()
        action_masked = not mask[action]

        # Calculate success probability based on difficulty and prerequisites
        success_prob = self._calculate_success_prob(technique_id, meta)
        success = self._rng.random() < success_prob

        # Use detector to determine detection
        detector_context = {
            "step": self._steps_taken,
            "phase": int(self._current_phase),
            "stealth_score": self._stealth_score,
            "security_level": self.config.security_level,
            "success": success,
        }
        detection_result = self._detector.evaluate(technique_id, detector_context)
        detected = detection_result["detected"]
        latency_ms = detection_result["latency_ms"]
        self._last_detection_latency = latency_ms

        # Track state before action
        old_phase = self._current_phase
        old_state = self._get_state_tuple()

        # Initialize reward with step cost
        reward = self.config.step_cost

        info = {
            "technique": technique_id,
            "action_id": action,
            "success": success,
            "detected": detected,
            "latency_ms": latency_ms,
            "phase": int(self._current_phase),
            "action_masked": action_masked,
            "detection_extra": detection_result.get("extra", {}),
        }

        # Process execution result
        if success:
            self._executed_techniques.append(technique_id)
            self._update_state_on_success(technique_id, meta)

            # Check if state actually advanced
            new_state = self._get_state_tuple()
            state_advanced = new_state != old_state

            if state_advanced:
                if not detected:
                    # +3 for advancing without detection
                    reward += self.config.advance_no_detect_reward
                    info["reward_type"] = "advance_undetected"
                else:
                    # +2 for detected while trying stealth (failure record)
                    reward += self.config.detected_stealth_reward
                    info["reward_type"] = "detected_stealth_failure"
            else:
                # Wasted action - didn't advance state
                reward += self.config.wasted_action_penalty
                info["reward_type"] = "wasted_action"

            # Check for objective completion
            if self._check_objective_complete():
                if not detected:
                    reward += self.config.objective_complete_reward
                    info["reward_type"] = "objective_complete_undetected"
                self._done = True
                info["objective_complete"] = True
        else:
            # Failed action
            reward += self.config.wasted_action_penalty
            info["reward_type"] = "action_failed"

        # Process detection score
        if detected:
            detection_amount = (1.0 - meta["stealth"]) * self.config.security_level
            self._detection_score += detection_amount
            self._stealth_score = max(0.0, self._stealth_score - 0.1)
            info["detection_amount"] = detection_amount

            # Check for lockout
            if self._detection_score >= self.config.detection_threshold:
                reward += self.config.lockout_penalty
                self._done = True
                info["locked_out"] = True
                info["reward_type"] = "lockout"

        # Increment step counter
        self._steps_taken += 1
        if self._steps_taken >= self.config.max_steps and not self._done:
            self._done = True
            info["timeout"] = True

        # Include updated action mask in info
        info["action_mask"] = self.get_action_mask()

        return self._get_obs(), reward, self._done, info

    def _get_state_tuple(self) -> tuple:
        """Get hashable state tuple for comparison."""
        return (
            self._current_phase,
            self._has_initial_access,
            self._has_persistence,
            self._has_credentials,
            self._has_lateral_access,
            self._has_collected_data,
        )

    def _get_obs(self) -> np.ndarray:
        """Construct observation vector."""
        return np.array([
            float(self._current_phase) / 9.0,  # Normalized phase
            float(self._steps_taken) / self.config.max_steps,  # Normalized steps
            self._detection_score / self.config.detection_threshold,  # Normalized detection
            float(self._has_initial_access),
            float(self._has_persistence),
            float(self._has_credentials),
            float(self._has_lateral_access),
            float(self._has_collected_data),
            self._stealth_score,
        ], dtype=np.float32)

    def _calculate_success_prob(self, technique_id: str, meta: Dict[str, float]) -> float:
        """Calculate probability of technique success."""
        base_prob = 1.0 - meta["difficulty"]
        tech_phase = int(meta["phase"])

        # Initial access techniques always possible
        if tech_phase == Phase.INITIAL_ACCESS:
            return base_prob

        # Execution requires initial access
        if tech_phase == Phase.EXECUTION and not self._has_initial_access:
            return base_prob * 0.3

        # Persistence requires execution (initial access as proxy)
        if tech_phase == Phase.PERSISTENCE and not self._has_initial_access:
            return base_prob * 0.2

        # Privilege escalation requires execution
        if tech_phase == Phase.PRIVILEGE_ESCALATION and not self._has_initial_access:
            return base_prob * 0.2

        # Credential access benefits from privilege escalation
        if tech_phase == Phase.CREDENTIAL_ACCESS:
            if not self._has_initial_access:
                return base_prob * 0.1

        # Lateral movement requires credentials
        if tech_phase == Phase.LATERAL_MOVEMENT:
            if not self._has_credentials:
                return base_prob * 0.3
            return base_prob * 1.2  # Bonus with credentials

        # Collection requires lateral access or initial access
        if tech_phase == Phase.COLLECTION:
            if not self._has_initial_access:
                return base_prob * 0.1

        # Exfiltration requires collected data
        if tech_phase == Phase.EXFILTRATION:
            if not self._has_collected_data:
                return base_prob * 0.1

        return min(1.0, base_prob)

    def _update_state_on_success(self, technique_id: str, meta: Dict[str, float]):
        """Update internal state after successful technique execution."""
        tech_phase = int(meta["phase"])

        if tech_phase == Phase.INITIAL_ACCESS:
            self._has_initial_access = True
            self._current_phase = max(self._current_phase, Phase.EXECUTION)

        elif tech_phase == Phase.EXECUTION:
            self._current_phase = max(self._current_phase, Phase.PERSISTENCE)

        elif tech_phase == Phase.PERSISTENCE:
            self._has_persistence = True
            self._current_phase = max(self._current_phase, Phase.PRIVILEGE_ESCALATION)

        elif tech_phase == Phase.PRIVILEGE_ESCALATION:
            self._current_phase = max(self._current_phase, Phase.CREDENTIAL_ACCESS)

        elif tech_phase == Phase.CREDENTIAL_ACCESS:
            self._has_credentials = True
            self._current_phase = max(self._current_phase, Phase.DISCOVERY)

        elif tech_phase == Phase.DISCOVERY:
            self._current_phase = max(self._current_phase, Phase.LATERAL_MOVEMENT)

        elif tech_phase == Phase.LATERAL_MOVEMENT:
            self._has_lateral_access = True
            self._current_phase = max(self._current_phase, Phase.COLLECTION)

        elif tech_phase == Phase.COLLECTION:
            self._has_collected_data = True
            self._current_phase = max(self._current_phase, Phase.EXFILTRATION)

        elif tech_phase == Phase.EXFILTRATION:
            self._current_phase = Phase.EXFILTRATION

    def _check_objective_complete(self) -> bool:
        """Check if campaign objective is complete."""
        return (
            self._has_initial_access and
            self._has_collected_data and
            "T1041" in self._executed_techniques
        )

    def get_action_mask(self) -> np.ndarray:
        """
        Get mask of valid actions based on current state.

        Returns:
            Boolean array where True indicates valid action
        """
        mask = np.ones(self.n_actions, dtype=bool)

        for i, tech_id in enumerate(self.techniques):
            meta = self.config.technique_meta[tech_id]
            tech_phase = int(meta["phase"])

            # Initial access: always valid at start, skip if we have access
            if tech_phase == Phase.INITIAL_ACCESS:
                if self._has_initial_access:
                    mask[i] = False  # No need for more initial access
                continue

            # Execution: requires initial access
            if tech_phase == Phase.EXECUTION:
                if not self._has_initial_access:
                    mask[i] = False
                continue

            # Persistence: requires initial access
            if tech_phase == Phase.PERSISTENCE:
                if not self._has_initial_access:
                    mask[i] = False
                elif self._has_persistence:
                    mask[i] = False  # Already have persistence
                continue

            # Privilege escalation: requires initial access
            if tech_phase == Phase.PRIVILEGE_ESCALATION:
                if not self._has_initial_access:
                    mask[i] = False
                continue

            # Credential access: requires initial access
            if tech_phase == Phase.CREDENTIAL_ACCESS:
                if not self._has_initial_access:
                    mask[i] = False
                elif self._has_credentials:
                    mask[i] = False  # Already have credentials
                continue

            # Discovery: requires initial access
            if tech_phase == Phase.DISCOVERY:
                if not self._has_initial_access:
                    mask[i] = False
                continue

            # Lateral movement: requires credentials
            if tech_phase == Phase.LATERAL_MOVEMENT:
                if not self._has_credentials:
                    mask[i] = False
                elif self._has_lateral_access:
                    mask[i] = False  # Already have lateral access
                continue

            # Collection: requires initial access
            if tech_phase == Phase.COLLECTION:
                if not self._has_initial_access:
                    mask[i] = False
                elif self._has_collected_data:
                    mask[i] = False  # Already collected data
                continue

            # Exfiltration: requires collected data
            if tech_phase == Phase.EXFILTRATION:
                if not self._has_collected_data:
                    mask[i] = False
                continue

        # Ensure at least one action is valid
        if not np.any(mask):
            mask[:] = True

        return mask

    @property
    def observation_space_shape(self) -> Tuple[int]:
        """Return observation space shape."""
        return (self.obs_dim,)

    @property
    def action_space_n(self) -> int:
        """Return number of actions."""
        return self.n_actions

    def render(self) -> str:
        """Render current state as string."""
        phase_names = [p.name for p in Phase]
        current_phase_name = phase_names[self._current_phase] if self._current_phase < len(phase_names) else "UNKNOWN"

        return (
            f"Phase: {current_phase_name} | "
            f"Steps: {self._steps_taken}/{self.config.max_steps} | "
            f"Detection: {self._detection_score:.2f}/{self.config.detection_threshold:.2f} | "
            f"Access: {self._has_initial_access} | "
            f"Creds: {self._has_credentials} | "
            f"Data: {self._has_collected_data} | "
            f"Stealth: {self._stealth_score:.2f}"
        )

    def get_technique_name(self, action: int) -> str:
        """Get technique ID for an action index."""
        if 0 <= action < len(self.techniques):
            return self.techniques[action]
        return "UNKNOWN"

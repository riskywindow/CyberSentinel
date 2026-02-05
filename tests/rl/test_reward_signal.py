"""
Test reward signal from detector adapter.

Verifies that:
- DetectorAdapter.evaluate() returns dict with 'detected' and 'latency_ms'
- Rewards have expected structure and monotonicity properties
"""

import pytest
import numpy as np

from redteam.envs import AttackEnv, EnvConfig, DetectorAdapter


class TestDetectorAdapter:
    """Test DetectorAdapter interface and behavior."""

    def test_evaluate_returns_required_keys(self):
        """evaluate() should return dict with detected, latency_ms, and extra."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        result = adapter.evaluate("T1566.001", {"step": 0, "phase": 0})

        assert "detected" in result
        assert "latency_ms" in result
        assert "extra" in result

    def test_detected_is_bool(self):
        """detected should be a boolean."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        result = adapter.evaluate("T1566.001", {"step": 0, "phase": 0})

        assert isinstance(result["detected"], bool)

    def test_latency_is_int(self):
        """latency_ms should be an integer."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        result = adapter.evaluate("T1566.001", {"step": 0, "phase": 0})

        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0

    def test_extra_is_dict(self):
        """extra should be a dictionary."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        result = adapter.evaluate("T1566.001", {"step": 0, "phase": 0})

        assert isinstance(result["extra"], dict)

    def test_stub_mode_indicated(self):
        """Stub mode should be indicated in extra."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        result = adapter.evaluate("T1566.001", {"step": 0, "phase": 0})

        assert result["extra"].get("stub_mode") == True

    def test_deterministic_with_seed(self):
        """Same seed should produce same detection results."""
        adapter1 = DetectorAdapter(use_real=False, seed=42)
        adapter2 = DetectorAdapter(use_real=False, seed=42)

        result1 = adapter1.evaluate("T1566.001", {"step": 0, "phase": 0})
        result2 = adapter2.evaluate("T1566.001", {"step": 0, "phase": 0})

        assert result1["detected"] == result2["detected"]
        assert result1["latency_ms"] == result2["latency_ms"]

    def test_different_techniques_different_probs(self):
        """Different techniques should have different detection characteristics."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        # Run many evaluations to get statistical behavior
        noisy_detections = 0  # T1059.003 (command shell) - noisy
        stealthy_detections = 0  # T1055 (process injection) - stealthy

        for i in range(100):
            adapter.reset(seed=i)
            r1 = adapter.evaluate("T1059.003", {"step": 0})
            adapter.reset(seed=i)
            r2 = adapter.evaluate("T1055", {"step": 0})

            if r1["detected"]:
                noisy_detections += 1
            if r2["detected"]:
                stealthy_detections += 1

        # Noisy technique should be detected more often
        assert noisy_detections > stealthy_detections

    def test_reset_clears_state(self):
        """reset() should clear internal state."""
        adapter = DetectorAdapter(use_real=False, seed=42)

        # Make some calls
        adapter.evaluate("T1566.001", {"step": 0})
        adapter.evaluate("T1566.001", {"step": 1})
        assert adapter.call_count == 2

        # Reset
        adapter.reset(seed=43)
        assert adapter.call_count == 0


class TestRewardStructure:
    """Test reward structure from environment."""

    def test_step_cost_always_applied(self):
        """Step cost should be applied to every step."""
        config = EnvConfig(step_cost=-0.1)
        env = AttackEnv(config)
        env.reset(seed=42)

        # Any action should include step cost
        _, reward, _, _ = env.step(0)

        # Reward should be at most step_cost (could be lower with penalties)
        # or higher with bonuses, but step_cost is always part of it
        # We can't directly test this, but we can verify reward is not zero
        assert reward != 0

    def test_advance_without_detection_positive(self):
        """Advancing without detection should give positive reward."""
        config = EnvConfig(
            advance_no_detect_reward=3.0,
            step_cost=-0.1,
        )
        env = AttackEnv(config)
        env.reset(seed=42)

        # Try initial access multiple times to get a successful undetected advance
        total_reward = 0
        for i in range(100):
            env.reset(seed=42 + i)
            obs, reward, done, info = env.step(0)  # Initial access attempt

            if info.get("success") and not info.get("detected"):
                # Should have positive reward (advance_no_detect - step_cost)
                assert reward > 0, f"Expected positive reward, got {reward}"
                break
        else:
            pytest.skip("Could not get undetected advance in 100 tries")

    def test_lockout_gives_large_penalty(self):
        """Lockout should give a large negative reward."""
        config = EnvConfig(
            lockout_penalty=-5.0,
            detection_threshold=0.1,  # Very low threshold
        )
        env = AttackEnv(config)

        # Find a seed that causes lockout
        for seed in range(100):
            env.reset(seed=seed)
            for _ in range(12):
                _, reward, done, info = env.step(2)  # Noisy technique
                if info.get("locked_out"):
                    # Should have large penalty
                    assert reward < -3.0, f"Expected large penalty, got {reward}"
                    return
                if done:
                    break

        pytest.skip("Could not trigger lockout in 100 seeds")

    def test_reward_info_contains_type(self):
        """Info should contain reward_type."""
        env = AttackEnv()
        env.reset(seed=42)

        _, _, _, info = env.step(0)

        assert "reward_type" in info
        assert info["reward_type"] in [
            "advance_undetected",
            "detected_stealth_failure",
            "wasted_action",
            "action_failed",
            "objective_complete_undetected",
            "lockout",
        ]


class TestRewardMonotonicity:
    """Test reward monotonicity on scripted episodes."""

    def test_successful_campaign_has_high_reward(self):
        """A successful campaign should have higher total reward than failed one."""
        env = AttackEnv()

        # Scripted successful path: initial access -> creds -> collect -> exfil
        # We'll run many seeds and check the ones that succeed vs fail
        successful_rewards = []
        failed_rewards = []

        for seed in range(50):
            env.reset(seed=seed)
            total_reward = 0
            success = False

            # Try a reasonable attack path
            for action in [0, 5, 10, 11]:  # initial, creds, collect, exfil
                _, reward, done, info = env.step(action)
                total_reward += reward
                if info.get("objective_complete"):
                    success = True
                if done:
                    break

            if success:
                successful_rewards.append(total_reward)
            else:
                failed_rewards.append(total_reward)

        # Successful campaigns should have higher average reward
        if len(successful_rewards) > 0 and len(failed_rewards) > 0:
            assert np.mean(successful_rewards) > np.mean(failed_rewards)
        # If no successful or failed campaigns, skip the test
        elif len(successful_rewards) == 0:
            pytest.skip("No successful campaigns in test")

    def test_progress_accumulates_positive_reward(self):
        """Making progress should accumulate positive reward contributions."""
        env = AttackEnv()
        env.reset(seed=42)

        # Track rewards per step
        rewards = []
        for _ in range(12):
            mask = env.get_action_mask()
            valid = np.where(mask)[0]
            action = valid[0] if len(valid) > 0 else 0

            _, reward, done, info = env.step(action)
            rewards.append(reward)

            if done:
                break

        # Should have at least some positive rewards (from progress)
        positive_rewards = [r for r in rewards if r > 0]
        assert len(positive_rewards) > 0, "Expected at least one positive reward"


class TestDetectorIntegration:
    """Test detector integration with environment."""

    def test_detection_info_in_step(self):
        """Step info should include detection results."""
        env = AttackEnv()
        env.reset(seed=42)

        _, _, _, info = env.step(0)

        assert "detected" in info
        assert "latency_ms" in info
        assert isinstance(info["detected"], bool)
        assert isinstance(info["latency_ms"], int)

    def test_detection_extra_available(self):
        """Detection extra info should be available."""
        env = AttackEnv()
        env.reset(seed=42)

        _, _, _, info = env.step(0)

        assert "detection_extra" in info
        assert isinstance(info["detection_extra"], dict)

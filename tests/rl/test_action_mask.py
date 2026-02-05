"""
Test action masking functionality.

Verifies that:
- reset() and step() return action masks in info dict
- Masks hide at least one action for non-initial phases
- Sampled actions never violate the mask
"""

import pytest
import numpy as np

from redteam.envs import AttackEnv, EnvConfig
from redteam.policy import PolicyNetwork, ActorCriticNetwork


class TestActionMaskInInfo:
    """Test that action masks are returned in info dict."""

    def test_reset_returns_mask(self):
        """reset() should return action_mask in info dict."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        assert "action_mask" in info
        mask = info["action_mask"]
        assert isinstance(mask, np.ndarray)
        assert mask.dtype == bool
        assert mask.shape == (env.n_actions,)

    def test_step_returns_mask(self):
        """step() should return action_mask in info dict."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        # Take a step
        obs, reward, done, info = env.step(0)

        assert "action_mask" in info
        mask = info["action_mask"]
        assert isinstance(mask, np.ndarray)
        assert mask.dtype == bool
        assert mask.shape == (env.n_actions,)


class TestMaskHidesActions:
    """Test that masks properly hide invalid actions."""

    def test_initial_phase_allows_initial_access(self):
        """Initial phase should allow initial access techniques."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)
        mask = info["action_mask"]

        # T1566.001 (action 0) and T1190 (action 1) are initial access
        assert mask[0] == True or mask[1] == True

    def test_non_initial_phase_masks_some_actions(self):
        """After advancing, some actions should be masked."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        # Try to get initial access first
        for _ in range(5):
            obs, reward, done, info = env.step(0)  # Try spearphishing
            if env._has_initial_access:
                break

        # Now check the mask
        mask = info["action_mask"]

        # After initial access, initial access techniques should be masked
        # T1566.001 (action 0) and T1190 (action 1)
        assert mask[0] == False or mask[1] == False

        # But at least some actions should still be valid
        assert np.sum(mask) > 0

    def test_exfiltration_masked_without_data(self):
        """Exfiltration should be masked until data is collected."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        # T1041 (exfiltration) is action 11
        exfil_idx = env.techniques.index("T1041")
        mask = info["action_mask"]

        # Without collected data, exfiltration should be masked
        assert mask[exfil_idx] == False

    def test_lateral_movement_masked_without_credentials(self):
        """Lateral movement should be masked until credentials acquired."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        # T1021.001 (RDP) and T1021.004 (SSH) are lateral movement
        rdp_idx = env.techniques.index("T1021.001")
        ssh_idx = env.techniques.index("T1021.004")
        mask = info["action_mask"]

        # Without credentials, lateral movement should be masked
        assert mask[rdp_idx] == False
        assert mask[ssh_idx] == False

    def test_mask_at_least_one_hidden_after_progress(self):
        """After making progress, at least one action should be masked."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        # Make some progress
        for _ in range(10):
            mask = info["action_mask"]
            valid_actions = np.where(mask)[0]
            if len(valid_actions) == 0:
                break
            action = np.random.choice(valid_actions)
            obs, reward, done, info = env.step(action)
            if done:
                break

        # After progress, we should have some masked actions
        # (either initial access is masked, or we're locked out)
        final_mask = info.get("action_mask", env.get_action_mask())

        # If not done, there should be at least one masked action
        # after we've progressed past initial access
        if not done and env._has_initial_access:
            assert np.sum(~final_mask) > 0, "Expected at least one masked action"


class TestSamplingRespectsaMask:
    """Test that policy sampling respects action masks."""

    def test_policy_network_respects_mask(self):
        """PolicyNetwork sampling should never return masked actions."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        policy = PolicyNetwork(obs_dim=env.obs_dim, n_actions=env.n_actions, use_torch=False)
        rng = np.random.default_rng(42)

        # Create restrictive mask (only allow first 3 actions)
        mask = np.array([True, True, True] + [False] * (env.n_actions - 3))

        # Sample 100 times and verify
        for _ in range(100):
            action, _ = policy.sample_action(obs, mask, rng)
            assert action in [0, 1, 2], f"Action {action} violates mask"

    def test_actor_critic_respects_mask(self):
        """ActorCriticNetwork sampling should never return masked actions."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        network = ActorCriticNetwork(obs_dim=env.obs_dim, n_actions=env.n_actions, use_torch=False)
        rng = np.random.default_rng(42)

        # Create restrictive mask (only allow actions 5-7)
        mask = np.array([False] * 5 + [True, True, True] + [False] * (env.n_actions - 8))

        # Sample 100 times and verify
        for _ in range(100):
            action, _, _ = network.sample_action(obs, mask, rng)
            assert action in [5, 6, 7], f"Action {action} violates mask"

    def test_sampling_in_episode_respects_mask(self):
        """During an episode, sampled actions should respect the mask."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)
        mask = info["action_mask"]

        policy = PolicyNetwork(obs_dim=env.obs_dim, n_actions=env.n_actions, use_torch=False)
        rng = np.random.default_rng(42)

        for _ in range(12):
            action, _ = policy.sample_action(obs, mask, rng)

            # Action should be allowed by mask
            assert mask[action] == True, f"Action {action} was masked but selected"

            obs, reward, done, info = env.step(action)
            mask = info.get("action_mask", env.get_action_mask())

            if done:
                break

    def test_masked_probs_near_zero(self):
        """Masked actions should have near-zero probability."""
        env = AttackEnv()
        obs, info = env.reset(seed=42)

        policy = PolicyNetwork(obs_dim=env.obs_dim, n_actions=env.n_actions, use_torch=False)

        # Create mask that disallows most actions
        mask = np.array([True, False, False, True, False, False,
                         False, False, False, False, False, False])

        probs = policy.get_action_probs(obs, mask)

        # Masked actions should have near-zero probability
        for i, allowed in enumerate(mask):
            if not allowed:
                assert probs[i] < 1e-6, f"Masked action {i} has prob {probs[i]}"

        # Probabilities should still sum to 1
        np.testing.assert_almost_equal(np.sum(probs), 1.0, decimal=5)


class TestMaskDeterminism:
    """Test that masks are deterministic."""

    def test_same_seed_same_mask_sequence(self):
        """Same seed should produce same mask sequence."""
        env = AttackEnv()

        # First run
        obs1, info1 = env.reset(seed=42)
        masks1 = [info1["action_mask"].copy()]
        for _ in range(5):
            obs1, _, done, info1 = env.step(0)
            masks1.append(info1["action_mask"].copy())
            if done:
                break

        # Second run with same seed
        obs2, info2 = env.reset(seed=42)
        masks2 = [info2["action_mask"].copy()]
        for _ in range(5):
            obs2, _, done, info2 = env.step(0)
            masks2.append(info2["action_mask"].copy())
            if done:
                break

        # Masks should be identical
        for i, (m1, m2) in enumerate(zip(masks1, masks2)):
            np.testing.assert_array_equal(m1, m2, err_msg=f"Mask {i} differs")

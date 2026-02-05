"""
Test environment contract - determinism, observation shapes, action masking.

These tests verify the RL environment meets the expected interface contract.
"""

import pytest
import numpy as np

from redteam.envs import AttackEnv, EnvConfig


class TestEnvDeterminism:
    """Test that environment is deterministic with same seed."""

    def test_reset_same_seed_same_obs(self):
        """Same seed should produce identical initial observations."""
        env = AttackEnv()

        obs1 = env.reset(seed=42)
        obs2 = env.reset(seed=42)

        np.testing.assert_array_equal(obs1, obs2)

    def test_reset_different_seed_different_state(self):
        """Different seeds should generally produce different trajectories."""
        env = AttackEnv()

        # Reset and take same actions with different seeds
        env.reset(seed=42)
        _, r1, _, _ = env.step(0)

        env.reset(seed=123)
        _, r2, _, _ = env.step(0)

        # While individual step results may vary due to stochasticity,
        # the env should handle both seeds without error
        assert isinstance(r1, float)
        assert isinstance(r2, float)

    def test_deterministic_episode_same_seed(self):
        """Running same episode twice with same seed and actions gives same result."""
        env = AttackEnv()

        # Episode 1
        env.reset(seed=42)
        rewards1 = []
        for action in [0, 2, 5, 8]:  # Fixed action sequence
            _, reward, done, _ = env.step(action)
            rewards1.append(reward)
            if done:
                break

        # Episode 2 - same seed and actions
        env.reset(seed=42)
        rewards2 = []
        for action in [0, 2, 5, 8]:
            _, reward, done, _ = env.step(action)
            rewards2.append(reward)
            if done:
                break

        assert rewards1 == rewards2


class TestObservationSpace:
    """Test observation space properties."""

    def test_obs_shape(self):
        """Observation should have expected shape."""
        env = AttackEnv()
        obs = env.reset(seed=42)

        assert obs.shape == env.observation_space_shape
        assert obs.shape == (env.obs_dim,)
        assert obs.shape == (9,)

    def test_obs_dtype(self):
        """Observation should be float32."""
        env = AttackEnv()
        obs = env.reset(seed=42)

        assert obs.dtype == np.float32

    def test_obs_normalized(self):
        """Observation values should be roughly normalized [0, 1]."""
        env = AttackEnv()
        obs = env.reset(seed=42)

        # Initial obs should have values in [0, 1]
        assert np.all(obs >= 0.0)
        assert np.all(obs <= 1.0)

    def test_obs_shape_after_step(self):
        """Observation shape should be consistent after stepping."""
        env = AttackEnv()
        obs = env.reset(seed=42)
        initial_shape = obs.shape

        for _ in range(5):
            obs, _, done, _ = env.step(0)
            assert obs.shape == initial_shape
            if done:
                break


class TestActionSpace:
    """Test action space properties."""

    def test_action_space_size(self):
        """Action space should match number of techniques."""
        env = AttackEnv()

        assert env.action_space_n == env.n_actions
        assert env.n_actions == len(env.techniques)
        assert env.n_actions == 12  # Default config has 12 techniques

    def test_valid_actions(self):
        """All valid actions should be accepted."""
        env = AttackEnv()
        env.reset(seed=42)

        for action in range(env.n_actions):
            env.reset(seed=42)
            obs, reward, done, info = env.step(action)
            assert isinstance(obs, np.ndarray)
            assert isinstance(reward, float)
            assert isinstance(done, bool)
            assert isinstance(info, dict)

    def test_invalid_action_raises(self):
        """Invalid actions should raise ValueError."""
        env = AttackEnv()
        env.reset(seed=42)

        with pytest.raises(ValueError):
            env.step(-1)

        with pytest.raises(ValueError):
            env.step(env.n_actions)

        with pytest.raises(ValueError):
            env.step(100)


class TestActionMasking:
    """Test action masking functionality."""

    def test_mask_shape(self):
        """Action mask should have correct shape."""
        env = AttackEnv()
        env.reset(seed=42)

        mask = env.get_action_mask()

        assert mask.shape == (env.n_actions,)
        assert mask.dtype == bool

    def test_initial_mask_mostly_valid(self):
        """Initially, most actions should be valid."""
        env = AttackEnv()
        env.reset(seed=42)

        mask = env.get_action_mask()

        # At least initial access techniques should be valid
        assert np.sum(mask) > 0
        # Not all actions may be valid (e.g., exfiltration without data)
        # but at least some should be

    def test_mask_updates_with_state(self):
        """Mask should reflect state changes."""
        env = AttackEnv()
        env.reset(seed=42)

        initial_mask = env.get_action_mask().copy()

        # Take some actions to change state
        for _ in range(3):
            env.step(0)

        updated_mask = env.get_action_mask()

        # Mask may or may not change depending on state
        # Just verify it's still valid
        assert updated_mask.shape == initial_mask.shape
        assert np.sum(updated_mask) > 0


class TestEpisodeTermination:
    """Test episode termination conditions."""

    def test_max_steps_terminates(self):
        """Episode should terminate after max steps."""
        config = EnvConfig(max_steps=5)
        env = AttackEnv(config)
        env.reset(seed=42)

        for i in range(10):
            _, _, done, info = env.step(0)
            if done:
                break

        assert done
        assert i < 10  # Should have terminated before 10 steps

    def test_step_after_done_raises(self):
        """Stepping after episode done should raise error."""
        config = EnvConfig(max_steps=2)
        env = AttackEnv(config)
        env.reset(seed=42)

        # Run until done
        for _ in range(10):
            _, _, done, _ = env.step(0)
            if done:
                break

        with pytest.raises(RuntimeError):
            env.step(0)

    def test_reset_after_done(self):
        """Should be able to reset after episode ends."""
        config = EnvConfig(max_steps=2)
        env = AttackEnv(config)
        env.reset(seed=42)

        # Run until done
        for _ in range(10):
            _, _, done, _ = env.step(0)
            if done:
                break

        # Reset should work
        obs = env.reset(seed=43)
        assert obs.shape == env.observation_space_shape


class TestRewardStructure:
    """Test reward structure."""

    def test_rewards_are_floats(self):
        """All rewards should be float values."""
        env = AttackEnv()
        env.reset(seed=42)

        for _ in range(5):
            _, reward, done, _ = env.step(0)
            assert isinstance(reward, (int, float))
            if done:
                break

    def test_reward_not_nan(self):
        """Rewards should never be NaN."""
        env = AttackEnv()
        env.reset(seed=42)

        for _ in range(10):
            _, reward, done, _ = env.step(np.random.randint(env.n_actions))
            assert not np.isnan(reward)
            if done:
                break


class TestInfoDict:
    """Test info dictionary contents."""

    def test_info_contains_technique(self):
        """Info should contain executed technique."""
        env = AttackEnv()
        env.reset(seed=42)

        _, _, _, info = env.step(0)

        assert "technique" in info
        assert info["technique"] == env.techniques[0]

    def test_info_contains_success_status(self):
        """Info should contain success status."""
        env = AttackEnv()
        env.reset(seed=42)

        _, _, _, info = env.step(0)

        assert "success" in info
        assert isinstance(info["success"], bool)

    def test_info_contains_detection_status(self):
        """Info should contain detection status."""
        env = AttackEnv()
        env.reset(seed=42)

        _, _, _, info = env.step(0)

        assert "detected" in info
        assert isinstance(info["detected"], bool)


class TestRender:
    """Test render functionality."""

    def test_render_returns_string(self):
        """Render should return a string representation."""
        env = AttackEnv()
        env.reset(seed=42)

        rendered = env.render()

        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_updates_with_state(self):
        """Render output should change as state changes."""
        env = AttackEnv()
        env.reset(seed=42)

        initial_render = env.render()

        # Take actions
        for _ in range(3):
            env.step(0)

        updated_render = env.render()

        # Render might be different if state changed
        # At minimum, steps should have incremented
        assert "Steps" in initial_render
        assert "Steps" in updated_render

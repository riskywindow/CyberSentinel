"""
Simple Policy Gradient (REINFORCE) implementation.

Supports both PyTorch (preferred) and pure NumPy fallback.
"""

import os
import json
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

# Try to import torch, fall back to numpy-only implementation
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.distributions import Categorical
    TORCH_AVAILABLE = True
except (ImportError, AttributeError, Exception):
    # Catch any torch import errors (including broken installations)
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    optim = None
    Categorical = None


class PolicyNetwork:
    """
    Simple two-layer MLP policy network.

    Supports both PyTorch and pure NumPy implementations.
    """

    def __init__(self, obs_dim: int, n_actions: int, hidden_dim: int = 64,
                 learning_rate: float = 1e-3, entropy_coef: float = 0.01,
                 use_torch: Optional[bool] = None):
        self.obs_dim = obs_dim
        self.n_actions = n_actions
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.entropy_coef = entropy_coef

        # Decide whether to use torch
        self.use_torch = use_torch if use_torch is not None else TORCH_AVAILABLE

        if self.use_torch and TORCH_AVAILABLE:
            self._init_torch()
        else:
            self._init_numpy()

    def _init_torch(self):
        """Initialize PyTorch network."""
        self.net = nn.Sequential(
            nn.Linear(self.obs_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_dim, self.n_actions),
        )
        self.optimizer = optim.Adam(self.net.parameters(), lr=self.learning_rate)

    def _init_numpy(self):
        """Initialize NumPy network weights."""
        self.use_torch = False
        # Xavier initialization
        scale1 = np.sqrt(2.0 / (self.obs_dim + self.hidden_dim))
        scale2 = np.sqrt(2.0 / (self.hidden_dim + self.hidden_dim))
        scale3 = np.sqrt(2.0 / (self.hidden_dim + self.n_actions))

        self.w1 = np.random.randn(self.obs_dim, self.hidden_dim).astype(np.float32) * scale1
        self.b1 = np.zeros(self.hidden_dim, dtype=np.float32)
        self.w2 = np.random.randn(self.hidden_dim, self.hidden_dim).astype(np.float32) * scale2
        self.b2 = np.zeros(self.hidden_dim, dtype=np.float32)
        self.w3 = np.random.randn(self.hidden_dim, self.n_actions).astype(np.float32) * scale3
        self.b3 = np.zeros(self.n_actions, dtype=np.float32)

    def forward(self, obs: np.ndarray) -> np.ndarray:
        """
        Forward pass to get action logits.

        Args:
            obs: Observation array of shape (obs_dim,) or (batch, obs_dim)

        Returns:
            Logits array of shape (n_actions,) or (batch, n_actions)
        """
        if self.use_torch and TORCH_AVAILABLE:
            with torch.no_grad():
                obs_t = torch.from_numpy(obs).float()
                if obs_t.dim() == 1:
                    obs_t = obs_t.unsqueeze(0)
                logits = self.net(obs_t)
                return logits.squeeze(0).numpy()
        else:
            return self._forward_numpy(obs)

    def _forward_numpy(self, obs: np.ndarray) -> np.ndarray:
        """NumPy forward pass."""
        # Layer 1
        h1 = np.maximum(0, obs @ self.w1 + self.b1)  # ReLU
        # Layer 2
        h2 = np.maximum(0, h1 @ self.w2 + self.b2)  # ReLU
        # Output layer
        logits = h2 @ self.w3 + self.b3
        return logits

    def get_action_probs(self, obs: np.ndarray, mask: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Get action probabilities.

        Args:
            obs: Observation array
            mask: Optional boolean mask for valid actions

        Returns:
            Probability distribution over actions
        """
        logits = self.forward(obs)

        # Apply mask if provided
        if mask is not None:
            logits = np.where(mask, logits, -1e9)

        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        return probs

    def sample_action(self, obs: np.ndarray, mask: Optional[np.ndarray] = None,
                      rng: Optional[np.random.Generator] = None) -> Tuple[int, float]:
        """
        Sample an action from the policy.

        Args:
            obs: Observation array
            mask: Optional boolean mask for valid actions
            rng: Random number generator

        Returns:
            Tuple of (action_index, log_probability)
        """
        probs = self.get_action_probs(obs, mask)
        rng = rng or np.random.default_rng()
        action = rng.choice(self.n_actions, p=probs)
        log_prob = np.log(probs[action] + 1e-10)
        return action, log_prob

    def compute_entropy(self, obs: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
        """Compute entropy of action distribution."""
        probs = self.get_action_probs(obs, mask)
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        return entropy

    def save(self, path: str):
        """Save policy to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.use_torch and TORCH_AVAILABLE:
            torch.save({
                "state_dict": self.net.state_dict(),
                "obs_dim": self.obs_dim,
                "n_actions": self.n_actions,
                "hidden_dim": self.hidden_dim,
                "learning_rate": self.learning_rate,
                "entropy_coef": self.entropy_coef,
            }, path)
        else:
            np.savez(path.with_suffix(".npz"),
                     w1=self.w1, b1=self.b1,
                     w2=self.w2, b2=self.b2,
                     w3=self.w3, b3=self.b3,
                     obs_dim=self.obs_dim,
                     n_actions=self.n_actions,
                     hidden_dim=self.hidden_dim,
                     learning_rate=self.learning_rate,
                     entropy_coef=self.entropy_coef)

    def load(self, path: str):
        """Load policy from file."""
        path = Path(path)

        if self.use_torch and TORCH_AVAILABLE and path.suffix == ".pt":
            checkpoint = torch.load(path, weights_only=False)
            self.net.load_state_dict(checkpoint["state_dict"])
        else:
            # Try numpy format
            npz_path = path.with_suffix(".npz") if path.suffix != ".npz" else path
            if npz_path.exists():
                data = np.load(npz_path)
                self.w1 = data["w1"]
                self.b1 = data["b1"]
                self.w2 = data["w2"]
                self.b2 = data["b2"]
                self.w3 = data["w3"]
                self.b3 = data["b3"]
                self.use_torch = False


class SimplePolicyGradient:
    """
    REINFORCE algorithm with baseline and entropy bonus.

    Implements simple policy gradient with:
    - Reward-to-go for variance reduction
    - Running mean baseline
    - Entropy regularization
    """

    def __init__(self, policy: PolicyNetwork, gamma: float = 0.99,
                 baseline_decay: float = 0.99):
        self.policy = policy
        self.gamma = gamma
        self.baseline_decay = baseline_decay
        self.baseline = 0.0

        # Trajectory buffers
        self.obs_buffer: List[np.ndarray] = []
        self.action_buffer: List[int] = []
        self.reward_buffer: List[float] = []
        self.log_prob_buffer: List[float] = []
        self.mask_buffer: List[Optional[np.ndarray]] = []

    def store_transition(self, obs: np.ndarray, action: int, reward: float,
                         log_prob: float, mask: Optional[np.ndarray] = None):
        """Store a transition in the buffer."""
        self.obs_buffer.append(obs.copy())
        self.action_buffer.append(action)
        self.reward_buffer.append(reward)
        self.log_prob_buffer.append(log_prob)
        self.mask_buffer.append(mask.copy() if mask is not None else None)

    def compute_returns(self) -> np.ndarray:
        """Compute discounted returns (reward-to-go)."""
        returns = []
        running_return = 0.0

        for reward in reversed(self.reward_buffer):
            running_return = reward + self.gamma * running_return
            returns.insert(0, running_return)

        return np.array(returns, dtype=np.float32)

    def update(self) -> Dict[str, float]:
        """
        Perform policy gradient update.

        Returns:
            Dictionary with loss, mean_return, and entropy
        """
        if len(self.obs_buffer) == 0:
            return {"loss": 0.0, "mean_return": 0.0, "entropy": 0.0}

        returns = self.compute_returns()
        mean_return = float(np.mean(returns))

        # Update baseline
        self.baseline = self.baseline_decay * self.baseline + (1 - self.baseline_decay) * mean_return

        # Advantage = returns - baseline
        advantages = returns - self.baseline

        # Normalize advantages
        if len(advantages) > 1:
            advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)

        if self.policy.use_torch and TORCH_AVAILABLE:
            loss, entropy = self._update_torch(advantages)
        else:
            loss, entropy = self._update_numpy(advantages)

        # Clear buffers
        self.obs_buffer.clear()
        self.action_buffer.clear()
        self.reward_buffer.clear()
        self.log_prob_buffer.clear()
        self.mask_buffer.clear()

        return {
            "loss": loss,
            "mean_return": mean_return,
            "entropy": entropy,
        }

    def _update_torch(self, advantages: np.ndarray) -> Tuple[float, float]:
        """PyTorch policy gradient update."""
        obs_t = torch.from_numpy(np.array(self.obs_buffer)).float()
        actions_t = torch.tensor(self.action_buffer, dtype=torch.long)
        advantages_t = torch.from_numpy(advantages).float()

        # Forward pass
        logits = self.policy.net(obs_t)
        dist = Categorical(logits=logits)
        log_probs = dist.log_prob(actions_t)
        entropy = dist.entropy().mean()

        # Policy gradient loss
        policy_loss = -(log_probs * advantages_t).mean()

        # Total loss with entropy bonus
        loss = policy_loss - self.policy.entropy_coef * entropy

        # Backward pass
        self.policy.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy.net.parameters(), max_norm=0.5)
        self.policy.optimizer.step()

        return float(loss.item()), float(entropy.item())

    def _update_numpy(self, advantages: np.ndarray) -> Tuple[float, float]:
        """NumPy policy gradient update (simple gradient descent)."""
        total_loss = 0.0
        total_entropy = 0.0

        # Compute gradients via finite differences (simplified)
        # For production, use proper backprop or autograd
        eps = 1e-4

        for i, (obs, action, advantage) in enumerate(zip(
            self.obs_buffer, self.action_buffer, advantages
        )):
            probs = self.policy.get_action_probs(obs, self.mask_buffer[i])
            log_prob = np.log(probs[action] + 1e-10)

            # Policy gradient: -log_prob * advantage
            total_loss -= log_prob * advantage

            # Entropy
            entropy = -np.sum(probs * np.log(probs + 1e-10))
            total_entropy += entropy

            # Simple parameter update using finite differences
            # Update w3 (output layer) - most impact
            grad_w3 = np.zeros_like(self.policy.w3)
            for j in range(self.policy.n_actions):
                # Approximate gradient
                if j == action:
                    # Gradient of log softmax w.r.t. logits
                    grad_w3[:, j] += (1 - probs[j]) * advantage * self._get_hidden(obs)
                else:
                    grad_w3[:, j] -= probs[j] * advantage * self._get_hidden(obs)

            self.policy.w3 += self.policy.learning_rate * grad_w3

        n = len(self.obs_buffer)
        return total_loss / n, total_entropy / n

    def _get_hidden(self, obs: np.ndarray) -> np.ndarray:
        """Get hidden layer activation for gradient computation."""
        h1 = np.maximum(0, obs @ self.policy.w1 + self.policy.b1)
        h2 = np.maximum(0, h1 @ self.policy.w2 + self.policy.b2)
        return h2

    def reset_baseline(self):
        """Reset the baseline to zero."""
        self.baseline = 0.0


def random_policy_action(n_actions: int, mask: Optional[np.ndarray] = None,
                         rng: Optional[np.random.Generator] = None) -> int:
    """Sample a random action (for baseline comparison)."""
    rng = rng or np.random.default_rng()
    if mask is not None:
        valid_actions = np.where(mask)[0]
        if len(valid_actions) == 0:
            return rng.integers(0, n_actions)
        return rng.choice(valid_actions)
    return rng.integers(0, n_actions)

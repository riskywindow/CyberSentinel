"""
Proximal Policy Optimization (PPO) implementation.

Supports both PyTorch (preferred) and pure NumPy fallback.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

# Try to import torch
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.distributions import Categorical
    TORCH_AVAILABLE = True
except (ImportError, AttributeError, Exception):
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    optim = None
    Categorical = None


class ActorCriticNetwork:
    """
    Actor-Critic network for PPO.

    Uses shared hidden layers with separate heads for policy and value.
    """

    def __init__(self, obs_dim: int, n_actions: int, hidden_dim: int = 64,
                 learning_rate: float = 3e-4, use_torch: Optional[bool] = None):
        self.obs_dim = obs_dim
        self.n_actions = n_actions
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate

        self.use_torch = use_torch if use_torch is not None else TORCH_AVAILABLE

        if self.use_torch and TORCH_AVAILABLE:
            self._init_torch()
        else:
            self._init_numpy()

    def _init_torch(self):
        """Initialize PyTorch networks."""
        # Shared layers
        self.shared = nn.Sequential(
            nn.Linear(self.obs_dim, self.hidden_dim),
            nn.Tanh(),
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.Tanh(),
        )
        # Policy head
        self.policy_head = nn.Linear(self.hidden_dim, self.n_actions)
        # Value head
        self.value_head = nn.Linear(self.hidden_dim, 1)

        # Combined parameters for optimizer
        self.optimizer = optim.Adam(
            list(self.shared.parameters()) +
            list(self.policy_head.parameters()) +
            list(self.value_head.parameters()),
            lr=self.learning_rate
        )

    def _init_numpy(self):
        """Initialize NumPy network weights."""
        self.use_torch = False

        # Xavier initialization using legacy numpy random for determinism
        # when np.random.seed() is called before construction
        def xavier(in_dim, out_dim):
            scale = np.sqrt(2.0 / (in_dim + out_dim))
            return (np.random.randn(in_dim, out_dim) * scale).astype(np.float32)

        # Shared layers
        self.w1 = xavier(self.obs_dim, self.hidden_dim)
        self.b1 = np.zeros(self.hidden_dim, dtype=np.float32)
        self.w2 = xavier(self.hidden_dim, self.hidden_dim)
        self.b2 = np.zeros(self.hidden_dim, dtype=np.float32)

        # Policy head
        self.w_policy = xavier(self.hidden_dim, self.n_actions)
        self.b_policy = np.zeros(self.n_actions, dtype=np.float32)

        # Value head
        self.w_value = xavier(self.hidden_dim, 1)
        self.b_value = np.zeros(1, dtype=np.float32)

    def forward(self, obs: np.ndarray, mask: Optional[np.ndarray] = None
                ) -> Tuple[np.ndarray, float]:
        """
        Forward pass to get policy logits and value estimate.

        Args:
            obs: Observation array
            mask: Optional action mask

        Returns:
            Tuple of (action_probs, value)
        """
        if self.use_torch and TORCH_AVAILABLE:
            return self._forward_torch(obs, mask)
        return self._forward_numpy(obs, mask)

    def _forward_torch(self, obs: np.ndarray, mask: Optional[np.ndarray] = None
                       ) -> Tuple[np.ndarray, float]:
        """PyTorch forward pass."""
        with torch.no_grad():
            obs_t = torch.from_numpy(obs).float()
            if obs_t.dim() == 1:
                obs_t = obs_t.unsqueeze(0)

            hidden = self.shared(obs_t)
            logits = self.policy_head(hidden)
            value = self.value_head(hidden)

            # Apply mask
            if mask is not None:
                mask_t = torch.from_numpy(mask).bool()
                logits = torch.where(mask_t, logits, torch.tensor(-1e9))

            probs = torch.softmax(logits, dim=-1)
            return probs.squeeze(0).numpy(), float(value.squeeze().item())

    def _forward_numpy(self, obs: np.ndarray, mask: Optional[np.ndarray] = None
                       ) -> Tuple[np.ndarray, float]:
        """NumPy forward pass."""
        # Shared layers with tanh
        h1 = np.tanh(obs @ self.w1 + self.b1)
        h2 = np.tanh(h1 @ self.w2 + self.b2)

        # Policy logits
        logits = h2 @ self.w_policy + self.b_policy
        if mask is not None:
            logits = np.where(mask, logits, -1e9)

        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)

        # Value
        value = float((h2 @ self.w_value + self.b_value)[0])

        return probs, value

    def get_value(self, obs: np.ndarray) -> float:
        """Get value estimate only."""
        _, value = self.forward(obs)
        return value

    def sample_action(self, obs: np.ndarray, mask: Optional[np.ndarray] = None,
                      rng: Optional[np.random.Generator] = None
                      ) -> Tuple[int, float, float]:
        """
        Sample action from policy.

        Returns:
            Tuple of (action, log_prob, value)
        """
        probs, value = self.forward(obs, mask)
        rng = rng or np.random.default_rng()
        action = rng.choice(self.n_actions, p=probs)
        log_prob = np.log(probs[action] + 1e-10)
        return action, log_prob, value

    def save(self, path: str):
        """Save network to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.use_torch and TORCH_AVAILABLE:
            torch.save({
                "shared": self.shared.state_dict(),
                "policy_head": self.policy_head.state_dict(),
                "value_head": self.value_head.state_dict(),
                "obs_dim": self.obs_dim,
                "n_actions": self.n_actions,
                "hidden_dim": self.hidden_dim,
            }, path)
        else:
            np.savez(path.with_suffix(".npz"),
                     w1=self.w1, b1=self.b1,
                     w2=self.w2, b2=self.b2,
                     w_policy=self.w_policy, b_policy=self.b_policy,
                     w_value=self.w_value, b_value=self.b_value,
                     obs_dim=self.obs_dim,
                     n_actions=self.n_actions,
                     hidden_dim=self.hidden_dim)

    def load(self, path: str):
        """Load network from file."""
        path = Path(path)

        if self.use_torch and TORCH_AVAILABLE and path.suffix == ".pt":
            checkpoint = torch.load(path, weights_only=False)
            self.shared.load_state_dict(checkpoint["shared"])
            self.policy_head.load_state_dict(checkpoint["policy_head"])
            self.value_head.load_state_dict(checkpoint["value_head"])
        else:
            npz_path = path.with_suffix(".npz") if path.suffix != ".npz" else path
            if npz_path.exists():
                data = np.load(npz_path)
                self.w1 = data["w1"]
                self.b1 = data["b1"]
                self.w2 = data["w2"]
                self.b2 = data["b2"]
                self.w_policy = data["w_policy"]
                self.b_policy = data["b_policy"]
                self.w_value = data["w_value"]
                self.b_value = data["b_value"]
                self.use_torch = False


class PPO:
    """
    Proximal Policy Optimization algorithm.

    Features:
    - Clipped surrogate objective
    - Generalized Advantage Estimation (GAE)
    - Entropy bonus
    - Value function loss
    """

    def __init__(self, network: ActorCriticNetwork,
                 clip_ratio: float = 0.2,
                 gamma: float = 0.99,
                 gae_lambda: float = 0.95,
                 entropy_coef: float = 0.01,
                 value_coef: float = 0.5,
                 n_epochs: int = 4,
                 minibatch_size: int = 32):
        self.network = network
        self.clip_ratio = clip_ratio
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.n_epochs = n_epochs
        self.minibatch_size = minibatch_size

        # Trajectory buffers
        self.obs_buffer: List[np.ndarray] = []
        self.action_buffer: List[int] = []
        self.reward_buffer: List[float] = []
        self.value_buffer: List[float] = []
        self.log_prob_buffer: List[float] = []
        self.mask_buffer: List[Optional[np.ndarray]] = []
        self.done_buffer: List[bool] = []

    def store_transition(self, obs: np.ndarray, action: int, reward: float,
                         value: float, log_prob: float, done: bool,
                         mask: Optional[np.ndarray] = None):
        """Store a transition."""
        self.obs_buffer.append(obs.copy())
        self.action_buffer.append(action)
        self.reward_buffer.append(reward)
        self.value_buffer.append(value)
        self.log_prob_buffer.append(log_prob)
        self.done_buffer.append(done)
        self.mask_buffer.append(mask.copy() if mask is not None else None)

    def compute_gae(self, last_value: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute GAE advantages and returns.

        Args:
            last_value: Value estimate for state after last step

        Returns:
            Tuple of (advantages, returns)
        """
        n = len(self.reward_buffer)
        advantages = np.zeros(n, dtype=np.float32)
        returns = np.zeros(n, dtype=np.float32)

        # GAE computation
        last_gae = 0.0
        for t in reversed(range(n)):
            if t == n - 1:
                next_value = last_value
                next_non_terminal = 1.0 - float(self.done_buffer[t])
            else:
                next_value = self.value_buffer[t + 1]
                next_non_terminal = 1.0 - float(self.done_buffer[t])

            delta = (self.reward_buffer[t] +
                     self.gamma * next_value * next_non_terminal -
                     self.value_buffer[t])
            last_gae = delta + self.gamma * self.gae_lambda * next_non_terminal * last_gae
            advantages[t] = last_gae

        returns = advantages + np.array(self.value_buffer, dtype=np.float32)
        return advantages, returns

    def update(self, last_value: float = 0.0) -> Dict[str, float]:
        """
        Perform PPO update.

        Returns:
            Dictionary with policy_loss, value_loss, entropy, and total_loss
        """
        if len(self.obs_buffer) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "total_loss": 0.0}

        # Compute advantages
        advantages, returns = self.compute_gae(last_value)

        # Normalize advantages
        advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)

        if self.network.use_torch and TORCH_AVAILABLE:
            stats = self._update_torch(advantages, returns)
        else:
            stats = self._update_numpy(advantages, returns)

        # Clear buffers
        self.obs_buffer.clear()
        self.action_buffer.clear()
        self.reward_buffer.clear()
        self.value_buffer.clear()
        self.log_prob_buffer.clear()
        self.mask_buffer.clear()
        self.done_buffer.clear()

        return stats

    def _update_torch(self, advantages: np.ndarray, returns: np.ndarray) -> Dict[str, float]:
        """PyTorch PPO update."""
        obs_t = torch.from_numpy(np.array(self.obs_buffer)).float()
        actions_t = torch.tensor(self.action_buffer, dtype=torch.long)
        old_log_probs_t = torch.tensor(self.log_prob_buffer, dtype=torch.float32)
        advantages_t = torch.from_numpy(advantages).float()
        returns_t = torch.from_numpy(returns).float()

        # Handle masks
        masks_t = []
        for m in self.mask_buffer:
            if m is not None:
                masks_t.append(torch.from_numpy(m).bool())
            else:
                masks_t.append(torch.ones(self.network.n_actions, dtype=torch.bool))
        masks_t = torch.stack(masks_t)

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0

        for _ in range(self.n_epochs):
            # Shuffle data
            indices = np.random.permutation(len(self.obs_buffer))

            for start in range(0, len(indices), self.minibatch_size):
                end = start + self.minibatch_size
                batch_indices = indices[start:end]

                batch_obs = obs_t[batch_indices]
                batch_actions = actions_t[batch_indices]
                batch_old_log_probs = old_log_probs_t[batch_indices]
                batch_advantages = advantages_t[batch_indices]
                batch_returns = returns_t[batch_indices]
                batch_masks = masks_t[batch_indices]

                # Forward pass
                hidden = self.network.shared(batch_obs)
                logits = self.network.policy_head(hidden)
                values = self.network.value_head(hidden).squeeze(-1)

                # Apply masks
                logits = torch.where(batch_masks, logits, torch.tensor(-1e9))

                # Policy distribution
                dist = Categorical(logits=logits)
                new_log_probs = dist.log_prob(batch_actions)
                entropy = dist.entropy().mean()

                # Policy loss (clipped surrogate)
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = 0.5 * ((values - batch_returns) ** 2).mean()

                # Total loss
                loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy

                # Backward pass
                self.network.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    list(self.network.shared.parameters()) +
                    list(self.network.policy_head.parameters()) +
                    list(self.network.value_head.parameters()),
                    max_norm=0.5
                )
                self.network.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                n_updates += 1

        return {
            "policy_loss": total_policy_loss / max(1, n_updates),
            "value_loss": total_value_loss / max(1, n_updates),
            "entropy": total_entropy / max(1, n_updates),
            "total_loss": (total_policy_loss + total_value_loss) / max(1, n_updates),
        }

    def _update_numpy(self, advantages: np.ndarray, returns: np.ndarray) -> Dict[str, float]:
        """NumPy PPO update (simplified gradient descent)."""
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0

        for _ in range(self.n_epochs):
            for i in range(len(self.obs_buffer)):
                obs = self.obs_buffer[i]
                action = self.action_buffer[i]
                old_log_prob = self.log_prob_buffer[i]
                advantage = advantages[i]
                target_return = returns[i]
                mask = self.mask_buffer[i]

                # Forward pass
                probs, value = self.network.forward(obs, mask)
                new_log_prob = np.log(probs[action] + 1e-10)

                # Ratio and clipped surrogate
                ratio = np.exp(new_log_prob - old_log_prob)
                surr1 = ratio * advantage
                surr2 = np.clip(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * advantage
                policy_loss = -min(surr1, surr2)

                # Value loss
                value_loss = 0.5 * (value - target_return) ** 2

                # Entropy
                entropy = -np.sum(probs * np.log(probs + 1e-10))

                total_policy_loss += policy_loss
                total_value_loss += value_loss
                total_entropy += entropy

                # Simple gradient update on policy weights
                grad = np.zeros_like(self.network.w_policy)
                h1 = np.tanh(obs @ self.network.w1 + self.network.b1)
                h2 = np.tanh(h1 @ self.network.w2 + self.network.b2)

                for j in range(self.network.n_actions):
                    if j == action:
                        grad[:, j] += (1 - probs[j]) * advantage * h2
                    else:
                        grad[:, j] -= probs[j] * advantage * h2

                self.network.w_policy += self.network.learning_rate * grad

                # Update value weights
                value_grad = (target_return - value) * h2
                self.network.w_value += self.network.learning_rate * value_grad.reshape(-1, 1)

        n = len(self.obs_buffer) * self.n_epochs
        return {
            "policy_loss": total_policy_loss / max(1, n),
            "value_loss": total_value_loss / max(1, n),
            "entropy": total_entropy / max(1, n),
            "total_loss": (total_policy_loss + total_value_loss) / max(1, n),
        }

    def clear_buffers(self):
        """Clear all trajectory buffers."""
        self.obs_buffer.clear()
        self.action_buffer.clear()
        self.reward_buffer.clear()
        self.value_buffer.clear()
        self.log_prob_buffer.clear()
        self.mask_buffer.clear()
        self.done_buffer.clear()

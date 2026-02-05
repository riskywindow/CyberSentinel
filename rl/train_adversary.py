#!/usr/bin/env python3
"""
Train an RL adversary agent using policy gradient or PPO.

Usage:
    python rl/train_adversary.py --algo pg --seed 42 --episodes 50
    python rl/train_adversary.py --algo ppo --seed 42 --episodes 200

Outputs:
    eval/rl/policy.pt       - Trained policy weights
    eval/rl/metrics.jsonl   - Per-episode metrics
    eval/rl/traces.jsonl    - Step-level episode traces
    eval/rl/score.json      - Training summary
    eval/rl/summary.md      - Markdown summary
"""

import argparse
import json
import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redteam.envs import AttackEnv, EnvConfig
from redteam.policy import (
    PolicyNetwork, SimplePolicyGradient,
    ActorCriticNetwork, PPO,
    random_policy_action
)


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except (ImportError, AttributeError, Exception):
        pass


class EpisodeTracer:
    """Records step-level traces for episodes."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.file = open(output_path, "w")
        self._current_episode = 0
        self._current_seed = 0

    def start_episode(self, episode: int, seed: int):
        """Start a new episode trace."""
        self._current_episode = episode
        self._current_seed = seed
        self._cumulative_reward = 0.0

    def log_step(self, step: int, obs: np.ndarray, action: int, action_name: str,
                 mask: np.ndarray, reward: float, info: Dict[str, Any],
                 rationale: Optional[str] = None):
        """Log a single step."""
        self._cumulative_reward += reward

        trace = {
            "seed": self._current_seed,
            "episode": self._current_episode,
            "step": step,
            "phase": info.get("phase", 0),
            "action_id": action,
            "action_name": action_name,
            "masked": bool(info.get("action_masked", False)),
            "reward": float(reward),
            "cumulative_reward": float(self._cumulative_reward),
            "detected": bool(info.get("detected", False)),
            "latency_ms": int(info.get("latency_ms", 0)),
            "success": bool(info.get("success", False)),
            "reward_type": info.get("reward_type", "unknown"),
        }
        if rationale:
            trace["rationale"] = rationale

        self.file.write(json.dumps(trace) + "\n")
        self.file.flush()

    def close(self):
        """Close the trace file."""
        self.file.close()


def train_episode_pg(env: AttackEnv, policy: PolicyNetwork, trainer: SimplePolicyGradient,
                     rng: np.random.Generator, tracer: Optional[EpisodeTracer] = None,
                     episode: int = 0, seed: int = 0,
                     use_random: bool = False) -> Dict[str, Any]:
    """Run one training episode with policy gradient."""
    obs, info = env.reset(seed=seed)
    mask = info.get("action_mask", env.get_action_mask())

    if tracer:
        tracer.start_episode(episode, seed)

    episode_reward = 0.0
    episode_steps = 0
    success = False
    detected = False
    step = 0

    while True:
        if use_random:
            action = random_policy_action(env.n_actions, mask, rng)
            log_prob = 0.0
        else:
            action, log_prob = policy.sample_action(obs, mask, rng)

        next_obs, reward, done, info = env.step(action)
        mask = info.get("action_mask", env.get_action_mask())

        if tracer:
            tracer.log_step(
                step=step,
                obs=obs,
                action=action,
                action_name=env.get_technique_name(action),
                mask=mask,
                reward=reward,
                info=info,
            )

        if not use_random:
            trainer.store_transition(obs, action, reward, log_prob, mask)

        episode_reward += reward
        episode_steps += 1
        step += 1
        obs = next_obs

        if info.get("objective_complete"):
            success = True
        if info.get("locked_out"):
            detected = True

        if done:
            break

    return {
        "reward": episode_reward,
        "steps": episode_steps,
        "success": success,
        "detected": detected,
    }


def train_episode_ppo(env: AttackEnv, network: ActorCriticNetwork, trainer: PPO,
                      rng: np.random.Generator, tracer: Optional[EpisodeTracer] = None,
                      episode: int = 0, seed: int = 0,
                      use_random: bool = False) -> Dict[str, Any]:
    """Run one training episode with PPO."""
    obs, info = env.reset(seed=seed)
    mask = info.get("action_mask", env.get_action_mask())

    if tracer:
        tracer.start_episode(episode, seed)

    episode_reward = 0.0
    episode_steps = 0
    success = False
    detected = False
    step = 0

    while True:
        if use_random:
            action = random_policy_action(env.n_actions, mask, rng)
            log_prob = 0.0
            value = 0.0
        else:
            action, log_prob, value = network.sample_action(obs, mask, rng)

        next_obs, reward, done, info = env.step(action)
        new_mask = info.get("action_mask", env.get_action_mask())

        if tracer:
            tracer.log_step(
                step=step,
                obs=obs,
                action=action,
                action_name=env.get_technique_name(action),
                mask=mask,
                reward=reward,
                info=info,
            )

        if not use_random:
            trainer.store_transition(obs, action, reward, value, log_prob, done, mask)

        episode_reward += reward
        episode_steps += 1
        step += 1
        obs = next_obs
        mask = new_mask

        if info.get("objective_complete"):
            success = True
        if info.get("locked_out"):
            detected = True

        if done:
            break

    return {
        "reward": episode_reward,
        "steps": episode_steps,
        "success": success,
        "detected": detected,
        "last_value": 0.0 if done else network.get_value(obs),
    }


def write_summary_md(output_dir: Path, results: Dict[str, Any]):
    """Write summary.md with results table."""
    summary_path = output_dir / "summary.md"

    lines = [
        "# RL Adversary Training Summary",
        "",
        f"**Seed:** {results['seed']}",
        f"**Episodes:** {results['episodes']}",
        f"**Algorithm:** {results['algorithm']}",
        f"**Training Time:** {results['training_time']:.2f}s",
        "",
        "## Results",
        "",
        "| Metric | Random | " + results['algorithm'].upper() + " |",
        "|--------|--------|" + "-" * len(results['algorithm']) + "---|",
        f"| Mean Reward | {results['random_mean_reward']:.3f} | {results['rl_mean_reward']:.3f} |",
        f"| Success Rate | {results['random_success_rate']*100:.1f}% | {results['rl_success_rate']*100:.1f}% |",
        "",
        f"**Reward Improvement:** {results['reward_improvement']:+.3f}",
        f"**Learning Detected:** {'Yes' if results['learning_detected'] else 'No'}",
        "",
        "## Files",
        "",
        "- `policy.npz` - Trained policy weights",
        "- `metrics.jsonl` - Per-episode metrics",
        "- `traces.jsonl` - Step-level traces",
        "- `score.json` - Training summary (JSON)",
        "- `learning_curve.png` - Learning curve plot",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"SEED={results['seed']} make rl-smoke",
        "```",
    ]

    with open(summary_path, "w") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Train RL adversary agent")
    parser.add_argument("--algo", type=str, default="pg", choices=["pg", "ppo"],
                        help="Algorithm: pg (policy gradient) or ppo")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed (default: from SEED env var or 42)")
    parser.add_argument("--episodes", type=int, default=50,
                        help="Number of training episodes")
    parser.add_argument("--steps-per-episode", type=int, default=12,
                        help="Maximum steps per episode")
    parser.add_argument("--hidden-dim", type=int, default=64,
                        help="Hidden layer dimension")
    parser.add_argument("--lr", type=float, default=1e-3,
                        help="Learning rate")
    parser.add_argument("--gamma", type=float, default=0.99,
                        help="Discount factor")
    parser.add_argument("--entropy-coef", type=float, default=0.01,
                        help="Entropy regularization coefficient")
    parser.add_argument("--clip-ratio", type=float, default=0.2,
                        help="PPO clip ratio")
    parser.add_argument("--gae-lambda", type=float, default=0.95,
                        help="GAE lambda for PPO")
    parser.add_argument("--output-dir", type=str, default="eval/rl",
                        help="Output directory for results")
    parser.add_argument("--use-real-detector", action="store_true",
                        help="Use real detector instead of stub")
    parser.add_argument("--no-baseline-comparison", action="store_true",
                        help="Skip random baseline comparison")
    parser.add_argument("--no-traces", action="store_true",
                        help="Skip writing episode traces")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    # Get seed from args, env var, or default
    seed = args.seed
    if seed is None:
        seed = int(os.environ.get("SEED", 42))

    print(f"Training RL adversary agent")
    print(f"  Algorithm: {args.algo.upper()}")
    print(f"  Seed: {seed}")
    print(f"  Episodes: {args.episodes}")
    print(f"  Steps per episode: {args.steps_per_episode}")
    print(f"  Detector: {'real' if args.use_real_detector else 'stub'}")
    print()

    # Set seed
    set_seed(seed)
    rng = np.random.default_rng(seed)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize environment
    env_config = EnvConfig(
        max_steps=args.steps_per_episode,
        use_real_detector=args.use_real_detector,
    )
    env = AttackEnv(env_config)

    # Initialize tracer
    tracer = None
    if not args.no_traces:
        tracer = EpisodeTracer(output_dir / "traces.jsonl")

    # Initialize policy and trainer based on algorithm
    if args.algo == "ppo":
        network = ActorCriticNetwork(
            obs_dim=env.obs_dim,
            n_actions=env.n_actions,
            hidden_dim=args.hidden_dim,
            learning_rate=args.lr,
        )
        trainer = PPO(
            network=network,
            clip_ratio=args.clip_ratio,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            entropy_coef=args.entropy_coef,
        )
        # For compatibility, create a policy wrapper
        policy = network
    else:
        policy = PolicyNetwork(
            obs_dim=env.obs_dim,
            n_actions=env.n_actions,
            hidden_dim=args.hidden_dim,
            learning_rate=args.lr,
            entropy_coef=args.entropy_coef,
        )
        trainer = SimplePolicyGradient(policy, gamma=args.gamma)
        network = None

    # Metrics storage
    metrics_path = output_dir / "metrics.jsonl"
    metrics_file = open(metrics_path, "w")

    # Training loop
    start_time = time.time()
    all_rewards = []
    all_successes = []
    all_entropies = []

    print("Training...")
    for episode in range(args.episodes):
        episode_seed = seed + episode

        if args.algo == "ppo":
            episode_stats = train_episode_ppo(
                env, network, trainer, rng, tracer,
                episode=episode, seed=episode_seed
            )
            # PPO updates less frequently - every episode for simplicity
            update_stats = trainer.update(last_value=episode_stats.get("last_value", 0.0))
            entropy = update_stats.get("entropy", 0.0)
        else:
            episode_stats = train_episode_pg(
                env, policy, trainer, rng, tracer,
                episode=episode, seed=episode_seed
            )
            update_stats = trainer.update()
            entropy = update_stats.get("entropy", 0.0)

        # Record metrics
        all_rewards.append(episode_stats["reward"])
        all_successes.append(episode_stats["success"])
        all_entropies.append(entropy)

        # Write to JSONL
        metric_record = {
            "episode": episode,
            "reward": float(episode_stats["reward"]),
            "steps": episode_stats["steps"],
            "success": bool(episode_stats["success"]),
            "detected": bool(episode_stats["detected"]),
            "entropy": float(entropy),
            "algorithm": args.algo,
            "timestamp": datetime.now().isoformat(),
        }
        if args.algo == "ppo":
            metric_record["policy_loss"] = float(update_stats.get("policy_loss", 0.0))
            metric_record["value_loss"] = float(update_stats.get("value_loss", 0.0))
        else:
            metric_record["loss"] = float(update_stats.get("loss", 0.0))
            metric_record["mean_return"] = float(update_stats.get("mean_return", 0.0))

        metrics_file.write(json.dumps(metric_record) + "\n")
        metrics_file.flush()

        if args.verbose or (episode + 1) % max(1, args.episodes // 10) == 0:
            print(f"Episode {episode + 1}/{args.episodes}: "
                  f"reward={episode_stats['reward']:.2f}, "
                  f"success={episode_stats['success']}, "
                  f"entropy={entropy:.3f}")

    metrics_file.close()
    if tracer:
        tracer.close()
    training_time = time.time() - start_time

    # Save policy
    policy_path = output_dir / "policy.pt"
    if args.algo == "ppo":
        network.save(str(policy_path))
    else:
        policy.save(str(policy_path))

    # Run random baseline comparison
    baseline_rewards = []
    baseline_successes = []

    if not args.no_baseline_comparison:
        print("\nRunning random baseline comparison...")
        baseline_rng = np.random.default_rng(seed)

        for episode in range(args.episodes):
            episode_seed = seed + episode
            if args.algo == "ppo":
                episode_stats = train_episode_ppo(
                    env, network, trainer, baseline_rng,
                    episode=episode, seed=episode_seed, use_random=True
                )
                trainer.clear_buffers()
            else:
                episode_stats = train_episode_pg(
                    env, policy, trainer, baseline_rng,
                    episode=episode, seed=episode_seed, use_random=True
                )
            baseline_rewards.append(episode_stats["reward"])
            baseline_successes.append(episode_stats["success"])

    # Compute final statistics
    rl_mean_reward = float(np.mean(all_rewards))
    rl_std_reward = float(np.std(all_rewards))
    rl_success_rate = float(np.mean(all_successes))
    rl_final_entropy = float(np.mean(all_entropies[-10:]) if len(all_entropies) >= 10 else np.mean(all_entropies))

    baseline_mean_reward = float(np.mean(baseline_rewards)) if baseline_rewards else 0.0
    baseline_success_rate = float(np.mean(baseline_successes)) if baseline_successes else 0.0

    # Check for learning
    reward_improvement = rl_mean_reward - baseline_mean_reward
    learning_detected = reward_improvement > 0 or rl_success_rate > baseline_success_rate

    # Compute policy hash
    policy_hash = ""
    for ext in [".pt", ".npz"]:
        hash_path = output_dir / f"policy{ext}"
        if hash_path.exists():
            with open(hash_path, "rb") as f:
                policy_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            break

    # Print summary
    print("\n" + "=" * 50)
    print("Training Summary")
    print("=" * 50)
    print(f"Algorithm: {args.algo.upper()}")
    print(f"Training time: {training_time:.2f}s")
    print(f"RL Policy:")
    print(f"  Mean reward: {rl_mean_reward:.3f} (+/- {rl_std_reward:.3f})")
    print(f"  Success rate: {rl_success_rate * 100:.1f}%")
    print(f"  Final entropy: {rl_final_entropy:.3f}")
    if baseline_rewards:
        print(f"Random Baseline:")
        print(f"  Mean reward: {baseline_mean_reward:.3f}")
        print(f"  Success rate: {baseline_success_rate * 100:.1f}%")
        print(f"Improvement: {reward_improvement:+.3f} reward")
    print(f"Learning detected: {learning_detected}")
    print(f"Policy hash: {policy_hash}")
    print("=" * 50)

    # Write score.json
    score_data = {
        "seed": seed,
        "algorithm": args.algo,
        "episodes": args.episodes,
        "steps_per_episode": args.steps_per_episode,
        "training_time_seconds": float(training_time),
        "rl_policy": {
            "mean_reward": rl_mean_reward,
            "std_reward": rl_std_reward,
            "success_rate": rl_success_rate,
            "final_entropy": rl_final_entropy,
        },
        "random_baseline": {
            "mean_reward": baseline_mean_reward,
            "success_rate": baseline_success_rate,
        },
        "reward_improvement": float(reward_improvement),
        "learning_detected": bool(learning_detected),
        "policy_hash": policy_hash,
        "timestamp": datetime.now().isoformat(),
    }

    score_path = output_dir / "score.json"
    with open(score_path, "w") as f:
        json.dump(score_data, f, indent=2)

    # Write summary.md
    summary_results = {
        "seed": seed,
        "algorithm": args.algo,
        "episodes": args.episodes,
        "training_time": training_time,
        "rl_mean_reward": rl_mean_reward,
        "rl_success_rate": rl_success_rate,
        "random_mean_reward": baseline_mean_reward,
        "random_success_rate": baseline_success_rate,
        "reward_improvement": reward_improvement,
        "learning_detected": learning_detected,
    }
    write_summary_md(output_dir, summary_results)

    print(f"\nOutputs saved to {output_dir}/")
    print(f"  policy.npz     - Trained policy")
    print(f"  metrics.jsonl  - Per-episode metrics")
    print(f"  traces.jsonl   - Step-level traces")
    print(f"  score.json     - Training summary")
    print(f"  summary.md     - Markdown summary")

    return 0 if learning_detected else 1


if __name__ == "__main__":
    sys.exit(main())

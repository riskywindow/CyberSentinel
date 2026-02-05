#!/usr/bin/env python3
"""
Evaluate a trained RL adversary agent.

Usage:
    python rl/eval_adversary.py --seed 42

Loads policy from eval/rl/policy.pt and runs evaluation episodes.
Outputs results to eval/rl/score.json.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redteam.envs import AttackEnv, EnvConfig
from redteam.policy import PolicyNetwork
from redteam.policy.simple_pg import random_policy_action


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except (ImportError, AttributeError, Exception):
        # Torch not available or broken installation
        pass


def evaluate_episode(env: AttackEnv, policy: PolicyNetwork, rng: np.random.Generator,
                     deterministic: bool = False, use_random: bool = False,
                     seed: int = None) -> dict:
    """
    Run one evaluation episode.

    Args:
        env: Attack environment
        policy: Policy network
        rng: Random number generator
        deterministic: If True, always pick highest probability action
        use_random: If True, use random policy
        seed: Optional seed for env.reset()

    Returns:
        Episode statistics
    """
    obs, info = env.reset(seed=seed)
    episode_reward = 0.0
    episode_steps = 0
    success = False
    detected = False
    techniques_used = []
    mask = info.get("action_mask", env.get_action_mask())

    while True:

        if use_random:
            action = random_policy_action(env.n_actions, mask, rng)
        elif deterministic:
            probs = policy.get_action_probs(obs, mask)
            action = int(np.argmax(probs))
        else:
            action, _ = policy.sample_action(obs, mask, rng)

        techniques_used.append(env.techniques[action])
        next_obs, reward, done, info = env.step(action)

        episode_reward += reward
        episode_steps += 1
        obs = next_obs
        mask = info.get("action_mask", env.get_action_mask())

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
        "techniques": techniques_used,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate RL adversary agent")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed (default: from SEED env var or 42)")
    parser.add_argument("--episodes", type=int, default=20,
                        help="Number of evaluation episodes")
    parser.add_argument("--steps-per-episode", type=int, default=12,
                        help="Maximum steps per episode")
    parser.add_argument("--policy-path", type=str, default="eval/rl/policy.pt",
                        help="Path to trained policy")
    parser.add_argument("--output-dir", type=str, default="eval/rl",
                        help="Output directory for results")
    parser.add_argument("--deterministic", action="store_true",
                        help="Use deterministic action selection")
    parser.add_argument("--compare-random", action="store_true",
                        help="Also evaluate random baseline")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    # Get seed from args, env var, or default
    seed = args.seed
    if seed is None:
        seed = int(os.environ.get("SEED", 42))

    print(f"Evaluating RL adversary agent")
    print(f"  Seed: {seed}")
    print(f"  Episodes: {args.episodes}")
    print(f"  Policy: {args.policy_path}")
    print()

    # Set seed
    set_seed(seed)
    rng = np.random.default_rng(seed)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize environment
    env_config = EnvConfig(max_steps=args.steps_per_episode)
    env = AttackEnv(env_config)

    # Load policy
    policy_path = Path(args.policy_path)
    policy = PolicyNetwork(
        obs_dim=env.obs_dim,
        n_actions=env.n_actions,
    )

    if policy_path.exists():
        print(f"Loading policy from {policy_path}")
        policy.load(str(policy_path))
    else:
        # Try numpy version
        npz_path = policy_path.with_suffix(".npz")
        if npz_path.exists():
            print(f"Loading policy from {npz_path}")
            policy.load(str(npz_path))
        else:
            print(f"Warning: Policy file not found at {policy_path}")
            print("Using random initialization")

    # Run evaluation
    print("\nEvaluating trained policy...")
    rl_results = []

    for episode in range(args.episodes):
        result = evaluate_episode(env, policy, rng, deterministic=args.deterministic,
                                  seed=seed + episode)
        rl_results.append(result)

        if args.verbose:
            print(f"Episode {episode + 1}: reward={result['reward']:.2f}, "
                  f"success={result['success']}, steps={result['steps']}")

    # Compute statistics
    rl_rewards = [r["reward"] for r in rl_results]
    rl_successes = [r["success"] for r in rl_results]
    rl_detections = [r["detected"] for r in rl_results]
    rl_steps = [r["steps"] for r in rl_results]

    rl_mean_reward = np.mean(rl_rewards)
    rl_std_reward = np.std(rl_rewards)
    rl_success_rate = np.mean(rl_successes)
    rl_detection_rate = np.mean(rl_detections)
    rl_mean_steps = np.mean(rl_steps)

    # Random baseline comparison
    baseline_mean_reward = 0.0
    baseline_success_rate = 0.0
    baseline_detection_rate = 0.0

    if args.compare_random:
        print("\nEvaluating random baseline...")
        baseline_rng = np.random.default_rng(seed)
        baseline_results = []

        for episode in range(args.episodes):
            result = evaluate_episode(env, policy, baseline_rng, use_random=True,
                                      seed=seed + episode)
            baseline_results.append(result)

        baseline_rewards = [r["reward"] for r in baseline_results]
        baseline_successes = [r["success"] for r in baseline_results]
        baseline_detections = [r["detected"] for r in baseline_results]

        baseline_mean_reward = np.mean(baseline_rewards)
        baseline_success_rate = np.mean(baseline_successes)
        baseline_detection_rate = np.mean(baseline_detections)

    # Print summary
    print("\n" + "=" * 50)
    print("Evaluation Summary")
    print("=" * 50)
    print(f"Trained Policy:")
    print(f"  Mean reward: {rl_mean_reward:.3f} (+/- {rl_std_reward:.3f})")
    print(f"  Success rate: {rl_success_rate * 100:.1f}%")
    print(f"  Detection rate: {rl_detection_rate * 100:.1f}%")
    print(f"  Mean steps: {rl_mean_steps:.1f}")

    if args.compare_random:
        print(f"Random Baseline:")
        print(f"  Mean reward: {baseline_mean_reward:.3f}")
        print(f"  Success rate: {baseline_success_rate * 100:.1f}%")
        print(f"  Detection rate: {baseline_detection_rate * 100:.1f}%")
        print(f"Improvement: {rl_mean_reward - baseline_mean_reward:+.3f} reward")

    print("=" * 50)

    # Write results to score.json
    score_data = {
        "seed": seed,
        "episodes": args.episodes,
        "deterministic": args.deterministic,
        "trained_policy": {
            "mean_reward": float(rl_mean_reward),
            "std_reward": float(rl_std_reward),
            "success_rate": float(rl_success_rate),
            "detection_rate": float(rl_detection_rate),
            "mean_steps": float(rl_mean_steps),
        },
        "timestamp": datetime.now().isoformat(),
    }

    if args.compare_random:
        score_data["random_baseline"] = {
            "mean_reward": float(baseline_mean_reward),
            "success_rate": float(baseline_success_rate),
            "detection_rate": float(baseline_detection_rate),
        }
        score_data["reward_improvement"] = float(rl_mean_reward - baseline_mean_reward)

    score_path = output_dir / "score.json"
    with open(score_path, "w") as f:
        json.dump(score_data, f, indent=2)

    print(f"\nResults saved to {score_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

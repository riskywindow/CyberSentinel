#!/usr/bin/env python3
"""
Plot RL training metrics from metrics.jsonl.

Usage:
    python rl/plot_rl.py

Reads from eval/rl/metrics.jsonl and outputs eval/rl/learning_curve.png.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import numpy as np

# Try to import matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def load_metrics(metrics_path: Path) -> List[Dict[str, Any]]:
    """Load metrics from JSONL file."""
    metrics = []
    with open(metrics_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                metrics.append(json.loads(line))
    return metrics


def smooth(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Apply moving average smoothing."""
    if len(values) < window:
        return values
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode='valid')


def plot_learning_curve(metrics: List[Dict[str, Any]], output_path: Path,
                        score_data: Dict[str, Any] = None):
    """Generate learning curve plot."""
    if not MATPLOTLIB_AVAILABLE:
        print("Warning: matplotlib not available, generating ASCII plot instead")
        plot_ascii(metrics, output_path)
        return

    episodes = [m["episode"] for m in metrics]
    rewards = np.array([m["reward"] for m in metrics])
    successes = np.array([m["success"] for m in metrics], dtype=float)
    entropies = np.array([m["entropy"] for m in metrics])

    # Smooth data for visualization
    window = max(1, len(episodes) // 10)
    smoothed_rewards = smooth(rewards, window)
    smoothed_successes = smooth(successes, window)

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle("RL Adversary Training - Learning Curves", fontsize=14)

    # Plot 1: Episode Reward
    ax1 = axes[0, 0]
    ax1.plot(episodes, rewards, alpha=0.3, color='blue', label='Raw')
    if len(smoothed_rewards) > 0:
        smoothed_x = episodes[window-1:]
        ax1.plot(smoothed_x, smoothed_rewards, color='blue', linewidth=2, label='Smoothed')
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    if score_data and "random_baseline" in score_data:
        ax1.axhline(y=score_data["random_baseline"]["mean_reward"],
                    color='red', linestyle='--', alpha=0.7, label='Random Baseline')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Reward')
    ax1.set_title('Episode Reward')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Success Rate (rolling)
    ax2 = axes[0, 1]
    ax2.plot(episodes, successes, alpha=0.3, color='green', label='Raw')
    if len(smoothed_successes) > 0:
        smoothed_x = episodes[window-1:]
        ax2.plot(smoothed_x, smoothed_successes, color='green', linewidth=2, label='Rolling Mean')
    ax2.set_ylim(-0.05, 1.05)
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Success Rate')
    ax2.set_title('Episode Success Rate')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Policy Entropy
    ax3 = axes[1, 0]
    ax3.plot(episodes, entropies, color='purple', alpha=0.7)
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Entropy')
    ax3.set_title('Policy Entropy')
    ax3.grid(True, alpha=0.3)

    # Plot 4: Cumulative Reward
    ax4 = axes[1, 1]
    cumulative_reward = np.cumsum(rewards)
    ax4.plot(episodes, cumulative_reward, color='orange', linewidth=2)
    ax4.set_xlabel('Episode')
    ax4.set_ylabel('Cumulative Reward')
    ax4.set_title('Cumulative Reward')
    ax4.grid(True, alpha=0.3)

    # Add summary text
    if score_data:
        summary_text = (
            f"Final Results:\n"
            f"Mean Reward: {score_data['rl_policy']['mean_reward']:.2f}\n"
            f"Success Rate: {score_data['rl_policy']['success_rate']*100:.1f}%\n"
        )
        if "random_baseline" in score_data:
            summary_text += f"vs Random: {score_data['reward_improvement']:+.2f}"
        fig.text(0.98, 0.02, summary_text, fontsize=10, family='monospace',
                 verticalalignment='bottom', horizontalalignment='right',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Learning curve saved to {output_path}")


def plot_ascii(metrics: List[Dict[str, Any]], output_path: Path):
    """Generate ASCII art plot as fallback."""
    rewards = [m["reward"] for m in metrics]

    # Simple ASCII histogram
    width = 60
    height = 20
    min_r = min(rewards)
    max_r = max(rewards)
    range_r = max_r - min_r if max_r != min_r else 1

    # Bin rewards
    n_bins = min(width, len(rewards))
    bin_size = len(rewards) / n_bins
    binned_rewards = []
    for i in range(n_bins):
        start = int(i * bin_size)
        end = int((i + 1) * bin_size)
        binned_rewards.append(np.mean(rewards[start:end]))

    # Generate ASCII plot
    lines = []
    lines.append("Learning Curve (ASCII)")
    lines.append("=" * (width + 10))

    for row in range(height - 1, -1, -1):
        threshold = min_r + (row + 0.5) * range_r / height
        line = f"{threshold:7.2f} |"
        for val in binned_rewards:
            if val >= threshold:
                line += "#"
            else:
                line += " "
        lines.append(line)

    lines.append("        +" + "-" * n_bins)
    lines.append("         0" + " " * (n_bins - 10) + f"{len(rewards)}")
    lines.append("                    Episode")
    lines.append("")
    lines.append(f"Mean reward: {np.mean(rewards):.3f}")
    lines.append(f"Final reward: {rewards[-1]:.3f}")

    output_text = "\n".join(lines)

    # Save to file
    txt_path = output_path.with_suffix('.txt')
    with open(txt_path, 'w') as f:
        f.write(output_text)

    print(output_text)
    print(f"\nASCII plot saved to {txt_path}")

    # Also try to create a basic PNG using just numpy
    try:
        create_simple_png(metrics, output_path)
    except Exception:
        pass


def create_simple_png(metrics: List[Dict[str, Any]], output_path: Path):
    """Create a minimal PNG without matplotlib."""
    # This is a fallback that creates a very basic visualization
    # using PIL if available
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return

    width, height = 800, 400
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    rewards = [m["reward"] for m in metrics]
    min_r, max_r = min(rewards), max(rewards)
    range_r = max_r - min_r if max_r != min_r else 1

    # Draw axes
    margin = 50
    draw.line([(margin, height - margin), (width - margin, height - margin)], fill='black')
    draw.line([(margin, margin), (margin, height - margin)], fill='black')

    # Plot points
    n_points = len(rewards)
    x_scale = (width - 2 * margin) / max(1, n_points - 1)
    y_scale = (height - 2 * margin) / range_r

    points = []
    for i, r in enumerate(rewards):
        x = margin + i * x_scale
        y = height - margin - (r - min_r) * y_scale
        points.append((x, y))

    # Draw line
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill='blue', width=2)

    img.save(output_path)
    print(f"Simple PNG saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot RL training metrics")
    parser.add_argument("--input-dir", type=str, default="eval/rl",
                        help="Input directory with metrics.jsonl")
    parser.add_argument("--output", type=str, default=None,
                        help="Output path for plot (default: input_dir/learning_curve.png)")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    metrics_path = input_dir / "metrics.jsonl"
    score_path = input_dir / "score.json"

    if not metrics_path.exists():
        print(f"Error: Metrics file not found at {metrics_path}")
        print("Run training first: python rl/train_adversary.py")
        return 1

    # Load metrics
    print(f"Loading metrics from {metrics_path}")
    metrics = load_metrics(metrics_path)
    print(f"Loaded {len(metrics)} episode records")

    # Load score data if available
    score_data = None
    if score_path.exists():
        with open(score_path, "r") as f:
            score_data = json.load(f)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_dir / "learning_curve.png"

    # Generate plot
    plot_learning_curve(metrics, output_path, score_data)

    return 0


if __name__ == "__main__":
    sys.exit(main())

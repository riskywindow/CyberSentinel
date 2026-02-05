"""
Smoke tests for RL training pipeline.

Runs quick training and verifies outputs are created.
"""

import json
import pytest
import subprocess
import sys
from pathlib import Path


class TestSmokeTraining:
    """Smoke tests for training pipeline."""

    def test_train_creates_metrics_file(self, tmp_path):
        """Training should create metrics.jsonl file."""
        output_dir = tmp_path / "rl_output"

        # Run training with minimal episodes
        result = subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "10",
            "--steps-per-episode", "8",
            "--output-dir", str(output_dir),
            "--no-baseline-comparison",
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)

        # Check process completed
        assert result.returncode in [0, 1], f"Training failed: {result.stderr}"

        # Check metrics file exists and is non-empty
        metrics_path = output_dir / "metrics.jsonl"
        assert metrics_path.exists(), f"metrics.jsonl not created. stdout: {result.stdout}"

        with open(metrics_path) as f:
            lines = f.readlines()

        assert len(lines) == 10, f"Expected 10 metric lines, got {len(lines)}"

        # Verify each line is valid JSON
        for line in lines:
            data = json.loads(line)
            assert "episode" in data
            assert "reward" in data
            assert "success" in data

    def test_train_creates_policy_file(self, tmp_path):
        """Training should create policy.pt file."""
        output_dir = tmp_path / "rl_output"

        result = subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "5",
            "--steps-per-episode", "6",
            "--output-dir", str(output_dir),
            "--no-baseline-comparison",
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)

        assert result.returncode in [0, 1], f"Training failed: {result.stderr}"

        # Check policy file exists
        policy_path = output_dir / "policy.pt"
        assert policy_path.exists() or (output_dir / "policy.npz").exists(), \
            "Neither policy.pt nor policy.npz created"

    def test_train_creates_score_file(self, tmp_path):
        """Training should create score.json file."""
        output_dir = tmp_path / "rl_output"

        result = subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "5",
            "--steps-per-episode", "6",
            "--output-dir", str(output_dir),
            "--no-baseline-comparison",
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)

        assert result.returncode in [0, 1], f"Training failed: {result.stderr}"

        # Check score file
        score_path = output_dir / "score.json"
        assert score_path.exists(), "score.json not created"

        with open(score_path) as f:
            score = json.load(f)

        assert "seed" in score
        assert "episodes" in score
        assert "rl_policy" in score
        assert "mean_reward" in score["rl_policy"]

    def test_train_reproducible_with_seed(self, tmp_path):
        """Same seed should produce identical results."""
        output_dir1 = tmp_path / "run1"
        output_dir2 = tmp_path / "run2"

        # Run 1
        subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "12345",
            "--episodes", "5",
            "--steps-per-episode", "6",
            "--output-dir", str(output_dir1),
            "--no-baseline-comparison",
        ], capture_output=True, cwd=Path(__file__).parent.parent.parent)

        # Run 2 with same seed
        subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "12345",
            "--episodes", "5",
            "--steps-per-episode", "6",
            "--output-dir", str(output_dir2),
            "--no-baseline-comparison",
        ], capture_output=True, cwd=Path(__file__).parent.parent.parent)

        # Load and compare scores
        with open(output_dir1 / "score.json") as f:
            score1 = json.load(f)
        with open(output_dir2 / "score.json") as f:
            score2 = json.load(f)

        # Mean rewards should be identical
        assert score1["rl_policy"]["mean_reward"] == score2["rl_policy"]["mean_reward"]
        assert score1["rl_policy"]["success_rate"] == score2["rl_policy"]["success_rate"]

    def test_train_completes_quickly(self, tmp_path):
        """Training 50 episodes should complete in under 30 seconds."""
        import time

        output_dir = tmp_path / "rl_output"

        start = time.time()
        result = subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "50",
            "--steps-per-episode", "12",
            "--output-dir", str(output_dir),
            "--no-baseline-comparison",
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)
        elapsed = time.time() - start

        assert result.returncode in [0, 1], f"Training failed: {result.stderr}"
        assert elapsed < 30, f"Training took {elapsed:.1f}s, expected < 30s"


class TestSmokeEvaluation:
    """Smoke tests for evaluation pipeline."""

    def test_eval_with_trained_policy(self, tmp_path):
        """Evaluation should work with trained policy."""
        output_dir = tmp_path / "rl_output"

        # First train
        subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "10",
            "--steps-per-episode", "8",
            "--output-dir", str(output_dir),
            "--no-baseline-comparison",
        ], capture_output=True, cwd=Path(__file__).parent.parent.parent)

        # Then evaluate
        result = subprocess.run([
            sys.executable, "-m", "rl.eval_adversary",
            "--seed", "42",
            "--episodes", "5",
            "--policy-path", str(output_dir / "policy.pt"),
            "--output-dir", str(output_dir),
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)

        assert result.returncode == 0, f"Evaluation failed: {result.stderr}"


class TestSmokePlotting:
    """Smoke tests for plotting."""

    def test_plot_creates_output(self, tmp_path):
        """Plotting should create learning_curve.png."""
        output_dir = tmp_path / "rl_output"

        # First train
        subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "10",
            "--steps-per-episode", "8",
            "--output-dir", str(output_dir),
            "--no-baseline-comparison",
        ], capture_output=True, cwd=Path(__file__).parent.parent.parent)

        # Then plot
        result = subprocess.run([
            sys.executable, "-m", "rl.plot_rl",
            "--input-dir", str(output_dir),
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)

        assert result.returncode == 0, f"Plotting failed: {result.stderr}"

        # Check output file exists (either png or txt fallback)
        has_plot = (
            (output_dir / "learning_curve.png").exists() or
            (output_dir / "learning_curve.txt").exists()
        )
        assert has_plot, "No plot output created"


class TestIntegration:
    """Integration tests for full pipeline."""

    def test_full_pipeline(self, tmp_path):
        """Full train -> eval -> plot pipeline should work."""
        output_dir = tmp_path / "rl_output"
        project_root = Path(__file__).parent.parent.parent

        # Train
        train_result = subprocess.run([
            sys.executable, "-m", "rl.train_adversary",
            "--seed", "42",
            "--episodes", "20",
            "--steps-per-episode", "10",
            "--output-dir", str(output_dir),
        ], capture_output=True, text=True, cwd=project_root)

        assert train_result.returncode in [0, 1], f"Training failed: {train_result.stderr}"

        # Eval
        eval_result = subprocess.run([
            sys.executable, "-m", "rl.eval_adversary",
            "--seed", "42",
            "--episodes", "10",
            "--policy-path", str(output_dir / "policy.pt"),
            "--output-dir", str(output_dir),
            "--compare-random",
        ], capture_output=True, text=True, cwd=project_root)

        assert eval_result.returncode == 0, f"Evaluation failed: {eval_result.stderr}"

        # Plot
        plot_result = subprocess.run([
            sys.executable, "-m", "rl.plot_rl",
            "--input-dir", str(output_dir),
        ], capture_output=True, text=True, cwd=project_root)

        assert plot_result.returncode == 0, f"Plotting failed: {plot_result.stderr}"

        # Verify all expected files exist
        assert (output_dir / "metrics.jsonl").exists()
        assert (output_dir / "score.json").exists()
        assert (output_dir / "policy.pt").exists() or (output_dir / "policy.npz").exists()

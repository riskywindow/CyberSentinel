# RL Adversary Training

This document describes the reinforcement learning (RL) system for training adversary agents to select ATT&CK techniques during simulated campaigns.

## Overview

The RL adversary learns to:
- Progress through attack phases (initial access -> exfiltration)
- Avoid detection by the target environment
- Maximize objective completion (data exfiltration)

## Quick Start

```bash
# Clean previous runs and run full smoke test (PG, 50 episodes)
make rl-clean && make rl-smoke

# Run PPO smoke test (200 episodes)
make rl-smoke-ppo

# Train with specific algorithm
make rl-train-pg   # Policy Gradient
make rl-train-ppo  # PPO
```

## State Space

The agent observes a 9-dimensional state vector:

| Dimension | Description | Range |
|-----------|-------------|-------|
| `phase` | Current campaign phase (normalized) | [0, 1] |
| `steps` | Steps taken (normalized) | [0, 1] |
| `detection` | Cumulative detection score (normalized) | [0, 1] |
| `has_initial_access` | Initial access achieved | {0, 1} |
| `has_persistence` | Persistence established | {0, 1} |
| `has_credentials` | Credentials acquired | {0, 1} |
| `has_lateral_access` | Lateral movement achieved | {0, 1} |
| `has_collected_data` | Data collected for exfiltration | {0, 1} |
| `stealth_score` | Current stealth level | [0, 1] |

## Action Space

The agent selects from 12 ATT&CK techniques:

| Action | Technique ID | Name | Phase |
|--------|--------------|------|-------|
| 0 | T1566.001 | Spearphishing Attachment | Initial Access |
| 1 | T1190 | Exploit Public-Facing Application | Initial Access |
| 2 | T1059.003 | Windows Command Shell | Execution |
| 3 | T1053.005 | Scheduled Task | Persistence |
| 4 | T1055 | Process Injection | Privilege Escalation |
| 5 | T1003.001 | LSASS Memory | Credential Access |
| 6 | T1083 | File and Directory Discovery | Discovery |
| 7 | T1135 | Network Share Discovery | Discovery |
| 8 | T1021.001 | Remote Desktop Protocol | Lateral Movement |
| 9 | T1021.004 | SSH | Lateral Movement |
| 10 | T1005 | Data from Local System | Collection |
| 11 | T1041 | Exfiltration Over C2 | Exfiltration |

## Action Masking

The environment enforces **action masking** to hide invalid actions based on the current state:

- Initial access techniques are masked once access is gained
- Lateral movement is masked until credentials are acquired
- Exfiltration is masked until data is collected
- Completed objectives (persistence, credentials, etc.) mask their techniques

**Why it matters:** Action masking prevents the agent from wasting steps on impossible actions and speeds up learning by focusing on valid transitions.

The mask is returned in the `info` dict from both `reset()` and `step()`:

```python
obs, info = env.reset(seed=42)
mask = info["action_mask"]  # Boolean array, True = valid action

obs, reward, done, info = env.step(action)
mask = info["action_mask"]  # Updated mask after action
```

## Reward Structure

Rewards are driven by the **detector adapter** which provides detection signals:

| Event | Reward |
|-------|--------|
| Step advances campaign without detection | +3.0 |
| Objective completes without detection | +6.0 |
| Detected while advancing (stealth failure) | +2.0 |
| Wasted action (no state change) | -0.5 |
| Step cost (every step) | -0.1 |
| Lockout (too many detections) | -5.0 |

### Detector Adapter

The `DetectorAdapter` class provides detection signals:

```python
from redteam.envs import DetectorAdapter

# Stub detector (fast, deterministic)
adapter = DetectorAdapter(use_real=False, seed=42)

# Real detector (uses evaluation harness)
adapter = DetectorAdapter(use_real=True)

result = adapter.evaluate("T1566.001", {"step": 0, "phase": 0})
# Returns: {"detected": bool, "latency_ms": int, "extra": dict}
```

**Switch between detectors** using the `--use-real-detector` flag:

```bash
# Use stub (default, fast)
python rl/train_adversary.py --algo pg --episodes 50

# Use real detector
python rl/train_adversary.py --algo pg --episodes 50 --use-real-detector
```

## Algorithms

### Policy Gradient (PG)

Simple REINFORCE algorithm with:
- Reward-to-go for variance reduction
- Running mean baseline
- Entropy regularization

**Best for:** Quick experiments, debugging, smoke tests

```bash
python rl/train_adversary.py --algo pg --episodes 50
```

### Proximal Policy Optimization (PPO)

More sophisticated algorithm with:
- Clipped surrogate objective
- Generalized Advantage Estimation (GAE)
- Separate value function
- Multiple epochs per batch

**Best for:** Better performance, longer training runs

```bash
python rl/train_adversary.py --algo ppo --episodes 200
```

### Hyperparameters

| Parameter | PG Default | PPO Default | Description |
|-----------|------------|-------------|-------------|
| `--lr` | 0.001 | 0.0003 | Learning rate |
| `--gamma` | 0.99 | 0.99 | Discount factor |
| `--entropy-coef` | 0.01 | 0.01 | Entropy bonus |
| `--clip-ratio` | - | 0.2 | PPO clip ratio |
| `--gae-lambda` | - | 0.95 | GAE lambda |
| `--hidden-dim` | 64 | 64 | Hidden layer size |

## CLI Reference

### Training

```bash
python rl/train_adversary.py [options]

Options:
  --algo {pg,ppo}         Algorithm (default: pg)
  --seed INT              Random seed (default: $SEED or 42)
  --episodes INT          Number of episodes (default: 50)
  --steps-per-episode INT Maximum steps (default: 12)
  --hidden-dim INT        Hidden layer size (default: 64)
  --lr FLOAT              Learning rate (default: 0.001)
  --gamma FLOAT           Discount factor (default: 0.99)
  --entropy-coef FLOAT    Entropy coefficient (default: 0.01)
  --clip-ratio FLOAT      PPO clip ratio (default: 0.2)
  --gae-lambda FLOAT      GAE lambda (default: 0.95)
  --output-dir PATH       Output directory (default: eval/rl)
  --use-real-detector     Use real detector instead of stub
  --no-baseline-comparison Skip random baseline
  --no-traces             Skip writing episode traces
  -v, --verbose           Verbose output
```

### Evaluation

```bash
python rl/eval_adversary.py [options]

Options:
  --seed INT              Random seed
  --episodes INT          Number of eval episodes (default: 20)
  --policy-path PATH      Path to trained policy (default: eval/rl/policy.pt)
  --output-dir PATH       Output directory
  --deterministic         Use greedy action selection
  --compare-random        Compare with random baseline
```

### Plotting

```bash
python rl/plot_rl.py [options]

Options:
  --input-dir PATH        Directory with metrics.jsonl (default: eval/rl)
  --output PATH           Output path for plot
```

## Output Files

After training, the following files are created in `eval/rl/`:

| File | Description |
|------|-------------|
| `policy.npz` | Trained policy weights (NumPy format) |
| `policy.pt` | Trained policy weights (PyTorch format, if available) |
| `metrics.jsonl` | Per-episode training metrics |
| `traces.jsonl` | Step-level episode traces |
| `score.json` | Training summary (JSON) |
| `summary.md` | Human-readable summary |
| `learning_curve.png` | Learning curve visualization |

### traces.jsonl Format

Each line contains a step trace:

```json
{
  "seed": 42,
  "episode": 0,
  "step": 0,
  "phase": 0,
  "action_id": 0,
  "action_name": "T1566.001",
  "masked": false,
  "reward": 2.9,
  "cumulative_reward": 2.9,
  "detected": false,
  "latency_ms": 75,
  "success": true,
  "reward_type": "advance_undetected"
}
```

### summary.md Format

```markdown
# RL Adversary Training Summary

**Seed:** 42
**Episodes:** 50
**Algorithm:** pg

## Results

| Metric | Random | PG |
|--------|--------|-----|
| Mean Reward | -0.5 | 2.3 |
| Success Rate | 5% | 15% |

**Reward Improvement:** +2.8
**Learning Detected:** Yes
```

## Determinism

The training is **deterministic by default** when using the same seed:

```bash
# These two runs produce identical results
SEED=42 make rl-smoke
SEED=42 make rl-smoke

# Verify by comparing policy hashes in score.json
```

### SEED Rules

1. **Environment variable:** `SEED=42 make rl-smoke`
2. **CLI flag:** `python rl/train_adversary.py --seed 42`
3. **Default:** If neither is set, defaults to 42

The seed controls:
- NumPy random state
- PyTorch random state (if available)
- Environment episode seeds
- Detector stub behavior

### Reproducibility Verification

```bash
# Run twice
SEED=12345 python rl/train_adversary.py --output-dir /tmp/run1
SEED=12345 python rl/train_adversary.py --output-dir /tmp/run2

# Compare
diff /tmp/run1/score.json /tmp/run2/score.json  # Should be identical
sha256sum /tmp/run1/policy.npz /tmp/run2/policy.npz  # Should match
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `rl-clean` | Clean eval/rl/ outputs |
| `rl-train-pg` | Train with PG (200 episodes) |
| `rl-train-ppo` | Train with PPO (200 episodes) |
| `rl-eval` | Evaluate trained policy |
| `rl-plot` | Generate learning curves |
| `rl-smoke` | Full smoke test (PG, 50 episodes) |
| `rl-smoke-ppo` | PPO smoke test (200 episodes) |
| `test-rl` | Run RL unit tests |

## Tests

```bash
# All RL tests
make test-rl

# Individual test files
pytest tests/rl/test_action_mask.py -v    # Action masking tests
pytest tests/rl/test_reward_signal.py -v  # Reward signal tests
pytest tests/rl/test_ppo_smoke.py -v      # PPO smoke tests
```

## Extending the System

### Custom Environment Configuration

```python
from redteam.envs import AttackEnv, EnvConfig

config = EnvConfig(
    max_steps=20,                    # Longer episodes
    detection_threshold=5.0,         # More forgiving detection
    security_level=0.3,              # Easier target
    advance_no_detect_reward=5.0,    # Higher progress reward
    use_real_detector=True,          # Use real evaluation harness
)
env = AttackEnv(config)
```

### Using the Detector Adapter

```python
from redteam.envs import DetectorAdapter

# Create adapter
adapter = DetectorAdapter(use_real=False, seed=42)

# Evaluate a technique
result = adapter.evaluate(
    technique_id="T1566.001",
    context={
        "step": 0,
        "phase": 0,
        "stealth_score": 1.0,
        "security_level": 0.5,
    }
)

print(f"Detected: {result['detected']}")
print(f"Latency: {result['latency_ms']}ms")
print(f"Extra: {result['extra']}")
```

### Loading a Trained Policy

```python
from redteam.envs import AttackEnv
from redteam.policy import PolicyNetwork, ActorCriticNetwork

env = AttackEnv()

# For PG policy
policy = PolicyNetwork(obs_dim=env.obs_dim, n_actions=env.n_actions)
policy.load("eval/rl/policy.pt")

# For PPO policy
network = ActorCriticNetwork(obs_dim=env.obs_dim, n_actions=env.n_actions)
network.load("eval/rl/policy.pt")

# Run episode
obs, info = env.reset(seed=42)
mask = info["action_mask"]

while True:
    action, _ = policy.sample_action(obs, mask)
    obs, reward, done, info = env.step(action)
    mask = info["action_mask"]
    print(f"Action: {env.techniques[action]}, Reward: {reward:.2f}")
    if done:
        break
```

## Dependencies

The RL system has minimal dependencies:
- **NumPy**: Required for all operations
- **PyTorch** (optional): Preferred for policy networks if available
- **Matplotlib** (optional): For generating learning curves

The system automatically falls back to NumPy-only implementations if PyTorch is not available.

# RL Adversary Training Summary

**Seed:** 42
**Episodes:** 50
**Algorithm:** pg
**Training Time:** 0.12s

## Results

| Metric | Random | PG |
|--------|--------|-----|
| Mean Reward | 6.568 | 5.750 |
| Success Rate | 30.0% | 28.0% |

**Reward Improvement:** -0.818
**Learning Detected:** No

## Files

- `policy.npz` - Trained policy weights
- `metrics.jsonl` - Per-episode metrics
- `traces.jsonl` - Step-level traces
- `score.json` - Training summary (JSON)
- `learning_curve.png` - Learning curve plot

## Reproduce

```bash
SEED=42 make rl-smoke
```
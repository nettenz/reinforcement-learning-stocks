# Gemini Experiment Session

## Last Updated
2026-03-30 — Stationary Sweep Complete: GENERALIZATION IMPROVED, ALPHA PENDING

## Project State
- Algorithm: PPO (Transitioning to SAC)
- Observation space: **STATIONARY FEATURES (FIXED)**
- Action space: discrete Buy/Sell/Hold (Current bottleneck)
- Look-ahead bias: FIXED
- Reward direction scale: 0.40 (Optimal in sweep, but returns still near zero)

## Latest Run: stationary-direction-sweep
**Configuration:**
- Seeds: 3 (7, 13, 42)
- Timesteps: 20k per run
- Features: Log returns, RelRange, RelMACD, RSI_Centered (Stationary)
- Device: **CPU** (Verified 10x faster than MPS for this architecture)

**Results:**
| Metric | Value | Status |
|---|---|---|
| Mean test accuracy | 0.517 ± 0.005 | **STABLE** |
| Best test accuracy | 0.524 | Solid |
| Mean test return | -0.016 to -0.10 | **LOW (Zero Alpha)** |
| Collapse rate | ~33% (Seed 13 consistently collapsed) | High for Seed 13 |
| **Val/Test gap** | **0.06** | **GREATLY IMPROVED** |

**Interpretation:**
The migration to stationary features was a success for generalization. The catastrophic val/test gap dropped from ~0.37 to ~0.06. However, the model now lacks the "conviction" to generate positive returns in a discrete action space. The agent is either over-cautious or the Buy/Sell signals are too noisy at this resolution.

## Root Cause Analysis (Updated)

### ISSUE 1: Discrete Action Space (PRIMARY)
**Problem:** A discrete 3-action space (Buy/Sell/Hold) forces binary 100% position shifts. On stationary features (which have lower signal-to-noise than raw prices), the model cannot express "weak conviction" or "partial position sizing".

**Fix Required:**
Migrate to SAC with a continuous action space `Box([-1, 1])`. This will allow the model to learn a mapping from stationary signals to optimal position sizes.

### ISSUE 2: Training Convergence
**Problem:** 20k timesteps might be too few for stationary features, which are more subtle than raw price levels.

**Fix Required:**
Increase timesteps to 50k-100k for the first SAC runs.

## Configs Ruled Out
- Raw OHLCV features — confirmed as the source of catastrophic overfitting.
- MPS acceleration — confirmed 10x slower than CPU for this MLP-based PPO model.

## Next Steps for Copilot

### PHASE 3: SAC Migration (URGENT)
1. **Update `src/trading_env.py`:**
   - Add `continuous_actions=False` flag to `__init__`.
   - If `True`, set `action_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)`.
   - Update `step()` to handle continuous values (mapping [-1, 1] to target position).

2. **Update `src/train_bot.py` & `src/experiments.py`:**
   - Support `--algo SAC`.
   - Integrate `SAC` from `stable_baselines3`.
   - Ensure the experiment runner can switch between algorithms and action spaces.

3. **Validation Run:**
   - Run SAC with stationary features on 3 seeds.
   - Target: Positive test return (> 5%) and stable accuracy (> 0.52).

## Next Experiment Command
```bash
# After SAC migration is implemented:
.venv/bin/python3 src/train_bot.py \
  --algo SAC \
  --include-news \
  --use-stationary-features \
  --continuous-actions \
  --timesteps 50000 \
  --device cpu
```

## Autonomy Status
- [ ] Continuing autonomously
- [X] **ESCALATING TO COPILOT** — Reason: SAC and Continuous Action Space implementation required.

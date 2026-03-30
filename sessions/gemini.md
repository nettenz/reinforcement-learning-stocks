# Gemini Experiment Session

## Last Updated
2026-03-30 — CPU PPO Follow-up Sweeps Completed (stability/accuracy/generalization)

## Project State
- Algorithm: PPO (Transitioning to SAC)
- Observation space: **STATIONARY FEATURES (FIXED)**
- Action space: discrete Buy/Sell/Hold (Current bottleneck)
- Look-ahead bias: FIXED
- Reward direction scale: 0.40 (Optimal in sweep, but returns still near zero)

## Latest Run: insights-generalization (CPU)
**Configuration:**
- Seeds: 3 (7, 13, 42)
- Timesteps: 20k per run
- Features: Log returns, RelRange, RelMACD, RSI_Centered (Stationary)
- Device: **CPU** (Verified 10x faster than MPS for this architecture)

**Results (previous stationary-direction-sweep baseline):**
| Metric | Value | Status |
|---|---|---|
| Mean test accuracy | 0.517 ± 0.005 | **STABLE** |
| Best test accuracy | 0.524 | Solid |
| Mean test return | -0.016 to -0.10 | **LOW (Zero Alpha)** |
| Collapse rate | ~33% (Seed 13 consistently collapsed) | High for Seed 13 |
| **Val/Test gap** | **0.06** | **GREATLY IMPROVED** |

**Interpretation:**
The migration to stationary features was a success for generalization. The catastrophic val/test gap dropped from ~0.37 to ~0.06. However, the model now lacks the "conviction" to generate positive returns in a discrete action space. The agent is either over-cautious or the Buy/Sell signals are too noisy at this resolution.

## New CPU Follow-up Runs (Completed)
All three recommendation sweeps were executed on Windows with `--device cpu`.

| Run Label | Top Seed | Ranking Score | Val Actionable | Test Actionable | Test Cumulative Return | Collapse Rate |
|---|---:|---:|---:|---:|---:|---:|
| insights-stability | 13 | 0.5739 | 0.6061 | 0.5308 | 0.2036 | 0.0% |
| insights-accuracy | 13 | 0.5739 | 0.6061 | 0.5303 | 0.1732 | 0.0% |
| insights-generalization | 7 | **0.5943** | 0.5957 | 0.5303 | 0.1732 | 0.0% |

**Outcome Summary:**
- Collapse signatures were eliminated in these 3-seed sweeps (0%).
- Test actionable accuracy held around ~0.53 across all three variants.
- Generalization run produced the best ranking score among the follow-ups.
- Positive test cumulative signal returns were observed in all follow-ups (17%–20%).

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

---

### DELEGATED_RESULTS (2026-03-30 07:26:15Z)
run_label: insights-generalization
snapshot_leaderboard_path: data\experiment_snapshots\experiment_leaderboard_20260330-063455Z_insights-generalization.csv
best_seed: 7
best_val_actionable_accuracy: 0.5957
best_test_actionable_accuracy: 0.5303
best_ranking_score: 0.5943
best_test_cumulative_signal_return: 0.1732
compare_vs_baseline: tied - Actionable accuracy remained around ~0.53 with stable multi-seed behavior and positive test returns.
next_single_command: .\.venv\Scripts\python.exe src\experiments.py --include-news --seeds 7,13,21,42,99 --timesteps 50000 --learning-rates 0.0003,0.0001 --gammas 0.994,0.997 --ent-coefs 0.01,0.02 --reward-action-bonus-scale 0.005,0.01,0.02 --reward-drawdown-penalty-scale 0.1,0.2,0.4 --max-runs 30 --run-label sharpe-sortino-qqq-refresh --device cpu

- Integrated Sharpe/Sortino/Max Drawdown + QQQ benchmark into `src\experiments.py`; current snapshot above predates these new columns.
- Next experiment should refresh leaderboard outputs to include risk-adjusted metrics and alpha-vs-QQQ columns.
- Keep stationary features and CPU for comparability with prior Gemini sweeps.

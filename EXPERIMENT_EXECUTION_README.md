# Experiment Batch Execution Guide

**Handoff Date**: 2026-04-10 08:24 UTC  
**Focus**: NVDA Phase 1-3 Robustness Improvements  
**Objective**: Improve test accuracy from 50% to 55%+ and reduce config CV from 9.43 to < 2.0

---

## Quick Start

### Prerequisites
1. Activate virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Verify data files exist:
   - `data/experiment_leaderboard.csv` (main)
   - `data/nvda_val.csv` (validation data)
   - `data/nvda_test.csv` (test data)

3. Read the strategy document:
   - `C:\Users\Emanuel\.copilot\session-state\b8954cc9-8288-4541-a2aa-cec04b0568ef\EXPERIMENT_STRATEGY_HANDOFF.md`

---

## Experiment Execution Order

### **STEP 1: Regime Diagnostics (30 minutes, no GPU)**

**File**: `run_validation_regime_diagnostics.py`

```powershell
.\.venv\Scripts\Activate.ps1
python run_validation_regime_diagnostics.py
```

**Output**:
- Console report with volatility, Sharpe, drawdown comparisons
- File: `data/regime_analysis.json`

**What to Check**:
- If `volatility_diff_pct > -20%`: Validation is easier (likely culprit for val-test gap)
- If `regime_shifts == 0`: Val-test gap is reward function issue, not data
- Decision: If regime similar, proceed directly to Exp 1

**⏱️ Elapsed Time**: 30 min

---

### **STEP 2: Entropy Schedule Ablation (2.5-3.5 hours, 15 GPU hours)**

**File**: `run_entropy_schedule_ablation.ps1`

```powershell
.\run_entropy_schedule_ablation.ps1
```

**What It Tests**:
- Treatment A: Fixed entropy 0.06 (no decay schedule)
- Treatment B: Decaying entropy 0.06 (control)
- Treatment C: Fixed entropy 0.08 (more exploration)

**Output**:
- 15 new leaderboard rows (3 treatments × 5 seeds)
- Column: `test_return_cv_by_config` (target: < 3.0 for best treatment)

**What to Check**:
- Which treatment has lowest `test_return_cv_by_config`?
- Do all 5 seeds cluster within ±10% `test_actionable_accuracy`?
- Is `test_alpha_vs_qqq` improving (less negative)?

**Record for Next Experiment**:
- Best entropy_schedule ("fixed" or "decay")
- Best ent_coef value

**Success Threshold**: `test_return_cv_by_config < 3.0` for winner

**⏱️ Cumulative Time**: 2.5-3.5 hours

---

### **STEP 3: Reward Calibration Sweep (2.5-3.5 hours, 15-18 GPU hours)**

**File**: `run_reward_calibration_sweep.ps1`

Before running, edit the script to set entropy params from Exp 2:

```powershell
# Near top of script, set these from Exp 2 results:
[double]$EntCoef = 0.06               # From Exp 2 best
[string]$EntropySchedule = "fixed"    # From Exp 2 best: "fixed" or "decay"
```

Then run:
```powershell
.\run_reward_calibration_sweep.ps1
```

**What It Tests**:
- Treatment A: reward_clip=2.0 (higher clip)
- Treatment B: reward_drawdown_penalty=0.10 (lower penalty)
- Treatment C: reward_turnover_penalty=0.02 (lower penalty)
- Treatment D: Control (current settings)

**Output**:
- 20 new leaderboard rows (4 treatments × 5 seeds)

**What to Check**:
- Which treatment has lowest `test_return_cv_by_config`?
- Is `test_alpha_vs_qqq` improving (less negative)?
- Is `test_actionable_accuracy` maintained >= 50%?

**Record for Next Experiment**:
- Best reward_clip value
- Best reward_drawdown_penalty_scale value
- Best reward_turnover_penalty_scale value

**Success Threshold**: `test_return_cv_by_config < 2.5` for winner

**⏱️ Cumulative Time**: 5-7 hours

---

### **CHECKPOINT: After Exp 2 + 3**

Before proceeding, verify improvements:
```
[ ] Config CV < 2.5 (was 9.43)?
[ ] Test alpha >= -100bp (was -150bp)?
[ ] Test accuracy >= 50% (maintained)?
```

If NO on any criterion, PAUSE and diagnose before Exp 4.

**⏱️ Cumulative Time**: 5-7 hours

---

### **STEP 4: Timesteps Optimization (3-4 hours, 10-12 GPU hours)**

**File**: `run_timesteps_optimization.ps1`

Before running, edit the script to set best params from Exp 2 & 3:

```powershell
[double]$EntCoef = 0.06               # From Exp 2 best
[string]$EntropySchedule = "fixed"    # From Exp 2 best
[double]$RewardClip = 1.0             # From Exp 3 best
[double]$DrawdownPenalty = 0.15       # From Exp 3 best
[double]$TurnoverPenalty = 0.05       # From Exp 3 best
```

Then run:
```powershell
.\run_timesteps_optimization.ps1
```

**What It Tests**:
- Timesteps: [10000, 15000, 20000, 25000, 30000]
- Using 3 seeds (reduced for cost)

**Output**:
- 15 new leaderboard rows (5 timesteps × 3 seeds)

**What to Check**:
- At which timesteps is `test_actionable_accuracy` highest?
- Is 20k local optimum, or is there a better value?
- Plot test_accuracy vs timesteps to visualize curve

**Record for Next Experiment**:
- Best timesteps value
- Peak test_accuracy at that timesteps

**Success Threshold**: Peak accuracy >= 50% AND cv < 2.0

**⏱️ Cumulative Time**: 8-11 hours

---

### **STEP 5: Sharpe vs Sortino Retest (2.5-3.5 hours, 12-15 GPU hours)**

**File**: `run_mode_comparison.ps1`

Before running, edit the script to set all best params from Exp 2, 3, 4:

```powershell
[int]$Timesteps = 20000               # From Exp 4 best
[double]$EntCoef = 0.06               # From Exp 2 best
[string]$EntropySchedule = "fixed"    # From Exp 2 best
[double]$RewardClip = 1.0             # From Exp 3 best
[double]$DrawdownPenalty = 0.15       # From Exp 3 best
[double]$TurnoverPenalty = 0.05       # From Exp 3 best
```

Then run:
```powershell
.\run_mode_comparison.ps1
```

**What It Tests**:
- reward_mode=sharpe with best params
- reward_mode=sortino with best params
- Using full 5 seed set for statistical significance

**Output**:
- 10 new leaderboard rows (2 modes × 5 seeds)

**What to Check**:
- Sharpe avg test_accuracy vs Sortino
- If Sharpe >= 50% AND Sortino < 45%: Clear winner
- If both similar: Sharpe wins by default (simpler)

**Record for Final Configuration**:
- Winning reward_mode (likely "sharpe")

**Success Threshold**: Winner achieves >= 50% test accuracy

**⏱️ Cumulative Time**: 11-14.5 hours

---

## Post-Experiment Analysis

### Leaderboard Review

After all experiments complete, run this analysis:

```python
import pandas as pd

lb = pd.read_csv('data/experiment_leaderboard.csv')
lb_v2 = lb[lb['leaderboard_version'] == 2]

# Filter to experiment runs
exp_runs = lb_v2[lb_v2['run_label'].str.contains('entropy|reward-calib|timesteps-opt|mode-compare', na=False)]

print("=" * 80)
print("EXPERIMENT RESULTS SUMMARY")
print("=" * 80)

# Exp 1 results
exp1 = exp_runs[exp_runs['run_label'].str.contains('entropy', na=False)]
print("\nEXP 1: ENTROPY SCHEDULE (by treatment)")
for treatment in exp1['run_label'].unique():
    subset = exp1[exp1['run_label'].str.contains(treatment, na=False)]
    print(f"  {treatment:40s}: avg_acc={subset['test_actionable_accuracy'].mean():.3f}, cv={subset['test_return_cv_by_config'].mean():.2f}")

# Exp 3 results
exp3 = exp_runs[exp_runs['run_label'].str.contains('reward-calib', na=False)]
print("\nEXP 3: REWARD CALIBRATION (by treatment)")
for treatment in ['clip', 'dd-penalty', 'to-penalty', 'control']:
    subset = exp3[exp3['run_label'].str.contains(treatment, na=False)]
    if len(subset) > 0:
        print(f"  {treatment:40s}: avg_acc={subset['test_actionable_accuracy'].mean():.3f}, cv={subset['test_return_cv_by_config'].mean():.2f}, alpha={subset['test_alpha_vs_qqq'].mean():.4f}")

# Exp 4 results
exp4 = exp_runs[exp_runs['run_label'].str.contains('timesteps-opt', na=False)]
print("\nEXP 4: TIMESTEPS OPTIMIZATION (by timesteps)")
for ts in exp4['timesteps'].unique():
    subset = exp4[exp4['timesteps'] == ts]
    print(f"  {int(ts):6d} steps: avg_acc={subset['test_actionable_accuracy'].mean():.3f}, cv={subset['test_return_cv_by_config'].mean():.2f}")

# Exp 5 results
exp5 = exp_runs[exp_runs['run_label'].str.contains('mode-compare', na=False)]
print("\nEXP 5: MODE COMPARISON (by reward mode)")
for mode in exp5['reward_mode'].unique():
    subset = exp5[exp5['reward_mode'] == mode]
    print(f"  {mode:40s}: avg_acc={subset['test_actionable_accuracy'].mean():.3f}, cv={subset['test_return_cv_by_config'].mean():.2f}")

print("\n" + "=" * 80)
```

---

## Promotion Re-Evaluation

Once all experiments complete, assemble best-found config and test on seeds [7,13,21,27,123]:

**Expected Best Config**:
```
reward_mode:          sharpe (or sortino)
ent_coef:             0.06
entropy_schedule:     fixed (from Exp 1)
timesteps:            20000 (or best from Exp 4)
reward_clip:          1.0 or 2.0 (from Exp 3)
reward_drawdown_penalty_scale: 0.15 or 0.10 (from Exp 3)
reward_turnover_penalty_scale: 0.05 or 0.02 (from Exp 3)
transaction_cost_rate: 0.001
other params:         unchanged from Phase 3
```

**Check These Promotion Gates**:
```
[ ] test_actionable_accuracy >= 0.53       (TARGET: 0.55+)
[ ] test_trade_win_rate >= 0.52            (TARGET: 0.55+)
[ ] test_alpha_vs_qqq >= 0.00              (TARGET: +50bp)
[ ] |val_acc - test_acc| <= 0.05           (TARGET: < 0.05)
[ ] test_return_cv_by_config < 1.0         (TARGET: 0.5-1.0)
```

**Promotion Decision**:
- 5/5 gates: READY FOR PROMOTION ✅
- 4/5 gates: CONDITIONAL (depends on which gate failed)
- 3/5 or fewer: NOT READY (escalate to reward architect)

---

## Troubleshooting

### Q: Experiment script fails with "model_path not found"
**A**: Ensure model files exist in `data/experiment_snapshots/` or check that `--append` flag is working correctly.

### Q: GPU is running out of memory
**A**: Reduce batch size in `src/experiments.py` or run fewer seeds per experiment.

### Q: Results are much worse than Phase 3
**A**: Check that you're using correct param values from previous experiments. Verify `--append` is adding to correct leaderboard.

### Q: Config CV stays above 3.0 after Exp 1
**A**: Root cause is not entropy schedule. Proceed to Exp 3 (reward calibration) which is more likely culprit.

### Q: Test alpha stays negative after Exp 3
**A**: May indicate market data quality issue or benchmark calculation problem. Escalate to strategy team.

---

## Key Parameters to Track

Create a file `experiment_tracking.txt`:

```
EXPERIMENT TRACKING LOG
Generated: 2026-04-10 08:24 UTC

EXPERIMENT 1: ENTROPY SCHEDULE
  Best Treatment:    ____________
  Best entropy_schedule ("fixed" or "decay"): ____________
  Best ent_coef:     ____________
  Test CV achieved:  ____________ (target: < 3.0)
  
EXPERIMENT 2: REWARD CALIBRATION
  Best Treatment:    ____________
  Best reward_clip:  ____________
  Best dd_penalty:   ____________
  Best to_penalty:   ____________
  Test CV achieved:  ____________ (target: < 2.5)
  Test alpha:        ____________ (target: >= -100bp)
  
EXPERIMENT 3: TIMESTEPS
  Best timesteps:    ____________ (target: >= 50% accuracy, < 2.0 cv)
  Test accuracy:     ____________
  Test CV:           ____________
  
EXPERIMENT 4: MODE COMPARISON
  Winning mode:      ____________ (expected: sharpe)
  Sharpe accuracy:   ____________
  Sortino accuracy:  ____________
  
BEST CONFIG SUMMARY:
  reward_mode:       ____________
  ent_coef:          ____________
  entropy_schedule:  ____________
  timesteps:         ____________
  reward_clip:       ____________
  dd_penalty:        ____________
  to_penalty:        ____________
```

---

## Total Timeline

| Experiment | Time | GPU Hours | Cumulative Time |
|-----------|------|-----------|-----------------|
| Diagnostic (Exp 0) | 0.5 hr | 0 | 0.5 hr |
| Entropy Ablation (Exp 1) | 3 hrs | 15 | 3.5 hrs |
| Reward Calib (Exp 3) | 3 hrs | 18 | 6.5 hrs |
| Timesteps Opt (Exp 4) | 3.5 hrs | 12 | 10 hrs |
| Mode Compare (Exp 5) | 3 hrs | 15 | 13 hrs |
| **TOTAL** | **13.5 hrs** | **60** | **13.5 hrs** |

---

## Success Metrics (Final)

After all experiments:

```
[ ] Config CV reduced from 9.43 to < 1.0
[ ] Test alpha improved from -150bp to >= -50bp
[ ] Test accuracy stable >= 50% across all seeds
[ ] Val-test gap reduced from 50% to < 5%
[ ] 4+ promotion gates passed
[ ] Ready for deployment testing
```

---

**Generated by**: Quant Experiment Strategist  
**Session**: b8954cc9-8288-4541-a2aa-cec04b0568ef  
**Handoff Date**: 2026-04-10 08:24 UTC

Good luck! 🚀

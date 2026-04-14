# 🎯 Quick Reference Card

## Experiment Execution Checklist

### Pre-Experiment (5 min)
- [ ] Activate `.venv`: `.\.venv\Scripts\Activate.ps1`
- [ ] Read today's experiment section from `EXPERIMENT_EXECUTION_README.md`
- [ ] Check script params match previous experiment results
- [ ] Have `EXPERIMENT_STRATEGY_HANDOFF.md` nearby for questions

---

## Experiment 0: Regime Diagnostics ⏱️ 30 min

```bash
python run_validation_regime_diagnostics.py
```

**Output**: `data/regime_analysis.json`

**Decision Point**:
- Volatility diff > -20%? → Validation is easier (regime shift likely)
- Sharpe diff > 0.5pp? → Market conditions differ
- If no shifts: Val-test gap is reward function issue (not data)

**Next**: Proceed to Exp 1

---

## Experiment 1: Entropy Schedule Ablation ⏱️ 2.5-3.5 hrs

```bash
.\run_entropy_schedule_ablation.ps1
```

**After Run**:
1. Filter leaderboard to `run_label` containing "entropy"
2. For each treatment, find lowest `test_return_cv_by_config`
3. Record winner's `ent_coef` value
4. Record winner's entropy schedule ("fixed" or "decay")

**Success**: Best treatment achieves `cv < 3.0` (was 9.43)

**Next**: Edit `run_reward_calibration_sweep.ps1`, set `$EntCoef`, `$EntropySchedule`

---

## Experiment 3: Reward Calibration ⏱️ 2.5-3.5 hrs

**Before Running**:
```powershell
# Edit run_reward_calibration_sweep.ps1
[double]$EntCoef = X.XX               # From Exp 1 best
[string]$EntropySchedule = "fixed"    # From Exp 1 best
```

```bash
.\run_reward_calibration_sweep.ps1
```

**After Run**:
1. Filter leaderboard to `run_label` containing "reward-calib"
2. For each treatment, calculate:
   - Lowest `test_return_cv_by_config` ← Primary goal
   - Highest `test_alpha_vs_qqq` ← Secondary goal
   - Maintained `test_actionable_accuracy >= 50%` ← Must check
3. Record winner's reward params

**Success**: Best treatment achieves:
- `cv < 2.5` (was 9.43)
- `test_alpha >= -100bp` (was -150bp)
- `test_acc >= 50%` (maintained)

**Checkpoint**:
```
[ ] Config CV < 2.5?        YES  NO
[ ] Test alpha >= -100bp?   YES  NO
[ ] Test acc >= 50%?        YES  NO
```
If NO: Diagnose before Exp 4. If YES: Continue.

**Next**: Edit `run_timesteps_optimization.ps1`, set all params from Exp 1 & 3

---

## Experiment 4: Timesteps Optimization ⏱️ 3-4 hrs

**Before Running**:
```powershell
# Edit run_timesteps_optimization.ps1
[int]$Timesteps = @(10000, 15000, 20000, 25000, 30000)
[double]$EntCoef = X.XX               # From Exp 1 best
[string]$EntropySchedule = "fixed"    # From Exp 1 best
[double]$RewardClip = X.X             # From Exp 3 best
[double]$DrawdownPenalty = X.XX       # From Exp 3 best
[double]$TurnoverPenalty = X.XX       # From Exp 3 best
```

```bash
.\run_timesteps_optimization.ps1
```

**After Run**:
1. Filter leaderboard to `run_label` containing "timesteps-opt"
2. Group by `timesteps`, calculate mean `test_actionable_accuracy` per group
3. Find peak; check if it's 20k or different value
4. Record best `timesteps` value

**Success**: Peak accuracy >= 50% AND cv < 2.0

**Next**: Edit `run_mode_comparison.ps1`, set all params from Exp 1, 3, 4

---

## Experiment 5: Mode Comparison ⏱️ 2.5-3.5 hrs

**Before Running**:
```powershell
# Edit run_mode_comparison.ps1
[int]$Timesteps = XXXXX               # From Exp 4 best
[double]$EntCoef = X.XX               # From Exp 1 best
[string]$EntropySchedule = "fixed"    # From Exp 1 best
[double]$RewardClip = X.X             # From Exp 3 best
[double]$DrawdownPenalty = X.XX       # From Exp 3 best
[double]$TurnoverPenalty = X.XX       # From Exp 3 best
```

```bash
.\run_mode_comparison.ps1
```

**After Run**:
1. Filter leaderboard to `run_label` containing "mode-compare"
2. Group by `reward_mode` ("sharpe" vs "sortino")
3. Calculate mean `test_actionable_accuracy` for each mode

**Decision**:
- Sharpe >= 50% AND Sortino < 45%? → Use Sharpe
- Both >= 48%? → Use Sharpe (simpler, default)
- Sortino wins? → Investigate (note: unexpected result)

**Success**: Winner achieves >= 50% test accuracy

---

## Post-Experiment: Promotion Re-Evaluation

**Assemble Best Config**:
```
reward_mode:          [FROM EXP 5]
ent_coef:             [FROM EXP 1]
entropy_schedule:     [FROM EXP 1]
timesteps:            [FROM EXP 4]
reward_clip:          [FROM EXP 3]
dd_penalty:           [FROM EXP 3]
to_penalty:           [FROM EXP 3]
transaction_cost_rate: 0.001 (unchanged)
other params:         unchanged
```

**Check Promotion Gates**:
```
Gate 1: test_actionable_accuracy >= 0.53
  Current: 0.500  Target: 0.55+  Status: [ ] PASS

Gate 2: test_trade_win_rate >= 0.52
  Current: 0.531  Target: 0.55+  Status: [ ] PASS

Gate 3: test_alpha_vs_qqq >= 0.00
  Current: -0.150 Target: +0.05  Status: [ ] PASS

Gate 4: |val_actionable_accuracy - test_actionable_accuracy| <= 0.05
  Current: 0.500  Target: < 0.05 Status: [ ] PASS

Gate 5: test_return_cv_by_config < 1.0
  Current: 9.43   Target: 0.5-1.0 Status: [ ] PASS
```

**Final Decision**:
- 5/5 gates: ✅ READY FOR PROMOTION
- 4/5 gates: ⚠️ CONDITIONAL (note which gate failed)
- 3/5 or fewer: ❌ NOT READY (escalate)

---

## 🔍 Key Metrics to Track

Print these after each experiment:

```python
import pandas as pd

lb = pd.read_csv('data/experiment_leaderboard.csv')

# Last N rows (new experiment runs)
new_runs = lb.tail(50)  # Adjust as needed

# Group by run label (experiment)
for label in new_runs['run_label'].unique():
    subset = new_runs[new_runs['run_label'].str.contains(label, na=False)]
    print(f"\n{label}:")
    print(f"  Count:           {len(subset)}")
    print(f"  Acc (mean/std):  {subset['test_actionable_accuracy'].mean():.3f} ± {subset['test_actionable_accuracy'].std():.3f}")
    print(f"  CV (mean):       {subset['test_return_cv_by_config'].mean():.2f}")
    print(f"  Alpha (mean):    {subset['test_alpha_vs_qqq'].mean():.4f}")
    print(f"  Sharpe (mean):   {subset['test_sharpe_ratio'].mean():.3f}")
```

---

## ⏰ Timeline at a Glance

| Exp | Duration | GPU Hrs | Cumulative |
|-----|----------|---------|-----------|
| 0   | 0.5h     | 0       | 0.5h      |
| 1   | 3h       | 15      | 3.5h      |
| 3   | 3h       | 18      | 6.5h      |
| 4   | 3.5h     | 12      | 10h       |
| 5   | 3h       | 15      | 13h       |
| **Σ** | **13h** | **60**  | **13h**   |

---

## 🚨 If Something Goes Wrong

| Problem | Solution |
|---------|----------|
| Script fails with error | Check that `.venv` is activated & params are correct |
| GPU out of memory | Reduce batch size in `src/experiments.py` or fewer seeds |
| Results much worse | Verify `--append` flag; check params from previous exp |
| Config CV stays > 5.0 | Skip to Exp 3 (reward calib) not Exp 1 (entropy) |
| Test alpha still negative | May be data/benchmark issue; escalate |

---

## 📞 Document Reference

| Question | See Document |
|----------|---|
| "What's the overall strategy?" | `EXPERIMENT_STRATEGY_HANDOFF.md` |
| "How do I run Exp 1?" | `EXPERIMENT_EXECUTION_README.md` → STEP 2 |
| "What are success criteria?" | This file + `EXPERIMENT_EXECUTION_README.md` |
| "What do I do after all experiments?" | `EXPERIMENT_EXECUTION_README.md` → Post-Experiment Analysis |
| "Is my result promotable?" | Promotion Re-Evaluation (below) |

---

## 📊 Best Config Template

After all experiments, fill this in:

```
BEST FOUND CONFIGURATION (Exp 1-5 Results)

Experiment 1 Results:
  Best Treatment: [Treatment A/B/C]
  entropy_schedule: [fixed/decay]
  ent_coef: [X.XX]
  test_cv: [X.XX]

Experiment 3 Results:
  Best Treatment: [A/B/C/D]
  reward_clip: [X.X]
  reward_drawdown_penalty_scale: [X.XX]
  reward_turnover_penalty_scale: [X.XX]
  test_cv: [X.XX]
  test_alpha: [X.XXX]

Experiment 4 Results:
  Best timesteps: [XXXXX]
  test_accuracy: [X.XXX]
  test_cv: [X.XX]

Experiment 5 Results:
  Winning mode: [sharpe/sortino]
  Sharpe accuracy: [X.XXX]
  Sortino accuracy: [X.XXX]

FINAL CONFIG FOR DEPLOYMENT:
  reward_mode: [sharpe/sortino]
  ent_coef: [X.XX]
  entropy_schedule: [fixed/decay]
  timesteps: [XXXXX]
  reward_clip: [X.X]
  reward_drawdown_penalty_scale: [X.XX]
  reward_turnover_penalty_scale: [X.XX]
  transaction_cost_rate: 0.001
  [other params unchanged]

PROMOTION READINESS:
  Gate 1 (test_acc >= 0.53): [ ] PASS [ ] FAIL [Value: X.XXX]
  Gate 2 (test_wr >= 0.52): [ ] PASS [ ] FAIL [Value: X.XXX]
  Gate 3 (test_alpha >= 0.00): [ ] PASS [ ] FAIL [Value: X.XXX]
  Gate 4 (|val-test| <= 0.05): [ ] PASS [ ] FAIL [Value: X.XXX]
  Gate 5 (test_cv < 1.0): [ ] PASS [ ] FAIL [Value: X.XXX]

Overall: [ ] READY [ ] NOT READY [ ] CONDITIONAL

Notes: ____________________________
```

---

**Print this page. Reference it while running experiments.**  
**Last updated**: 2026-04-10 08:24 UTC

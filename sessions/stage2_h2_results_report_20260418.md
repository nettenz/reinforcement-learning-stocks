# Stage 2 H2 Results Report

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Hypothesis: H2 - Longer-Horizon Targets  
Run ID: h2-target-sweep-20260418  
Status: fail

---

## 1. Run Metadata

- **Dataset version**: tech_training_data_stationary.csv
- **Feature set version**: stationary_features_v1
- **Target variant**: sweep across 1d_forward_return, 3d_forward_return, 5d_forward_return, directional_threshold
- **Model family**: linear/logistic, tree-based, naive_momentum
- **Rolling-window scheme**: train 20%, validation 20%, test 20%, slide 33%
- **Cost assumptions**: transaction_cost=0.0005, slippage=0.0002, turnover_rule=position_change
- **Recent window included**: yes

---

## 2. Thesis Being Tested

> Longer-horizon targets may reduce noise sensitivity and improve stability versus short-horizon targets.

This was tested as a first-pass H2 sweep without changing the feature set.

---

## 3. Benchmarks

This sweep was compared against:

- buy-hold
- naive momentum
- flat/no-trade baseline

---

## 4. Window-Level Metrics

This was a multi-variant sweep, so the most useful view is the aggregate result for each target variant.

| Target Variant | Best Model Family | Mean Net Return | Mean Net Benchmark Gap | Mean Net Sharpe | Stability CV | Recent Window Gap | Primary Predictive Metric | Verdict |
| ---------------- | ------------------ | ----------------- | ------------------------ | ----------------- | -------------- | ------------------ | --------------------------- | --------- |
| 1d_forward_return | tree | +0.2713 | -0.4016 | +0.4510 | 0.424 | -0.9897 | -0.2589 R2 | KILL |
| 3d_forward_return | linear | +0.3074 | -0.4188 | +0.4473 | 0.917 | -1.2063 | -0.0373 R2 | KILL |
| 5d_forward_return | linear | +0.1257 | -0.6084 | +0.2800 | 1.464 | -1.0463 | -0.0540 R2 | KILL |
| directional_threshold | linear | +0.6948 | -0.0314 | +0.7580 | 0.514 | -0.0895 | 0.5506 accuracy | KILL |

---

## 5. Aggregate Metrics

- **Mean gross return**: positive in all variants, but this did not survive benchmark comparison.
- **Mean net return**: positive in all variants, but still below buy-hold in every sweep variant.
- **Mean net benchmark gap**: negative for all variants.
- **Mean net Sharpe**: positive for all variants, but benchmark Sharpe remained higher or comparable in key windows.
- **Mean benchmark Sharpe gap**: negative for all variants.
- **Primary predictive metric (mean)**: mixed; regression variants remained below zero R2, directional accuracy was the strongest but still not enough.
- **Stability CV**: acceptable for 1d and directional_threshold, but 5d was unstable.
- **2/3 benchmark pass achieved**: no
- **Recent window pass**: no

---

## 6. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: FAIL
- **G2 Economic Robustness**: FAIL
- **G3 Stability**: PASS for 1d and directional_threshold, FAIL for 5d
- **G4 Predictive Support**: PASS for directional_threshold, FAIL for the regression variants
- **G5 Cost Survivability**: FAIL

### H2-Specific Gates

- **H2-1 Positive mean net edge for at least one horizon**: FAIL
- **H2-2 2/3 windows beat buy-hold or momentum**: FAIL
- **H2-3 Recent window does not collapse**: FAIL

### Hard Stop Conditions Triggered

- [x] only one window positive
- [x] buy-hold cleanly dominates
- [x] net edge non-positive after costs
- [x] recent window fails severely
- [ ] leakage or benchmark inconsistency detected

---

## 7. Interpretation

### What worked

- The 3-day directional run briefly produced one window that beat buy-hold on net return and Sharpe.
- Directional classification produced the best predictive metric of the sweep.
- The 1-day and directional variants controlled turnover better than the 5-day run.

### What failed

- None of the target variants cleared the 2/3 benchmark rule.
- Regression targets remained negative in predictive quality and did not generalize to forward windows.
- The 5-day target was the weakest stability case and failed the recent-window test hard.
- The directional variant looked better statistically, but its benchmark gap remained negative and the recent window still failed.

### Is the edge real or likely artifact?

Likely artifact or at best a thin, regime-specific effect. The sweep showed isolated pockets of relative strength, but the signal did not survive the benchmark contract or the recent-window filter.

### Does this justify another H2 iteration?

No. The current H2 sweep does not justify more H2 tuning before moving to a different hypothesis family.

---

## 8. Final Verdict

**Verdict**: KILL

**Reason**:  
Across four H2 target variants, the best case was the directional_threshold run, but it still finished with a negative mean net benchmark gap (-0.0314), failed the recent-window gate, and did not produce 2/3 benchmark wins. The sweep therefore does not clear the H2 contract, even though some subwindows showed positive returns and one 3-day window beat buy-hold. The correct next move is to stop H2 and proceed to H1 rather than keep tuning horizon length.

**Next action**:

- kill H2 and move to H1

---

## 9. Notes

Ledger: [logs/stage2_h2_results_ledger.json](../logs/stage2_h2_results_ledger.json)

Generated reports:

- [results/stage2_h2/stage2_h2_1d_forward_return_report_20260418_164610.md](../results/stage2_h2/stage2_h2_1d_forward_return_report_20260418_164610.md)
- [results/stage2_h2/stage2_h2_3d_forward_return_report_20260418_164611.md](../results/stage2_h2/stage2_h2_3d_forward_return_report_20260418_164611.md)
- [results/stage2_h2/stage2_h2_5d_forward_return_report_20260418_164612.md](../results/stage2_h2/stage2_h2_5d_forward_return_report_20260418_164612.md)
- [results/stage2_h2/stage2_h2_directional_threshold_report_20260418_164613.md](../results/stage2_h2/stage2_h2_directional_threshold_report_20260418_164613.md)

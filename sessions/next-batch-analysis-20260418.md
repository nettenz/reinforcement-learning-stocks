# Quant Professional Interpretation: Automated Analysis
**Generated:** 2026-04-18 09:01 UTC  
**Runs Analyzed:** 136  
**Unique Seeds:** 21  
**Algorithm:** SAC (Continuous Action Space)

---

## Executive Summary
- **Signal Verdict:** **BEARISH** — Strategy is not yet investable. Fundamental changes required.
- **Val Return (mean):** 0.7917
- **Test Return (mean):** 0.0472
- **Val→Test Gap:** 0.7445
- **Val Sharpe (mean):** 0.48
- **Test Sharpe (mean):** 0.14

---

## Top Run (by Ranking Score)

| Metric | Value |
|---|---|
| Seed | 7 |
| Timesteps | 20000 |
| Learning Rate | 0.0003 |
| Reward Mode | sortino |
| Rolling Window | 100 |
| Ranking Score | 0.6853 |
| Val Accuracy | 0.6604 |
| Test Accuracy | 0.0000 |
| Val Win Rate | 0.6316 |
| Test Win Rate | 0.0000 |
| Val Sharpe | 2.2490 |
| Test Sharpe | 0.0000 |
| Val Sortino | 2.9086 |
| Test Sortino | 0.0000 |
| Val Max DD | -0.0108 |
| Test Max DD | 0.0000 |
| Val Alpha vs QQQ | -0.3110 |
| Test Alpha vs QQQ | -0.1280 |

---

## Generalization Analysis (Val → Test)
- **Return Gap (mean):** 0.7445 ± 0.9453
- **Accuracy Gap (mean):** 0.0332
- **Sharpe Gap (mean):** 0.34
- ⚠️ **WARNING:** Significant overfitting detected. Val massively outperforms test.

---

## Trading Activity & Behaviors
- **Val Win Rate (mean):** 0.4587
- **Test Win Rate (mean):** 0.4250
- **Low Activity Runs:** 52.2%
- ⚠️ **WARNING:** Agent shows high levels of inactivity. Correlate with `ent_coef` in Sweep Analysis.

---

## Parameter Sweep Analysis
Analysis of how varying hyperparameters impacted performance (averaged across seeds).
### Impact of: `timesteps`
|   timesteps |   val_sharpe_ratio |   test_sharpe_ratio |   val_alpha_vs_qqq |   test_alpha_vs_qqq |   val_reward_action_bonus_mean |
|------------:|-------------------:|--------------------:|-------------------:|--------------------:|-------------------------------:|
|       20000 |           0.483396 |            0.138669 |          -0.274084 |           -0.145187 |                     0.00143077 |
|       40000 |           0.446254 |            0.127368 |          -0.314932 |           -0.134277 |                     0.00108839 |

---

## Seed Stability
- **Seeds Tested:** 21
- **Stability Rating:** LOW
- **Val Return CV:** 1.39
- **Test Return CV:** 5.84

---

## Reward Mode Comparison
| reward_mode   |   ('val_sharpe_ratio', 'mean') |   ('val_sharpe_ratio', 'std') |   ('test_sharpe_ratio', 'mean') |   ('test_sharpe_ratio', 'std') |   ('val_sortino_ratio', 'mean') |   ('val_sortino_ratio', 'std') |   ('test_sortino_ratio', 'mean') |   ('test_sortino_ratio', 'std') |   ('val_alpha_vs_qqq', 'mean') |   ('val_alpha_vs_qqq', 'std') |   ('test_alpha_vs_qqq', 'mean') |   ('test_alpha_vs_qqq', 'std') |   ('val_cumulative_signal_return', 'mean') |   ('val_cumulative_signal_return', 'std') |   ('test_cumulative_signal_return', 'mean') |   ('test_cumulative_signal_return', 'std') |   ('val_max_drawdown', 'mean') |   ('val_max_drawdown', 'std') |   ('test_max_drawdown', 'mean') |   ('test_max_drawdown', 'std') |   ('val_actionable_accuracy', 'mean') |   ('val_actionable_accuracy', 'std') |   ('test_actionable_accuracy', 'mean') |   ('test_actionable_accuracy', 'std') |   ('val_trade_win_rate', 'mean') |   ('val_trade_win_rate', 'std') |   ('test_trade_win_rate', 'mean') |   ('test_trade_win_rate', 'std') |   ('ranking_score', 'mean') |   ('ranking_score', 'std') |
|:--------------|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|--------------------------------:|-------------------------------:|---------------------------------:|--------------------------------:|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|-------------------------------------------:|------------------------------------------:|--------------------------------------------:|-------------------------------------------:|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|--------------------------------------:|-------------------------------------:|---------------------------------------:|--------------------------------------:|---------------------------------:|--------------------------------:|----------------------------------:|---------------------------------:|----------------------------:|---------------------------:|
| sortino       |                       0.480665 |                       1.61943 |                        0.137838 |                       0.540883 |                        0.821653 |                        2.30485 |                          0.14317 |                        0.698396 |                      -0.277088 |                      0.428289 |                       -0.144385 |                       0.188977 |                                    0.79169 |                                   1.09848 |                                   0.0472223 |                                   0.275907 |                      -0.191459 |                      0.205409 |                       -0.183575 |                       0.186169 |                               0.46604 |                             0.184092 |                               0.432881 |                              0.200858 |                         0.458728 |                        0.178193 |                          0.425049 |                         0.194727 |                    0.445876 |                   0.245716 |

---

## Benchmark Comparison (vs QQQ)
- **Val Alpha (mean):** -0.2771
- **Test Alpha (mean):** -0.1444
- **% Runs Beating QQQ (test):** 11%

---

## Recommended Next Steps

1. **CRITICAL — Action Collapse:** The agent is inactive in >50% of runs. Increase `ent_coef` (entropy) or `reward_action_bonus_scale`.
2. **Overfitting Detected:** Val→Test return gap is 74.4%. Reduce timesteps or increase entropy (`ent_coef`) for better regularization.
3. **Seed Instability:** Cross-seed variance is high (CV=1.39). Increase `ent_coef` to encourage broader exploration during training.
4. **Alpha Deficit:** Strategy underperforms QQQ benchmark. Consider switching to `sharpe` or `sortino` reward modes to prioritize risk-adjusted growth.


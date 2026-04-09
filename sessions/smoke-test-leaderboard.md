# Quant Professional Interpretation: Automated Analysis
**Generated:** 2026-04-06 06:34 UTC  
**Runs Analyzed:** 140  
**Unique Seeds:** 10  
**Algorithm:** SAC (Continuous Action Space)

---

## Executive Summary
- **Signal Verdict:** **NEUTRAL** — Mixed results. Hyperparameter tuning or architecture changes recommended.
- **Val Return (mean):** 1.1677
- **Test Return (mean):** 0.0185
- **Val→Test Gap:** 1.1492
- **Val Sharpe (mean):** 0.81
- **Test Sharpe (mean):** 0.07

---

## Top Run (by Ranking Score)

| Metric | Value |
|---|---|
| Seed | 42 |
| Timesteps | 20000 |
| Learning Rate | 0.0003 |
| Reward Mode | sharpe |
| Rolling Window | 100 |
| Ranking Score | 0.6597 |
| Val Accuracy | 0.5813 |
| Test Accuracy | 0.5387 |
| Val Win Rate | 0.5635 |
| Test Win Rate | 0.5196 |
| Val Sharpe | 1.6906 |
| Test Sharpe | -0.1668 |
| Val Sortino | 2.3133 |
| Test Sortino | -0.1755 |
| Val Max DD | -0.1110 |
| Test Max DD | -0.1448 |
| Val Alpha vs QQQ | 0.0178 |
| Test Alpha vs QQQ | -0.1780 |

---

## Generalization Analysis (Val → Test)
- **Return Gap (mean):** 1.1492 ± 0.9203
- **Accuracy Gap (mean):** 0.0173
- **Sharpe Gap (mean):** 0.74
- ⚠️ **WARNING:** Significant overfitting detected. Val massively outperforms test.

---

## Trading Activity & Behaviors
- **Val Win Rate (mean):** 0.5198
- **Test Win Rate (mean):** 0.5015
- **Low Activity Runs:** 7.9%

---

## Parameter Sweep Analysis
Analysis of how varying hyperparameters impacted performance (averaged across seeds).
### Impact of: `ent_coef`
|   ent_coef |   val_sharpe_ratio |   test_sharpe_ratio |   val_alpha_vs_qqq |   test_alpha_vs_qqq |   val_reward_action_bonus_mean |
|-----------:|-------------------:|--------------------:|-------------------:|--------------------:|-------------------------------:|
|       0.02 |           0.081572 |           0.0104386 |        -0.228668   |            -0.15536 |                     0.00585806 |
|       0.05 |           1.21855  |           0.108885  |         0.00283411 |            -0.11973 |                     0.00878853 |

### Impact of: `timesteps`
|   timesteps |   val_sharpe_ratio |   test_sharpe_ratio |   val_alpha_vs_qqq |   test_alpha_vs_qqq |   val_reward_action_bonus_mean |
|------------:|-------------------:|--------------------:|-------------------:|--------------------:|-------------------------------:|
|       20000 |           0.875181 |            0.052611 |         -0.0468749 |           -0.136858 |                     0.00867859 |
|       40000 |           0.582599 |            0.151145 |         -0.200737  |           -0.116313 |                     0.00430753 |

---

## Seed Stability
- **Seeds Tested:** 10
- **Stability Rating:** LOW
- **Val Return CV:** 0.96
- **Test Return CV:** 13.09

---

## Reward Mode Comparison
| reward_mode   |   ('val_sharpe_ratio', 'mean') |   ('val_sharpe_ratio', 'std') |   ('test_sharpe_ratio', 'mean') |   ('test_sharpe_ratio', 'std') |   ('val_sortino_ratio', 'mean') |   ('val_sortino_ratio', 'std') |   ('test_sortino_ratio', 'mean') |   ('test_sortino_ratio', 'std') |   ('val_alpha_vs_qqq', 'mean') |   ('val_alpha_vs_qqq', 'std') |   ('test_alpha_vs_qqq', 'mean') |   ('test_alpha_vs_qqq', 'std') |   ('val_cumulative_signal_return', 'mean') |   ('val_cumulative_signal_return', 'std') |   ('test_cumulative_signal_return', 'mean') |   ('test_cumulative_signal_return', 'std') |   ('val_max_drawdown', 'mean') |   ('val_max_drawdown', 'std') |   ('test_max_drawdown', 'mean') |   ('test_max_drawdown', 'std') |   ('val_actionable_accuracy', 'mean') |   ('val_actionable_accuracy', 'std') |   ('test_actionable_accuracy', 'mean') |   ('test_actionable_accuracy', 'std') |   ('val_trade_win_rate', 'mean') |   ('val_trade_win_rate', 'std') |   ('test_trade_win_rate', 'mean') |   ('test_trade_win_rate', 'std') |   ('ranking_score', 'mean') |   ('ranking_score', 'std') |
|:--------------|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|--------------------------------:|-------------------------------:|---------------------------------:|--------------------------------:|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|-------------------------------------------:|------------------------------------------:|--------------------------------------------:|-------------------------------------------:|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|--------------------------------------:|-------------------------------------:|---------------------------------------:|--------------------------------------:|---------------------------------:|--------------------------------:|----------------------------------:|---------------------------------:|----------------------------:|---------------------------:|
| sharpe        |                       0.812485 |                         1.503 |                       0.0737255 |                       0.478847 |                         1.30229 |                        2.23928 |                          0.11532 |                            0.58 |                     -0.0798453 |                      0.522844 |                       -0.132455 |                       0.128436 |                                    1.16768 |                                   1.12086 |                                   0.0185258 |                                   0.242466 |                      -0.204177 |                      0.191976 |                       -0.194713 |                       0.136917 |                              0.529151 |                            0.0914651 |                               0.511824 |                             0.0868992 |                         0.519827 |                       0.0824742 |                          0.501463 |                        0.0796062 |                    0.529932 |                     0.2012 |

---

## Benchmark Comparison (vs QQQ)
- **Val Alpha (mean):** -0.0798
- **Test Alpha (mean):** -0.1325
- **% Runs Beating QQQ (test):** 13%

---

## Recommended Next Steps

1. **Overfitting Detected:** Val→Test return gap is 114.9%. Reduce timesteps or increase entropy (`ent_coef`) for better regularization.
2. **Seed Instability:** Cross-seed variance is high (CV=0.96). Increase `ent_coef` to encourage broader exploration during training.
3. **Alpha Deficit:** Strategy underperforms QQQ benchmark. Consider switching to `sharpe` or `sortino` reward modes to prioritize risk-adjusted growth.


---

## Strategic AI Analyst Interpretation

The primary concern is the significant overfitting, as evidenced by the large gap between validation and test performance. While the mean validation return is positive, the test return is near zero, and the test Sharpe ratio is abysmal. The parameter sweep suggests increasing the entropy coefficient (`ent_coef`) might improve generalization, potentially by encouraging broader exploration and preventing the agent from latching onto spurious patterns in the validation set. We should prioritize reducing the number of training timesteps, and rigorously evaluate the effects of increased entropy. Finally, the models are consistently underperforming the QQQ benchmark based on test alpha; the "sharpe" reward mode produced better test results, but given the high variance between seeds, further investigation is warranted.

The most dangerous hidden risk is the low seed stability. A high coefficient of variation (CV) in both validation and test returns indicates that the strategy's performance is highly dependent on the random initialization of the training process. This suggests that the strategy may be exploiting specific quirks in the training data that are not representative of the broader market. This instability, combined with the already present overfitting, will make live-trading with this system very dangerous.

Based on the reported data, I would assign a confidence score of **15%** for this strategy becoming benchmark-beating. The severe overfitting and instability issues require substantial architectural or hyperparameter tuning changes before it can be considered viable.

# Quant Professional Interpretation: Automated Analysis
**Generated:** 2026-04-13 21:09 UTC  
**Runs Analyzed:** 101  
**Unique Seeds:** 11  
**Algorithm:** SAC (Continuous Action Space)

---

## Executive Summary
- **Signal Verdict:** **BEARISH** — Strategy is not yet investable. Fundamental changes required.
- **Val Return (mean):** 0.9416
- **Test Return (mean):** 0.0420
- **Val→Test Gap:** 0.8996
- **Val Sharpe (mean):** 0.55
- **Test Sharpe (mean):** 0.17

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
- **Return Gap (mean):** 0.8996 ± 0.9579
- **Accuracy Gap (mean):** 0.0328
- **Sharpe Gap (mean):** 0.38
- ⚠️ **WARNING:** Significant overfitting detected. Val massively outperforms test.

---

## Trading Activity & Behaviors
- **Val Win Rate (mean):** 0.4594
- **Test Win Rate (mean):** 0.4257
- **Low Activity Runs:** 51.5%
- ⚠️ **WARNING:** Agent shows high levels of inactivity. Correlate with `ent_coef` in Sweep Analysis.

---

## Parameter Sweep Analysis
Analysis of how varying hyperparameters impacted performance (averaged across seeds).
### Impact of: `timesteps`
|   timesteps |   val_sharpe_ratio |   test_sharpe_ratio |   val_alpha_vs_qqq |   test_alpha_vs_qqq |   val_reward_action_bonus_mean |
|------------:|-------------------:|--------------------:|-------------------:|--------------------:|-------------------------------:|
|       20000 |           0.556726 |            0.172565 |          -0.229383 |           -0.149438 |                     0.00140117 |
|       40000 |           0.446254 |            0.127368 |          -0.314932 |           -0.134277 |                     0.00108839 |

---

## Seed Stability
- **Seeds Tested:** 11
- **Stability Rating:** LOW
- **Val Return CV:** 1.22
- **Test Return CV:** 5.67

---

## Reward Mode Comparison
| reward_mode   |   ('val_sharpe_ratio', 'mean') |   ('val_sharpe_ratio', 'std') |   ('test_sharpe_ratio', 'mean') |   ('test_sharpe_ratio', 'std') |   ('val_sortino_ratio', 'mean') |   ('val_sortino_ratio', 'std') |   ('test_sortino_ratio', 'mean') |   ('test_sortino_ratio', 'std') |   ('val_alpha_vs_qqq', 'mean') |   ('val_alpha_vs_qqq', 'std') |   ('test_alpha_vs_qqq', 'mean') |   ('test_alpha_vs_qqq', 'std') |   ('val_cumulative_signal_return', 'mean') |   ('val_cumulative_signal_return', 'std') |   ('test_cumulative_signal_return', 'mean') |   ('test_cumulative_signal_return', 'std') |   ('val_max_drawdown', 'mean') |   ('val_max_drawdown', 'std') |   ('test_max_drawdown', 'mean') |   ('test_max_drawdown', 'std') |   ('val_actionable_accuracy', 'mean') |   ('val_actionable_accuracy', 'std') |   ('test_actionable_accuracy', 'mean') |   ('test_actionable_accuracy', 'std') |   ('val_trade_win_rate', 'mean') |   ('val_trade_win_rate', 'std') |   ('test_trade_win_rate', 'mean') |   ('test_trade_win_rate', 'std') |   ('ranking_score', 'mean') |   ('ranking_score', 'std') |
|:--------------|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|--------------------------------:|-------------------------------:|---------------------------------:|--------------------------------:|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|-------------------------------------------:|------------------------------------------:|--------------------------------------------:|-------------------------------------------:|-------------------------------:|------------------------------:|--------------------------------:|-------------------------------:|--------------------------------------:|-------------------------------------:|---------------------------------------:|--------------------------------------:|---------------------------------:|--------------------------------:|----------------------------------:|---------------------------------:|----------------------------:|---------------------------:|
| sortino       |                       0.545788 |                       1.72721 |                         0.16809 |                       0.491937 |                        0.945893 |                        2.46442 |                         0.143691 |                         0.61776 |                      -0.237853 |                      0.454162 |                       -0.147936 |                       0.147745 |                                   0.941643 |                                   1.14867 |                                   0.0420426 |                                   0.238501 |                      -0.187329 |                      0.205311 |                       -0.173949 |                       0.174119 |                              0.467168 |                             0.187605 |                               0.434348 |                              0.201775 |                         0.459429 |                         0.18074 |                          0.425707 |                         0.194896 |                    0.458881 |                   0.258869 |

---

## Benchmark Comparison (vs QQQ)
- **Val Alpha (mean):** -0.2379
- **Test Alpha (mean):** -0.1479
- **% Runs Beating QQQ (test):** 10%

---

## Recommended Next Steps

1. **CRITICAL — Action Collapse:** The agent is inactive in >50% of runs. Increase `ent_coef` (entropy) or `reward_action_bonus_scale`.
2. **Overfitting Detected:** Val→Test return gap is 90.0%. Reduce timesteps or increase entropy (`ent_coef`) for better regularization.
3. **Seed Instability:** Cross-seed variance is high (CV=1.22). Increase `ent_coef` to encourage broader exploration during training.
4. **Alpha Deficit:** Strategy underperforms QQQ benchmark. Consider switching to `sharpe` or `sortino` reward modes to prioritize risk-adjusted growth.


---

## Strategic AI Analyst Interpretation

The report paints a concerning picture of the current SAC trading strategy. The massive discrepancy between validation and test results strongly suggests severe overfitting, rendering the strategy unusable in live trading. This is further compounded by the high percentage of "Low Activity Runs," indicating the agent is failing to actively learn and adapt to the market dynamics. The negative alpha compared to QQQ and high cross-seed variance further erode confidence.

The immediate strategic pivot should focus on addressing the overfitting and inactivity issues. Specifically, we must significantly increase the entropy coefficient (`ent_coef`) to encourage exploration and prevent the agent from prematurely converging to a suboptimal policy. Simultaneously, reducing the number of timesteps could also aid in curbing overfitting. A systematic hyperparameter optimization, focusing on the interplay between `ent_coef`, `timesteps`, and potentially the `reward_action_bonus_scale`, is crucial. Finally, while the reward mode choice might influence profitability, the core problems of overfitting and inactivity need resolution before optimizing for different risk-adjusted returns.

The most dangerous hidden risk is the illusion of success during validation. The strategy appears to perform well in the validation environment but utterly fails to generalize to unseen data. This creates a false sense of accomplishment and potentially leads to premature deployment with disastrous consequences. The fact that the test accuracy and win rate are 0.00 in the top run is a huge red flag. Given these critical issues, I assign a confidence score of only **5%** to this strategy becoming benchmark-beating in its current form. Substantial improvements are needed before any further consideration.

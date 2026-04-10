# Gemini Quant Analysis Report
**Date:** 2026-04-09  
**Focus:** Directional vs. Downside Ablation and Generalization Analysis  
**Tickers:** NVDA (Tech Basket)  
**Algorithm:** SAC (Continuous Action Space)  

---

## 1. Research Summary
The most recent experiments focused on two key axes for improving model generalization under realistic execution constraints (`next_bar` mode): **Directional Strength Ablation** and **Downside Control Ablation**. These runs aimed to mitigate the significant overfitting observed in previous cycles, where validation performance was high but test performance remained near zero or negative.

## 2. What Improved
*   **Generalization with Drawdown Penalties:** The introduction of `reward_drawdown_penalty_scale` (0.10 and 0.15) significantly improved test-set metrics across all cohorts. 
    *   **Test Actionable Accuracy:** Improved from ~0.49 (baseline) to **0.525**.
    *   **Test Cumulative Signal Return:** Moved from negative (-0.14) to positive (**+0.07**).
*   **Execution Realism:** All recent runs successfully transitioned to `next_bar` execution, eliminating the "same-bar fill" lookahead bias identified in the April 2nd Environment Realism Audit.

## 3. What Degraded or Remains Weak
*   **Directional Over-Optimization:** Increasing the `reward_direction_scale` from 0.35 to 0.40 was **counterproductive**. Test accuracy dropped from ~0.49 to ~0.40, suggesting that higher directional rewards force the agent to over-fit to noise rather than capturing robust trends.
*   **Val-Test Gap:** While absolute test performance improved, the gap remains large. Validation Sharpes are consistently >1.0, while Test Sharpes hover near 0.1–0.4, indicating persistent overfitting to the training/validation regime.
*   **News Feature Absence:** No runs in the latest standardized batch utilized the news sentiment features (`include_news=1`), likely due to the audit's finding that the current sentiment data is 98.5% binary noise.

## 4. Most Likely Explanations
*   **Reward Hacking on Volatility:** Without a drawdown penalty, the agent appears to chase high-variance signals that look good in validation but fail in the test set.
*   **Action Collapse/Inertia:** The high `reward_hold_penalty` (0.1) combined with low entropy may be causing the agent to stay in positions too long, missing regime shifts in the test period.

## 5. Confidence Level for Current Conclusions
*   **High:** The benefit of drawdown penalties is consistent across multiple seeds and metrics.
*   **High:** The failure of increased directional scale is clear and suggests a ceiling for this specific reward component.

## 6. Recommended Next Experiment Batch
1.  **Downside + Entropy Sweep:** Combine the best `dd015` config with a slightly higher `ent_coef` (e.g., 0.07 vs 0.05) to see if increased exploration prevents the "stuck" behavior during test-set regime shifts.
2.  **Turnover Normalization:** Test a higher `reward_turnover_penalty_scale` (currently 0.05) to see if more aggressive trade reduction further bridges the Val/Test gap.
3.  **Stationary vs. Non-Stationary Baseline:** Re-verify performance using `use_stationary_features=1` for all tech tickers to ensure the current gains aren't dependent on non-stationary price levels.

## 7. Priority Order
1.  **Entropy Calibration** (High impact on generalization).
2.  **Turnover Control** (Reduces costs and noise sensitivity).
3.  **Stationary Feature Verification**.

## 8. Success/Failure Interpretation Plan
*   **Success:** Mean Test Sharpe increases to >0.5 across 5+ seeds while maintaining Test Win Rate >52%.
*   **Failure:** Test returns revert to negative or seed variance increases significantly.

## 9. Leaderboard Comparability Impact
**MODERATE.** The shift to `next_bar` mode is a breaking change for historical comparisons. All future evaluations MUST be compared against the April 6th `next_bar` baselines, not the older `same_bar` runs which are now considered "unrealistic" due to lookahead bias.

## 10. Promotion Readiness Assessment
**NOT PROMOTABLE.** While the `downside-ab` runs show the first signs of positive test-set alpha in a realistic environment, the high volatility and relatively low Sharpe in the test set do not yet meet the criteria for a production-ready trading policy. Further stabilization of the Val-Test gap is required.

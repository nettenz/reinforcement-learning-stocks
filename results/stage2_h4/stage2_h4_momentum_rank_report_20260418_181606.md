# Stage 2 H4 Results Report

Date: 2026-04-18
Hypothesis: H4 - Concentration-Capped Cross-Sectional Ranking
Run ID: momentum_rank
Status: kill

## 1. Run Metadata
- Universe: AAPL, AMD, NVDA, QQQ, SPY
- Model family: momentum_rank
- Rebalance frequency: monthly
- Selection rule: top-2 capped at 0.50
- Cost assumptions: transaction_cost=0.0005, slippage=0.0002, turnover_rule=weight_change

## 2. Thesis Being Tested
> Relative ranking with concentration caps may improve robustness and reduce single-ticker risk compared to pure top-k selection.

## 3. Universe Sufficiency Check
| Window | Period | Asset Count Available | Rebalance Observations | Sufficiency Verdict |
| ------ | ------ | --------------------- | ---------------------- | ------------------- |
| 0 | 2019-11-29 to 2022-10-31 | 5 | 36 | pass |
| 1 | 2021-06-30 to 2024-05-31 | 5 | 36 | pass |
| 2 | 2023-01-31 to 2025-12-31 | 5 | 36 | pass |

### Auto-Kill Check
- [ ] insufficient universe size
- [ ] equal-weight or buy-hold dominates
- [x] recent window fails severely

## 4. Benchmarks
- equal-weight portfolio
- buy-hold
- momentum ranking baseline

## 5. Window-Level Metrics
| Window | Period | Gross Return | Net Return | Equal-Weight Return | Buy-Hold Return | Momentum Rank Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Rank Metric | Dominant Ticker | Verdict |
| ------ | ------ | ------------ | ---------- | ------------------- | --------------- | -------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------- | --------------- | ------- |
| 0 | 2019-11-29 to 2022-10-31 | +1.5141 | +1.5141 | +1.1594 | +1.0821 | +1.5141 | +0.3547 | +1.021 | +0.106 | -0.3834 | 0.600 | +0.1140 | AMD | pass |
| 1 | 2021-06-30 to 2024-05-31 | +1.8051 | +1.8051 | +1.1908 | +1.4617 | +1.8051 | +0.3434 | +1.094 | +0.089 | -0.4591 | 0.544 | +0.0058 | NVDA | pass |
| 2 | 2023-01-31 to 2025-12-31 | +2.2026 | +2.2026 | +2.6359 | +3.0598 | +2.2026 | -0.8572 | +1.300 | -0.604 | -0.2617 | 0.558 | -0.1374 | NVDA | fail |

## 6. Aggregate Metrics
- Mean gross return: +1.8406
- Mean net return: +1.8406
- Mean net benchmark gap: -0.0530
- Mean net Sharpe: +1.138
- Mean benchmark Sharpe gap: -0.136
- Primary ranking metric: -0.0058
- Stability CV: 0.153
- 2/3 benchmark pass achieved: yes
- Recent window pass: no
- Single-ticker dominance: no
- Largest ticker contribution share: 0.626

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: FAIL
- G3 Stability: PASS
- G4 Predictive Support: FAIL
- G5 Cost Survivability: FAIL

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.3466 | 0.091 | supporting |
| AMD | +1.2837 | 0.338 | supporting |
| NVDA | +1.8254 | 0.481 | supporting |
| QQQ | +0.0016 | 0.000 | supporting |
| SPY | +0.3353 | 0.088 | supporting |

## 9. Final Verdict
**Verdict**: KILL
**Reason**: mean net benchmark gap -0.0530, recent-window gap -0.8572, rank metric -0.0058, largest ticker share 0.626.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

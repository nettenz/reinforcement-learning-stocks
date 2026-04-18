# Stage 2 H3 Results Report

Date: 2026-04-18
Hypothesis: H3 - Cross-Sectional Ranking
Run ID: h3-linear_rank-20260418-173333
Status: kill

## 1. Run Metadata
- Universe: AAPL, AMD, NVDA, QQQ, SPY
- Model family: linear_rank
- Rebalance frequency: monthly
- Selection rule: top-2 equal weight
- Cost assumptions: transaction_cost=0.0005, slippage=0.0002, turnover_rule=weight_change

## 2. Thesis Being Tested
> Relative ranking may be more learnable than absolute direction and may reveal durable relative-strength structure.

## 3. Universe Sufficiency Check
| Window | Period | Asset Count Available | Rebalance Observations | Sufficiency Verdict |
| ------ | ------ | --------------------- | ---------------------- | ------------------- |
| 0 | 2019-11-29 to 2022-10-31 | 5 | 36 | pass |
| 1 | 2021-06-30 to 2024-05-31 | 5 | 36 | pass |
| 2 | 2023-01-31 to 2025-12-31 | 5 | 36 | pass |

### Auto-Kill Check
- [x] insufficient universe size
- [ ] equal-weight or buy-hold dominates
- [x] recent window fails severely

## 4. Benchmarks
- equal-weight portfolio
- buy-hold
- momentum ranking baseline

## 5. Window-Level Metrics
| Window | Period | Gross Return | Net Return | Equal-Weight Return | Buy-Hold Return | Momentum Rank Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Rank Metric | Dominant Ticker | Verdict |
| ------ | ------ | ------------ | ---------- | ------------------- | --------------- | -------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------- | --------------- | ------- |
| 0 | 2019-11-29 to 2022-10-31 | +1.5011 | +1.5011 | +1.1594 | +1.0821 | +1.5141 | +0.3417 | +0.949 | +0.033 | -0.4176 | 0.503 | -0.0088 | AMD | pass |
| 1 | 2021-06-30 to 2024-05-31 | +1.5290 | +1.5290 | +1.1908 | +1.4617 | +1.8051 | +0.0673 | +0.956 | -0.049 | -0.4799 | 0.475 | +0.1228 | NVDA | fail |
| 2 | 2023-01-31 to 2025-12-31 | +1.7746 | +1.7746 | +2.6359 | +3.0598 | +2.2026 | -1.2852 | +1.284 | -0.620 | -0.1695 | 0.461 | -0.0380 | NVDA | fail |

## 6. Aggregate Metrics
- Mean gross return: +1.6016
- Mean net return: +1.6016
- Mean net benchmark gap: -0.2921
- Mean net Sharpe: +1.063
- Mean benchmark Sharpe gap: -0.212
- Primary ranking metric: +0.0253
- Stability CV: 0.077
- 2/3 benchmark pass achieved: no
- Recent window pass: no
- Single-ticker dominance: yes
- Largest ticker contribution share: 0.854

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: FAIL
- G3 Stability: PASS
- G4 Predictive Support: FAIL
- G5 Cost Survivability: FAIL

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.1543 | 0.043 | supporting |
| AMD | +0.7538 | 0.210 | supporting |
| NVDA | +2.3304 | 0.649 | supporting |
| QQQ | +0.1108 | 0.031 | supporting |
| SPY | +0.2417 | 0.067 | supporting |

## 9. Final Verdict
**Verdict**: KILL
**Reason**: mean net benchmark gap -0.2921, recent-window gap -1.2852, rank metric +0.0253, largest ticker share 0.854.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

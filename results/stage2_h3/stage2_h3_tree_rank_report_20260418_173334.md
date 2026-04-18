# Stage 2 H3 Results Report

Date: 2026-04-18
Hypothesis: H3 - Cross-Sectional Ranking
Run ID: h3-tree_rank-20260418-173334
Status: kill

## 1. Run Metadata
- Universe: AAPL, AMD, NVDA, QQQ, SPY
- Model family: tree_rank
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
| 0 | 2019-11-29 to 2022-10-31 | +0.8075 | +0.8075 | +1.1594 | +1.0821 | +1.5141 | -0.3519 | +0.692 | -0.224 | -0.5273 | 0.544 | -0.0994 | AMD | fail |
| 1 | 2021-06-30 to 2024-05-31 | +1.4964 | +1.4964 | +1.1908 | +1.4617 | +1.8051 | +0.0347 | +0.880 | -0.125 | -0.5583 | 0.419 | +0.0673 | NVDA | fail |
| 2 | 2023-01-31 to 2025-12-31 | +2.4523 | +2.4523 | +2.6359 | +3.0598 | +2.2026 | -0.6075 | +1.445 | -0.459 | -0.2201 | 0.531 | +0.0292 | NVDA | fail |

## 6. Aggregate Metrics
- Mean gross return: +1.5854
- Mean net return: +1.5854
- Mean net benchmark gap: -0.3082
- Mean net Sharpe: +1.006
- Mean benchmark Sharpe gap: -0.269
- Primary ranking metric: -0.0010
- Stability CV: 0.425
- 2/3 benchmark pass achieved: no
- Recent window pass: no
- Single-ticker dominance: yes
- Largest ticker contribution share: 0.734

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: FAIL
- G3 Stability: PASS
- G4 Predictive Support: FAIL
- G5 Cost Survivability: FAIL

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.2830 | 0.079 | supporting |
| AMD | +1.4476 | 0.405 | supporting |
| NVDA | +1.5806 | 0.442 | supporting |
| QQQ | +0.0488 | 0.014 | supporting |
| SPY | +0.2158 | 0.060 | supporting |

## 9. Final Verdict
**Verdict**: KILL
**Reason**: mean net benchmark gap -0.3082, recent-window gap -0.6075, rank metric -0.0010, largest ticker share 0.734.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

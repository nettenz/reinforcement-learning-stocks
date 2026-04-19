# Stage 2 H4 Results Report

Date: 2026-04-18
Hypothesis: H4 - Concentration-Capped Cross-Sectional Ranking
Run ID: linear_rank
Status: fail

## 1. Run Metadata
- Universe: AAPL, AMD, NVDA, QQQ, SPY
- Model family: linear_rank
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
- [ ] recent window fails severely

## 4. Benchmarks
- equal-weight portfolio
- buy-hold
- momentum ranking baseline

## 5. Window-Level Metrics
| Window | Period | Gross Return | Net Return | Equal-Weight Return | Buy-Hold Return | Momentum Rank Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Rank Metric | Dominant Ticker | Verdict |
| ------ | ------ | ------------ | ---------- | ------------------- | --------------- | -------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------- | --------------- | ------- |
| 0 | 2019-11-29 to 2022-10-31 | +3.7994 | +3.7994 | +1.1594 | +1.0821 | +1.5141 | +2.6400 | +1.487 | +0.571 | -0.3188 | 0.475 | +0.2778 | NVDA | pass |
| 1 | 2021-06-30 to 2024-05-31 | +5.7314 | +5.7314 | +1.1908 | +1.4617 | +1.8051 | +4.2697 | +1.566 | +0.562 | -0.4015 | 0.322 | +0.2719 | NVDA | pass |
| 2 | 2023-01-31 to 2025-12-31 | +6.1544 | +6.1544 | +2.6359 | +3.0598 | +2.2026 | +3.0946 | +1.887 | -0.016 | -0.2370 | 0.419 | +0.1520 | NVDA | fail |

## 6. Aggregate Metrics
- Mean gross return: +5.2284
- Mean net return: +5.2284
- Mean net benchmark gap: +3.3348
- Mean net Sharpe: +1.647
- Mean benchmark Sharpe gap: +0.372
- Primary ranking metric: +0.2339
- Stability CV: 0.196
- 2/3 benchmark pass achieved: yes
- Recent window pass: no
- Single-ticker dominance: no
- Largest ticker contribution share: 0.598

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: PASS
- G3 Stability: PASS
- G4 Predictive Support: PASS
- G5 Cost Survivability: PASS

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.5554 | 0.084 | supporting |
| AMD | +2.2457 | 0.339 | supporting |
| NVDA | +3.8250 | 0.577 | supporting |
| QQQ | -0.1331 | 0.000 | supporting |
| SPY | -0.0519 | 0.000 | supporting |

## 9. Final Verdict
**Verdict**: FAIL
**Reason**: mean net benchmark gap +3.3348, recent-window gap +3.0946, rank metric +0.2339, largest ticker share 0.598.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

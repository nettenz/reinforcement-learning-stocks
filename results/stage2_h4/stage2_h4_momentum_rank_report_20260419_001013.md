# Stage 2 H4 Results Report

Date: 2026-04-19
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
| 0 | 2021-03-31 to 2022-10-31 | 5 | 20 | pass |
| 1 | 2022-10-31 to 2024-05-31 | 5 | 20 | pass |
| 2 | 2024-05-31 to 2025-12-31 | 5 | 20 | pass |

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
| 0 | 2021-03-31 to 2022-10-31 | +0.2105 | +0.2105 | +0.0518 | +0.0184 | +0.2105 | +0.1587 | +0.508 | +0.239 | -0.3834 | 0.580 | +0.1421 | NVDA | pass |
| 1 | 2022-10-31 to 2024-05-31 | +1.8724 | +1.8724 | +1.7967 | +2.4566 | +1.8724 | -0.5842 | +1.888 | -0.575 | -0.1385 | 0.555 | -0.1579 | NVDA | fail |
| 2 | 2024-05-31 to 2025-12-31 | +0.2013 | +0.2013 | +0.5804 | +0.5114 | +0.2013 | -0.3791 | +0.507 | -0.888 | -0.2617 | 0.580 | -0.1632 | AMD | fail |

## 6. Aggregate Metrics
- Mean gross return: +0.7614
- Mean net return: +0.7614
- Mean net benchmark gap: -0.2682
- Mean net Sharpe: +0.967
- Mean benchmark Sharpe gap: -0.408
- Primary ranking metric: -0.0596
- Stability CV: 1.032
- 2/3 benchmark pass achieved: no
- Recent window pass: no
- Single-ticker dominance: yes
- Largest ticker contribution share: 0.878

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: FAIL
- G3 Stability: FAIL
- G4 Predictive Support: PASS
- G5 Cost Survivability: FAIL

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.1523 | 0.081 | supporting |
| AMD | +0.7014 | 0.375 | supporting |
| NVDA | +1.0121 | 0.540 | supporting |
| QQQ | -0.0877 | 0.000 | supporting |
| SPY | +0.0069 | 0.004 | supporting |

## 9. Final Verdict
**Verdict**: KILL
**Reason**: mean net benchmark gap -0.2682, recent-window gap -0.3791, rank metric -0.0596, largest ticker share 0.878.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

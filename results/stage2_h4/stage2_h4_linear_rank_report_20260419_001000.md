# Stage 2 H4 Results Report

Date: 2026-04-19
Hypothesis: H4 - Concentration-Capped Cross-Sectional Ranking
Run ID: linear_rank
Status: kill

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
| 0 | 2021-03-31 to 2022-10-31 | 5 | 20 | pass |
| 1 | 2022-10-31 to 2024-05-31 | 5 | 20 | pass |
| 2 | 2024-05-31 to 2025-12-31 | 5 | 20 | pass |

### Auto-Kill Check
- [x] insufficient universe size
- [ ] equal-weight or buy-hold dominates
- [ ] recent window fails severely

## 4. Benchmarks
- equal-weight portfolio
- buy-hold
- momentum ranking baseline

## 5. Window-Level Metrics
| Window | Period | Gross Return | Net Return | Equal-Weight Return | Buy-Hold Return | Momentum Rank Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Rank Metric | Dominant Ticker | Verdict |
| ------ | ------ | ------------ | ---------- | ------------------- | --------------- | -------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------- | --------------- | ------- |
| 0 | 2021-03-31 to 2022-10-31 | -0.0166 | -0.0166 | +0.0518 | +0.0184 | +0.2105 | -0.0684 | +0.199 | -0.070 | -0.4576 | 0.380 | -0.0368 | AAPL | fail |
| 1 | 2022-10-31 to 2024-05-31 | +1.3270 | +1.3270 | +1.7967 | +2.4566 | +1.8724 | -1.1295 | +1.640 | -0.823 | -0.1312 | 0.555 | +0.0368 | AMD | fail |
| 2 | 2024-05-31 to 2025-12-31 | +0.9582 | +0.9582 | +0.5804 | +0.5114 | +0.2013 | +0.3778 | +1.385 | -0.010 | -0.1403 | 0.380 | +0.0211 | AMD | fail |

## 6. Aggregate Metrics
- Mean gross return: +0.7562
- Mean net return: +0.7562
- Mean net benchmark gap: -0.2734
- Mean net Sharpe: +1.075
- Mean benchmark Sharpe gap: -0.301
- Primary ranking metric: +0.0070
- Stability CV: 0.750
- 2/3 benchmark pass achieved: no
- Recent window pass: no
- Single-ticker dominance: no
- Largest ticker contribution share: 0.610

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: FAIL
- G3 Stability: PASS
- G4 Predictive Support: FAIL
- G5 Cost Survivability: FAIL

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.1658 | 0.088 | supporting |
| AMD | +0.9742 | 0.517 | supporting |
| NVDA | +0.6207 | 0.330 | supporting |
| QQQ | +0.1034 | 0.055 | supporting |
| SPY | +0.0193 | 0.010 | supporting |

## 9. Final Verdict
**Verdict**: KILL
**Reason**: mean net benchmark gap -0.2734, recent-window gap +0.3778, rank metric +0.0070, largest ticker share 0.610.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

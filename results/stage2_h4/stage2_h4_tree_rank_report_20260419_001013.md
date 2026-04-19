# Stage 2 H4 Results Report

Date: 2026-04-19
Hypothesis: H4 - Concentration-Capped Cross-Sectional Ranking
Run ID: tree_rank
Status: kill

## 1. Run Metadata
- Universe: AAPL, AMD, NVDA, QQQ, SPY
- Model family: tree_rank
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
| 0 | 2021-03-31 to 2022-10-31 | +0.0194 | +0.0194 | +0.0518 | +0.0184 | +0.2105 | -0.0324 | +0.268 | -0.001 | -0.5113 | 0.430 | -0.1053 | AMD | fail |
| 1 | 2022-10-31 to 2024-05-31 | +1.8846 | +1.8846 | +1.7967 | +2.4566 | +1.8724 | -0.5720 | +1.760 | -0.703 | -0.1513 | 0.480 | -0.0579 | NVDA | fail |
| 2 | 2024-05-31 to 2025-12-31 | +0.1095 | +0.1095 | +0.5804 | +0.5114 | +0.2013 | -0.4709 | +0.393 | -1.002 | -0.2305 | 0.580 | -0.1895 | AAPL | fail |

## 6. Aggregate Metrics
- Mean gross return: +0.6712
- Mean net return: +0.6712
- Mean net benchmark gap: -0.3584
- Mean net Sharpe: +0.807
- Mean benchmark Sharpe gap: -0.568
- Primary ranking metric: -0.1175
- Stability CV: 1.280
- 2/3 benchmark pass achieved: no
- Recent window pass: no
- Single-ticker dominance: no
- Largest ticker contribution share: 0.658

## 7. Gate Check
- G1 Benchmark Superiority: FAIL
- G2 Economic Robustness: FAIL
- G3 Stability: FAIL
- G4 Predictive Support: PASS
- G5 Cost Survivability: FAIL

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.3064 | 0.190 | supporting |
| AMD | +0.4576 | 0.284 | supporting |
| NVDA | +0.6995 | 0.435 | supporting |
| QQQ | -0.0112 | 0.000 | supporting |
| SPY | +0.1457 | 0.091 | supporting |

## 9. Final Verdict
**Verdict**: KILL
**Reason**: mean net benchmark gap -0.3584, recent-window gap -0.4709, rank metric -0.1175, largest ticker share 0.658.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

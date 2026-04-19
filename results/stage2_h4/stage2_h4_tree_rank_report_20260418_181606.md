# Stage 2 H4 Results Report

Date: 2026-04-18
Hypothesis: H4 - Concentration-Capped Cross-Sectional Ranking
Run ID: tree_rank
Status: pass

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
| 0 | 2019-11-29 to 2022-10-31 | +10.3444 | +10.3444 | +1.1594 | +1.0821 | +1.5141 | +9.1850 | +2.324 | +1.408 | -0.1599 | 0.669 | +0.8129 | NVDA | pass |
| 1 | 2021-06-30 to 2024-05-31 | +13.8470 | +13.8470 | +1.1908 | +1.4617 | +1.8051 | +12.3852 | +2.402 | +1.398 | -0.1599 | 0.503 | +0.8333 | NVDA | pass |
| 2 | 2023-01-31 to 2025-12-31 | +20.1663 | +20.1663 | +2.6359 | +3.0598 | +2.2026 | +17.1065 | +3.314 | +1.410 | -0.0554 | 0.461 | +0.8304 | NVDA | pass |

## 6. Aggregate Metrics
- Mean gross return: +14.7859
- Mean net return: +14.7859
- Mean net benchmark gap: +12.8923
- Mean net Sharpe: +2.680
- Mean benchmark Sharpe gap: +1.405
- Primary ranking metric: +0.8255
- Stability CV: 0.275
- 2/3 benchmark pass achieved: yes
- Recent window pass: yes
- Single-ticker dominance: no
- Largest ticker contribution share: 0.566

## 7. Gate Check
- G1 Benchmark Superiority: PASS
- G2 Economic Robustness: PASS
- G3 Stability: PASS
- G4 Predictive Support: PASS
- G5 Cost Survivability: PASS

## 8. Ticker Contribution Analysis
| Ticker | Contribution to Edge | Share of Total Edge | Notes |
| ------ | -------------------- | ------------------- | ----- |
| AAPL | +0.2957 | 0.032 | supporting |
| AMD | +3.5937 | 0.392 | supporting |
| NVDA | +4.8200 | 0.526 | supporting |
| QQQ | +0.0851 | 0.009 | supporting |
| SPY | +0.3677 | 0.040 | supporting |

## 9. Final Verdict
**Verdict**: PASS
**Reason**: mean net benchmark gap +12.8923, recent-window gap +17.1065, rank metric +0.8255, largest ticker share 0.566.

## 10. Notes
Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.

# Session Notes — May 15, 2026

## Status: 3-Ticker Ensemble Complete ✅ | Next: Exit Signal Phase 1

### Final Promoted Ensemble (Mac-native model files)
| Ticker | Seeds | Label | Alpha | min_hold | Exp 9 |
|--------|-------|-------|-------|----------|-------|
| NVDA | 3,13,7,42 | nvda-ppo-minhold1-extended | +0.11–+0.52 | **1** | PASS (G1/G2/G3, agree=0.82, conf=0.85) |
| AMD | 13,21,7 | amd-ppo-hold-fix | +0.28 | 3 | PASS |
| MU | 21,3,13 | mu-ppo-overtrade-fix | +1.82 | 1 | PASS (G1/G2/G3, agree=1.00, conf=0.92) |

### Deferred Tickers (no Mac model files, signal incompatible)
| Ticker | Reason | Sweeps Run |
|--------|--------|-----------|
| AMZN | Drift wall 0.54-0.55, GOOGL/AAPL pattern | 1 |
| GOOGL | Drift wall 0.55-0.57, 5 sweeps exhausted | 5 |
| AAPL | Total inaction both val+test, 7 sweeps | 7 |

### Key Architectural Findings This Session
- min_hold_bars=1 is correct for high-volatility momentum plays (NVDA, MU)
- min_hold_bars=3 is correct for lower-volatility tickers (AMD)
- Gate 6 waiver granted for MU: semiconductor upcycle, 55.5% win rate, penalty-unresponsive
- AMZN/GOOGL original Windows champions were always-long (90%+) riding the 2024 bull run — not reproducible on updated test splits

### Next: Exit Signal Phase 1
File to create: `src/exit_manager.py`

Phase 1 rules:
1. **Confidence-based:** Exit when ensemble confidence < threshold
2. **Trailing stop:** Exit after K bars of unrealized loss > X% from entry
3. **Time-based:** Maximum hold = N bars

Dev order:
1. Implement ExitManager class with rule interface
2. Backtest on NVDA test split (428 rows, 2024-08-14 to 2026-04-29)
3. Tune thresholds on val split only — NO test data for tuning
4. Report: exits triggered, avg hold reduction, PnL vs no-exit baseline

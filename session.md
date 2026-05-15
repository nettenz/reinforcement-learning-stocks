# Session Notes — May 14, 2026

## Status: AAPL Formally Deferred ❌ | Ensemble at 5/6 | Next: Exit Signal Phase 1

### AAPL Deferral Summary
7 sweeps, all levers exhausted:
- `aapl-ppo-double-loosen` ×2: 0.0% trade rate
- `aapl-ppo-minhold1` (min_hold_bars=1): 0.0%, drift=0.000 (no trading in val either)
- `aapl-ppo-high-entropy` (ent_coef 0.10–0.20, 100k steps): 0.0% unchanged

Gate 4 drift=0.000 with 0% val AND test = no reward gradient above zero in training itself.
AAPL is architecturally incompatible with Binary PPO. Not a tuning problem.
Do not run further AAPL sweeps under this architecture.

### Final Promoted Ensemble
| Ticker | Seeds | Architecture | min_hold | Alpha |
|--------|-------|--------------|----------|-------|
| NVDA | 3,13,7,42 | PPO Binary | **1** | +0.11–+0.52 |
| AMD | 13,21,7 | PPO Binary | 3 | +0.28 |
| MU | 42,7 | PPO Binary | 3 | +0.15 |
| AMZN | 7,13,42 | PPO Binary | 3 | +0.11 |
| GOOGL | 13 | PPO Binary | 3 | +0.66 |
| AAPL | ❌ Deferred | — | — | — |

### Next: Exit Signal Phase 1
File: `src/exit_manager.py` (create if not exists)

Phase 1 rules to implement:
1. **Confidence-based:** Exit when ensemble confidence < threshold (e.g. 0.60)
2. **Trailing stop:** Exit after K bars of unrealized loss > X% from entry
3. **Time-based:** Maximum hold = N bars regardless of signal

Development order:
1. Implement `ExitManager` class with rule interface
2. Backtest on NVDA test split (428 rows, 2024-08-14 to 2026-04-29)
3. Tune thresholds on val split — DO NOT tune on test
4. Report: exits triggered, avg hold reduction, PnL impact vs no-exit baseline

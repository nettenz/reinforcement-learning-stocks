# Session Notes — May 14, 2026

## Status: NVDA Binary PPO Retrofit COMPLETE ✅

### What happened this session
- Ran `nvda-ppo-raw-features` (Exp A): 0.0% trade rate — ruled out feature space as root cause
- Diagnosed Gate 4 drift = 0.56 → val accuracy ~0.56, test = 0.0 → regime generalization failure, not pure inaction
- Ran `nvda-ppo-minhold1-extended` (Exp C): **BREAKTHROUGH** — 7/10 configs, all 6 gates passed
  - Champion: seed 3 (Sharpe 2.03), stable cluster: seeds 13, 7, 42, 21 (CV 0.19)
  - Root cause confirmed: `min_hold_bars=3` was the sole architectural blocker for NVDA
- Generated ensemble config with `--top-n 4`, seeds [3, 13, 7, 42]
- Fixed `run_exp9_walkforward.py` to read `use_stationary_features` from ensemble config
- Added `"use_stationary_features": false` to NVDA entry in `ensemble_config.json`
- **Exp 9 PASS**: G1 0.548≥0.536, G2 agreement 0.82, G3 unanimous 0.57. Avg conf 0.85.

### Key architectural finding
NVDA's signal distribution requires short-duration holds. `min_hold_bars=3` makes cash always
the lower-risk choice → total inaction. `min_hold_bars=1` immediately unlocked trading.
This is ticker-specific. Always ablate min_hold_bars before penalty/feature tuning.

### Promoted ensemble (ensemble_config.json)
| Ticker | Seeds | Architecture | min_hold | Alpha |
|--------|-------|--------------|----------|-------|
| NVDA | 3,13,7,42 | PPO Binary | **1** | +0.11–+0.52 |
| AMD | 13,21,7 | PPO Binary | 3 | +0.28 |
| MU | 42,7 | PPO Binary | 3 | +0.15 |
| AMZN | 7,13,42 | PPO Binary | 3 | +0.11 |
| GOOGL | 13 | PPO Binary | 3 | +0.66 |
| AAPL | — | Blocked | — | — |

## Next Steps
1. **AAPL**: Apply `min_hold_bars=1` ablation (same fix as NVDA). Prior sweeps all used min_hold=3.
2. **Exit Signal Phase 1**: Now unblocked. Start with `src/exit_manager.py`, backtest on NVDA test split.
3. **AAPL one-liner:**
   ```zsh
   source .venv/bin/activate && python3 src/experiments.py --ticker aapl --reward-mode sharpe --ent-coefs 0.05,0.08 --timesteps 80000 --seeds 3,7,13,21,42 --execution-mode next_bar --binary-actions --min-hold-bars 1 --max-weight-delta-per-step 0.10 --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.01 --n-envs 1 --run-label "aapl-ppo-minhold1" --append
   ```

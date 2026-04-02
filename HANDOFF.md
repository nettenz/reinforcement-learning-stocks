# Cross-Platform Handoff: Dashboard Integrity + Stability Safeguards

Updated: 2026-04-01

Use this handoff to resume quickly on Windows/macOS.

## Optimization Handoff Entry Point
- Primary optimization handoff is now in `implementation_plan.md`.
- That file includes:
   - Reality-checked optimization objectives and guardrails
   - Promotion gates for model/config acceptance
   - Windows command templates for baseline/coarse/focused sweeps
   - A copy/paste "Custom Agent Instruction Seed" for a dedicated optimization agent
- Latest session handoff: `sessions/session-2026-04-01-model-alignment-and-curated-picker.md`.

## Current Status
- Dashboard launcher is stable (`run_dashboard.ps1` start/status/stop fixed for stale/duplicate PID handling).
- Dashboard runtime integrity verified (`HTTP 200`) after start via PowerShell launcher.
- `TradingEnv.step()` now handles scalar/0-d/1-d actions safely (fixes IndexError in dashboard evaluation path).
- Legacy PPO discrete actions now map correctly to continuous environment semantics (0 Hold, 1 Buy, 2 Sell).
- Experiment pipeline now defaults to anti-overfit/stability-friendly settings and exposes config-level return CV risk.

## Fixes Applied in This Session
1. `run_dashboard.ps1`
   - Deduplicate process IDs before stop.
   - Skip stale/exited PIDs without failing.
   - Avoid PowerShell reserved `$PID` variable collision.
2. `src/trading_env.py`
   - Robust action parsing (`np.asarray`, 0-d + vector support).
   - Backward compatibility mapping for PPO discrete actions to target weights.
3. `src\experiments.py`
   - New defaults:
     - `--reward-mode sharpe`
     - `--ent-coefs 0.02,0.05`
     - `--timesteps 20000,40000`
   - Added per-config stability metrics:
     - `test_return_mean_by_config`
     - `test_return_std_by_config`
     - `test_return_cv_by_config`
     - `high_return_cv_risk` (`CV >= 1.0`)
4. `src\analytics_dashboard.py`
   - Experiments page defaults aligned with new anti-overfit settings.
   - Best run snapshot surfaces `Config Test Return CV` and `High CV Risk`.
   - Insights recommendations now bias toward shorter timesteps + higher entropy + Sharpe mode.

## Runtime Verification Performed
- `.venv\Scripts\python.exe -m py_compile src\analytics_dashboard.py src\signal_analytics.py src\trading_env.py src\experiments.py` ✅
- `.venv\Scripts\python.exe tests\test_script.py` ✅
- `.\run_dashboard.ps1 -Action start/status/stop -Port 8501` ✅

## Confirmed Signal Behavior (Post-Fix)
- `models\ppo_trading_bot_with_news.zip`: includes Sell signals.
- `models\ppo_trading_bot_no_news.zip`: includes Sell signals.
- `models\ppo_trading_bot.zip`: includes Sell signals.
- `models\sac_trading_bot.zip`: includes Sell signals.

## Recommended Next Experiment Command (Windows / .venv)
```powershell
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13,21,42,84 --timesteps 20000,40000 --learning-rates 0.0003,0.0001 --gammas 0.99,0.995 --ent-coefs 0.02,0.05 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-mode sharpe --reward-return-scale 1.0 --reward-direction-scale 0.35 --reward-hold-penalty-scale 0.10 --reward-drawdown-penalty-scale 0.10 --reward-action-bonus-scale 0.02 --reward-clip 1.0 --reward-ignore-transaction-cost --append --run-label sharpe-stability-v1
```

## Quick Leaderboard CV Check
```powershell
.\.venv\Scripts\python.exe -c "import pandas as pd; df=pd.read_csv('data/experiment_leaderboard.csv'); cols=[c for c in ['reward_mode','timesteps','ent_coef','test_cumulative_signal_return','test_return_cv_by_config','high_return_cv_risk','ranking_score'] if c in df.columns]; print(df[cols].head(15).to_string(index=False))"
```

## Dashboard Start (Windows)
```powershell
.\run_dashboard.ps1 -Action start -Port 8501
```

## Promotion Gate (Suggested)
Promote only configs satisfying:
1. `test_actionable_accuracy >= 0.53`
2. `test_trade_win_rate >= 0.52`
3. `test_alpha_vs_qqq >= 0.00`
4. `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05`
5. `test_return_cv_by_config < 1.0`

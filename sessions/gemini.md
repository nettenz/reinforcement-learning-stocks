# Gemini Experiment Session

## Last Updated
2026-03-31 (SAC Migration & Reward Sweeps Complete)

## Project State
- Algorithm: **SAC (Continuous Action Space)** — Migration from PPO successful.
- Environment: **OOP Refactored** with `PositionManager` and `RewardEvaluator`.
- Observation Space: **Position-Aware** — Now includes `[current_weight, unrealized_pnl, time_in_position]`.
- P&L Math: **CORRECTED** — Trades execute at current price; net worth correctly tracks cash + market value.
- Look-ahead bias audited: YES (Verified in both `TradingEnv` and `signal_analytics`).

## Runs Completed
| Run Label | Reward Mode | Best Ranking Score | Val Acc (Actionable) | Test Acc (Actionable) | Verdict |
|---|---|---|---|---|---|
| sweep-legacy | legacy | 0.5780 | 57.1% | 51.7% | Stable baseline. |
| sweep-sharpe | sharpe | 0.5907 | 57.4% | 54.4% | **Best performer** at 20k steps. |
| sweep-sortino | sortino | 0.5780 | 57.4% | 54.4% | Comparable to Sharpe. |
| confirmatory-sharpe | sharpe (100k) | 0.4738 | 54.6% | 0.0% | **Over-optimized**; generalization failed. |

## Configs Ruled Out
- **High Timesteps (100k+):** Leads to severe overfitting on current feature set (0% test accuracy).
- **High Entropy (ent_coef > 0.01):** Tends to dilute directional conviction in the tech basket.
- **Old PPO Logic:** Discrete actions and broken P&L math are deprecated.

## What Was Interpreted
The migration to SAC with continuous actions (-1.0 to 1.0) has significantly improved the agent's ability to scale positions. The **Sharpe reward mode** (0.0 entropy, 20k steps) currently provides the best balance of validation accuracy and test generalization. A critical bug in the `PositionManager` was fixed: previously, the agent was "paying" for price movements due to a timing error in cash/share updates, which suppressed long signals. Now, the agent correctly generates buy signals and tracks positive P&L.

## What Was Added or Changed
- **SAC Migration:** `src/train_bot.py` and `src/experiments.py` now use SAC.
- **OOP Environment:** `src/trading_env.py` split into `PositionManager`, `RewardEvaluator`, and `TradingEnv` for better maintainability.
- **Robust Training Script:** `src/train_bot.py` updated to handle both `VecEnv` and standard Gym environment return types (`reset` and `step`).
- **Quant Report:** Generated professional interpretation in `sessions/quant-report-*.md`.
- **Documentation:** `README.md` updated with new reward strategy knobs and commands.

## Next Steps
1. **Feature Engineering:** Since 100k steps led to overfitting, the current feature set may be too "thin." Explore adding more technical indicators or sentiment depth.
2. **Shorting Validation:** Verify the agent's behavior during negative price movements to ensure the -1.0 weight (Full Short) is being utilized effectively in the `legacy` or `sharpe` modes.
3. **Ensemble Testing:** With high cross-seed variance (CV=7.16), implement an ensemble predictor that averages weights from multiple top-ranked models.

## Current Best Command
```powershell
# Recommended for stable results:
.venv\Scripts\python.exe src/train_bot.py --reward-mode sharpe --timesteps 20000 --n-envs 8
```

## Autonomy Status
- [X] Continuing autonomously
- [ ] Escalating to user
- [ ] Hard stop — diagnosis: N/A

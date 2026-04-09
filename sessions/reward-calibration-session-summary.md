# Session Summary: Entropy Calibration and Reward-Cal Next Step

## Latest Results
The 10-seed entropy calibration batch established `ent_coef=0.10` as the best current lead.

Observed cohort means:
- `ent=0.06`: test Sharpe `0.0056`, test Sortino `-0.0206`, test alpha `-0.1944`, CV `12.53`
- `ent=0.08`: test Sharpe `0.1415`, test Sortino `0.1807`, test alpha `-0.1301`, CV `8.93`
- `ent=0.10`: test Sharpe `0.2770`, test Sortino `0.3701`, test alpha `-0.0919`, CV `1.79`

The strongest lead is still not promotion-ready because alpha remains negative and the config CV is above target, but the move to `ent=0.10` is a meaningful stability improvement.

## Interpretation
The entropy sweep suggests exploration was a real bottleneck, but not the whole bottleneck. The model is now more stable, yet it still does not produce positive benchmark-relative alpha. That points to reward shaping rather than exploration as the next lever.

## Reward-Shape Diagnosis
The current reward system remains a hybrid of:
- rolling Sharpe or Sortino base
- directional shaping
- flat-position penalty
- action bonus
- turnover penalty
- drawdown penalty
- execution costs that are partly ignored in the reward signal

Two implementation notes matter:
- `reward_sharpe_scale` exists but is not used.
- The learning signal is still not explicitly weighting realized P&L enough for a benchmark-alpha objective.

## Correctness / Compatibility Update
A backward-compatible reward-P&L path was added to the OOP environment layer and wired through the experiment runner:
- `RewardEvaluator` now accepts `pnl_scale`
- `TradingEnv` now accepts `reward_pnl_scale`
- `experiments.py` now passes `reward_pnl_scale` through the CLI and per-run config

This keeps current behavior unchanged when `reward_pnl_scale=0.0`.

## Proposed Next Batch
Use the new reward-calibration launcher:
- [run_reward_calibration.ps1](../run_reward_calibration.ps1)

Batch design:
- Fixed: `ent_coef=0.10`, `reward_direction_scale=0.35`, `reward_mode=sharpe`, `ticker=nvda`, `timesteps=20000`
- Seed list: `7,13,21,42,84,101,123,256,512,777`
- Arms:
  - baseline: `pnl=0.00`, `turnover=0.05`, `drawdown=0.10`
  - balanced: `pnl=0.10`, `turnover=0.04`, `drawdown=0.12`
  - aggressive: `pnl=0.20`, `turnover=0.03`, `drawdown=0.15`

## Success Criteria
- Mean test alpha improves toward zero or positive
- Mean test Sharpe stays near or above the current `ent=0.10` lead
- Config CV does not worsen materially
- No single seed dominates the result

## If Reverting Is Needed
Revert only if the reward calibration batch worsens test alpha and CV without a compensating Sharpe lift, or if the new `reward_pnl_scale` term creates a noisy or unstable learning signal.

Rollback path:
- Set `reward_pnl_scale=0.0` in the next batch and keep `ent_coef=0.10` fixed.
- Keep `reward_return_scale`, `reward_direction_scale`, turnover, and drawdown settings at the current baseline values.
- Do not remove the code paths unless the new term is confirmed harmful across multiple seeds; the wiring is backward-compatible and safe to leave in place.
- If a hard revert is required, remove the `reward_pnl_scale` CLI usage from the launcher and restore the previous `run_reward_calibration.ps1` baseline arm as the only comparison point.

## Comparability
Impact level: Medium.

Reason:
- Reward semantics are changing through explicit P&L weighting.
- The data/feature space is unchanged.
- Historical leaderboards remain comparable within `leaderboard_version=2`, but reward-calibration results should be analyzed as a new sub-regime, not pooled blindly with earlier entropy sweeps.

## Recommendation
Proceed with reward calibration after the current entropy run completes. If the reward batch fails to improve alpha and stability, pivot to environment realism and cost semantics before any larger reward redesign.

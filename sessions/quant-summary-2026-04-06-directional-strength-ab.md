# Quant Summary — Directional-Strength A/B

**Date:** 2026-04-06
**Scope:** NVDA, 20k timesteps, next-bar execution, Sharpe reward, same seeds

## Conclusion
The latest completed batch supports a narrow next experiment: a directional-strength A/B on the confirmed base. The most defensible base remains `ent_coef=0.05` with `reward_action_bonus_scale=0.02`. The strategy is still not promotion-ready because test alpha remains negative and the confirmed base is only near the actionable gate, not comfortably above it.

## Evidence
- `ent_coef=0.05` outperformed `0.02` on the 20k next-bar Sharpe setup.
- `reward_action_bonus_scale=0.02` was more stable than `0.05`.
- The hold-penalty reduction experiment regressed and should not be used as a next base.
- Fresh-seed confirmation improved Sharpe but did not resolve benchmark alpha.

## Recommended next run
- Compare `reward_direction_scale=0.35` vs `0.40`.
- Keep everything else fixed: `ent_coef=0.05`, `reward_action_bonus_scale=0.02`, `timesteps=20000`, `threshold=0.002`, `horizon=1`, `execution_mode=next_bar`.
- Judge by mean test actionable accuracy, mean test alpha vs QQQ, mean test Sharpe, and seed variance.

## Interpretation
- If actionable accuracy rises without alpha deterioration, the directional term is a useful final calibration lever.
- If alpha worsens or stability drops, the strategy needs downside-control tuning instead of more directional pressure.
- Single-seed improvement is not enough; only cohort-level gain counts.

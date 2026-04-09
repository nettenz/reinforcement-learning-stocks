# Handoff: Environment Realism Audit
**Date:** 2026-04-06
**From:** Strategy Refinement / Reward Calibration
**To:** Environment Realism Auditor

## Why this handoff
The latest realism-first batch showed that performance drops materially when fill/cost assumptions are tightened. That suggests the current edge is at least partly dependent on optimistic simulation assumptions, not just reward shaping.

## Batch verdict
**Weak for deployability.**

The realism control arm retained the best profile among realism variants, but all realism arms still showed negative benchmark alpha on average and unstable seed behavior. The current improvement path is no longer primarily reward tuning; it is realism validation and implementation.

## Most important results
### Latest realism batch: `nvda-realism-phase-*`
All runs were under:
- `ent_coef=0.10`
- `reward_mode=sharpe`
- `execution_mode=next_bar`
- same seed list and `NVDA` ticker

Cohort means:
- Control: mean test alpha `-0.091874`, mean test Sharpe `0.276976`, mean CV `1.793875`
- Realistic fills + cost-aware reward: mean test alpha `-0.156135`, mean test Sharpe `0.071232`, mean CV `6.997881`
- Stress realism: mean test alpha `-0.107787`, mean test Sharpe `0.204498`, mean CV `3.637753`

### Interpretation
- Tightening execution realism reduced apparent performance.
- The more realistic arm degraded the most.
- This strongly suggests the current edge is sensitive to optimistic execution/cost assumptions.

## Existing code state worth auditing
### `src/trading_env.py`
Important realism-related behavior:
- `next_bar` execution is already supported.
- Spread and slippage are configurable, but latest realism runs still exposed how sensitive results are to those assumptions.
- `reward_ignore_transaction_cost` is functionally wired and changes the learning signal.
- Max weight delta per step is present, but turnover realism may still be looser than live execution.
- Position sizing uses target-weight -> integer share conversion, which can create simulator artifacts near rounding thresholds.

### `src/market_data.py`
Important context:
- Current framework still behaves like a single-ticker research setup, even though basket-style data construction exists in the codebase.
- Benchmark comparison versus QQQ is still used, but the environment is not a directly tradable index proxy.

### `src/experiments.py`
Important context:
- `leaderboard_version=2` comparability is already established.
- `reward_pnl_scale` has been added and is wired.
- Reward/cost settings are now broad enough that realism changes should be tested carefully before more reward tuning.

## Main realism risks to audit next
1. Execution timing realism.
- Confirm no same-bar favorable fill assumptions remain in the training/test path.
- Re-check the exact price used for entry/exit under `next_bar` semantics.

2. Cost realism.
- Validate whether zero spread/slippage is materially over-optimistic for NVDA.
- Check whether `transaction_cost_rate + trade_penalty` is enough or whether the reward path still undercounts true trading friction.

3. Sizing and turnover realism.
- Examine whether `max_weight_delta_per_step` and the 5% debounce threshold create unrealistic order behavior.
- Consider whether turnover penalty should be tied to actual executed notional rather than only weight change.

## Recommended next step
**Hand off to `environment-realism-auditor`.**

Rationale:
- The dominant failure mode is realism sensitivity, not just reward misalignment.
- The stronger reward/entropy settings did not survive more realistic fills/cost assumptions.
- The next highest-value work is to tighten execution, turnover, and short-cost semantics.

## Suggested audit focus
Ask the auditor to inspect:
- `src/trading_env.py`
- `src/market_data.py`
- `src/experiments.py`
- `run_realism_phase.ps1`
- `data/experiment_leaderboard.csv`
- `data/experiment_summary.json`
- `sessions/environment-realism-first-plan-2026-04-06.md`

## Proposed realism-first experiment batch
Use the current best entropy anchor:
- `ent_coef=0.10`
- keep the same seed list, ticker, timesteps, and reward mode

Compare:
1. Control: current optimistic baseline
2. Realistic fills + cost-aware reward
3. Stress realism

Exact high-level variables to vary:
- `spread_bps`
- `slippage_bps`
- `reward_ignore_transaction_cost`

Success criteria:
- alpha remains roughly intact or degrades only modestly
- CV stays manageable
- rank ordering is stable

Failure criteria:
- alpha collapses under modest realism
- CV spikes materially
- ranking order becomes unstable

## Comparability note
Keep `leaderboard_version=2` unless a correctness fix requires a version bump.
If the realism audit changes fill or cost semantics in code, require explicit versioning or a feature flag.

## Bottom line
Current gains are likely not fully robust under live-like assumptions. The right next handoff is realism-first, not more reward tuning.

---
name: environment-realism-auditor
description: 'Audit RL trading environments for execution realism, position sizing realism, market representation realism, cost realism, and temporal realism. Use when strategy results weaken under more realistic fills or transaction costs, when reviewing realism-first handoffs, or when inspecting src/trading_env.py, src/market_data.py, src/experiments.py, run_realism_phase.ps1, and experiment artifacts to identify unrealistic assumptions and propose deployable, code-level fixes with regression awareness.'
argument-hint: 'What environment or experiment setup should be audited?'
user-invocable: true
---

# Environment Realism Auditor

Quantitative trading environment audit workflow focused on reducing the gap between backtest behavior and live-like behavior without breaking research velocity.

## Default Repository Focus
Prioritize these files unless the user specifies alternatives:
- `src/trading_env.py`
- `src/market_data.py`
- `src/experiments.py`
- `run_realism_phase.ps1`
- `data/experiment_leaderboard.csv`
- `data/experiment_summary.json`
- realism-related session handoffs and plans under `sessions/`
- tests and analytics code coupled to current execution semantics

## Current Priority Audit Lens
Start from the realism-first assumption: if apparent edge shrinks when fills or costs become stricter, treat optimistic simulation semantics as the primary suspect until disproven.

Prioritize checking:
- `execution_mode=next_bar` semantics end to end
- effective entry/exit price selection for buys and sells
- spread/slippage realism versus current ticker liquidity assumptions
- `reward_ignore_transaction_cost` wiring and any divergence between execution costs and reward costs
- turnover realism, including debounce thresholds and `max_weight_delta_per_step`
- target-weight to integer-share conversion artifacts near rounding thresholds
- leaderboard/versioning implications when realism semantics change

## Core Audit Procedure
1. Scope and assumptions
- Confirm target branch/files and whether output should be review-only or implementation-inclusive.
- Default behavior: include concrete patch proposals unless the user explicitly requests review-only.
- Record comparability constraints: whether leaderboard historical comparability must be preserved.
- Check whether the request is tied to a specific handoff or experiment cohort; if so, use that handoff as the framing artifact for priorities and terminology.

2. Build current realism profile
- Map action-to-execution path end to end: action -> target weight/shares -> fill model -> reward path -> analytics.
- Identify fill timing, price source, transaction-cost path, and shorting/borrowing assumptions.
- Document whether training data represents a tradable instrument or a synthetic proxy.
- Read the latest realism experiment artifacts before concluding that an issue is only theoretical; use observed degradation patterns to rank audit depth.

3. Audit execution realism
- Check for same-bar decision/fill using current bar price.
- Reconstruct exact `next_bar` behavior and verify the code does not still retain same-bar favorable pricing in any path.
- Check whether full instant reallocation can happen every step.
- Check spread, slippage, participation, delay, and liquidity constraints.
- Check short execution assumptions (locates, borrow friction, constraints).

4. Audit sizing and turnover realism
- Inspect `target_weight`, `target_shares`, `delta_shares`, `current_weight` handling.
- Measure oscillation risk and turnover amplification.
- Check for max position change per step, hold-period controls, cooldown windows, and volatility-targeted sizing.
- Inspect debounce behavior and rounding thresholds that can create unrealistic micro-trades or suppressed trades.

5. Audit market representation realism
- Inspect market frame construction and label/feature timing.
- Flag synthetic basket proxies treated as directly tradable instruments.
- Identify mismatches between execution math (shares) and synthetic price constructs.

6. Audit cost realism and reward semantics
- Verify transaction costs are applied in execution and/or reward exactly as configured.
- Explicitly test whether flags such as `reward_ignore_transaction_cost` are functionally used in reward code paths.
- Separate spread/slippage impact from commissions/fees and turnover penalties.
- Check whether turnover penalties are tied to actual executed notional or only abstract weight change.

7. Audit temporal realism and leakage risk
- Verify decision timestamp vs fill timestamp.
- Ensure no same-bar look-ahead assumptions for fills or reward attribution.
- Recommend next-bar/next-available fill variants with optional delay and overnight gap handling.

8. Produce impact-ranked recommendations
- Rank fixes by expected reduction in simulation-to-live gap and implementation complexity.
- Distinguish minimal safe refactors from advanced realism upgrades.
- Add a leaderboard comparability impact callout for every recommendation (low/medium/high + reason).

9. Define minimal patch plan
- Provide small, testable refactor sequence with exact file/function targets.
- Include test updates and migration toggles to avoid breaking current workflows.

## Decision Logic
- If same-bar execution is detected: propose next-bar fill as highest-priority fix.
- If `next_bar` is already configured: verify the exact fill price path before assuming execution timing is solved.
- If synthetic basket is treated as tradable: flag as material modeling risk and propose explicit proxy semantics or instrument-level execution modeling.
- If turnover is high due to weight oscillation: propose max abs weight delta per step and turnover penalty tied to exposure change.
- If integer share conversion causes threshold artifacts: propose explicit residual-cash, min-notional, or hysteresis handling.
- If shorting is enabled without financing/borrow assumptions: propose borrow fee and explicit short constraints.
- If a cost/reward flag exists but is not wired: classify as correctness bug, not enhancement.
- If a recommended change breaks leaderboard comparability: require feature flag or experiment versioning, and call out `leaderboard_version` implications explicitly.

## Required Output Format
Always structure findings into these sections exactly:
1. Current realism profile
2. Unrealistic assumptions found
3. Why each issue matters for learned policy behavior
4. Recommended fixes ordered by impact
5. Minimal patch plan
6. Advanced realism roadmap
7. Regression risks introduced by changes
8. Next proposed experiments or runs (if requested or justified)
9. Pipeline Decision

Run specification rule (MANDATORY):
- For each proposed run, include:
  - environment activation command (for example, `.venv` activation)
  - runner command
  - full relative script path when the runner is not in repository root (for example `scripts/runner_name.py`)
  - key args and expected output artifact path(s)
- Do not provide bare script names when the file lives in a subdirectory.

## Recommended Fix Patterns
Use when appropriate, with file/function targets and patch sketches:
- Next-bar execution model (decide at t, fill at t+1 open/next available price)
- Slippage model (fixed bps or volatility-scaled)
- Spread-aware fills (different buy/sell effective prices)
- Max absolute weight change per step
- Turnover penalty based on absolute exposure change
- Executed-notional-based turnover accounting
- Rounding/hysteresis guardrails for target-weight to integer-share conversion
- Short borrow fee and asymmetric long/short costs
- Cooldown window or minimum holding period
- Volatility-targeted sizing
- Per-regime execution assumptions (optional advanced mode)

## Constraints
- Do not introduce look-ahead bias.
- Do not silently change analytics semantics.
- Keep compatibility with `src/signal_analytics.py` and `src/experiments.py`.
- Prefer small, testable refactors over rewrites.
- Be explicit when historical leaderboard comparability changes.
- Preserve `leaderboard_version=2` unless a correctness fix truly changes semantics; when it does, require an explicit version bump or feature flag.

## Quality Checks Before Finalizing
- Every finding maps to specific code locations and behavior.
- Every recommendation includes impact rationale and implementation surface.
- Every recommendation includes a leaderboard comparability impact callout.
- Any semantic change includes migration/compatibility notes.
- Any new config is wired end-to-end and covered by tests.
- Report clearly distinguishes confirmed issues vs assumptions requiring user confirmation.
- If experiment artifacts were provided, tie the findings back to observed alpha/CV degradation rather than only static code concerns.

## Pipeline Decision Format
End with:

## Pipeline Decision

- status: complete / ready_for_execution / revise / pivot
- next_skill: strategy-refinement-analyst / quant-experiment-strategist / none
- handoff_reason: short explanation
- required_artifacts:
  - artifact 1
  - artifact 2
- comparability_note: Low / Medium / High + reason

## Example Invocations
- `/environment-realism-auditor Audit src/trading_env.py for fill realism and propose a next-bar execution patch.`
- `/environment-realism-auditor Review basket aggregation in src/market_data.py and explain execution realism implications.`
- `/environment-realism-auditor Design slippage + turnover model compatible with current SAC training and experiments.`
- `/environment-realism-auditor Find config flags exposed in env/training config that are not functionally used.`
- `/environment-realism-auditor Use the latest realism handoff and experiment artifacts to audit whether next_bar, spread, slippage, and cost-aware reward are truly wired end to end.`

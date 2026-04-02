---
name: environment-realism-auditor
description: 'Audit RL trading environments for execution realism, position sizing realism, market representation realism, cost realism, and temporal realism. Use for src/trading_env.py, src/market_data.py, src/train_bot.py, and src/experiments.py when identifying unrealistic assumptions and proposing deployable, code-level fixes with regression awareness.'
argument-hint: 'What environment or experiment setup should be audited?'
user-invocable: true
---

# Environment Realism Auditor

Quantitative trading environment audit workflow focused on reducing the gap between backtest behavior and live-like behavior without breaking research velocity.

## Use This Skill When
- You need to audit a reinforcement-learning trading environment for realism.
- You suspect policy performance is inflated by unrealistic execution assumptions.
- You need concrete, code-level changes that preserve compatibility with existing training and experiment pipelines.
- You want a structured report with impact-ranked recommendations and migration risk notes.

## Default Repository Focus
Prioritize these files unless the user specifies alternatives:
- `src/trading_env.py`
- `src/market_data.py`
- `src/train_bot.py`
- `src/experiments.py`
- tests and analytics code coupled to current execution semantics

## Core Audit Procedure
1. Scope and assumptions
- Confirm target branch/files and whether output should be review-only or implementation-inclusive.
- Default behavior: include concrete patch proposals unless the user explicitly requests review-only.
- Record comparability constraints: whether leaderboard historical comparability must be preserved.

2. Build current realism profile
- Map action-to-execution path end to end: action -> target weight/shares -> fill model -> reward path -> analytics.
- Identify fill timing, price source, transaction-cost path, and shorting/borrowing assumptions.
- Document whether training data represents a tradable instrument or a synthetic proxy.

3. Audit execution realism
- Check for same-bar decision/fill using current bar price.
- Check whether full instant reallocation can happen every step.
- Check spread, slippage, participation, delay, and liquidity constraints.
- Check short execution assumptions (locates, borrow friction, constraints).

4. Audit sizing and turnover realism
- Inspect `target_weight`, `target_shares`, `delta_shares`, `current_weight` handling.
- Measure oscillation risk and turnover amplification.
- Check for max position change per step, hold-period controls, cooldown windows, and volatility-targeted sizing.

5. Audit market representation realism
- Inspect market frame construction and label/feature timing.
- Flag synthetic basket proxies treated as directly tradable instruments.
- Identify mismatches between execution math (shares) and synthetic price constructs.

6. Audit cost realism and reward semantics
- Verify transaction costs are applied in execution and/or reward exactly as configured.
- Explicitly test whether flags such as `reward_ignore_transaction_cost` are functionally used in reward code paths.
- Separate spread/slippage impact from commissions/fees and turnover penalties.

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
- If synthetic basket is treated as tradable: flag as material modeling risk and propose explicit proxy semantics or instrument-level execution modeling.
- If turnover is high due to weight oscillation: propose max abs weight delta per step and turnover penalty tied to exposure change.
- If shorting is enabled without financing/borrow assumptions: propose borrow fee and explicit short constraints.
- If a cost/reward flag exists but is not wired: classify as correctness bug, not enhancement.
- If a recommended change breaks leaderboard comparability: require feature flag or experiment versioning.

## Required Output Format
Always structure findings into these sections exactly:
1. Current realism profile
2. Unrealistic assumptions found
3. Why each issue matters for learned policy behavior
4. Recommended fixes ordered by impact
5. Minimal patch plan
6. Advanced realism roadmap
7. Regression risks introduced by changes

## Recommended Fix Patterns
Use when appropriate, with file/function targets and patch sketches:
- Next-bar execution model (decide at t, fill at t+1 open/next available price)
- Slippage model (fixed bps or volatility-scaled)
- Spread-aware fills (different buy/sell effective prices)
- Max absolute weight change per step
- Turnover penalty based on absolute exposure change
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

## Quality Checks Before Finalizing
- Every finding maps to specific code locations and behavior.
- Every recommendation includes impact rationale and implementation surface.
- Every recommendation includes a leaderboard comparability impact callout.
- Any semantic change includes migration/compatibility notes.
- Any new config is wired end-to-end and covered by tests.
- Report clearly distinguishes confirmed issues vs assumptions requiring user confirmation.

## Example Invocations
- `/environment-realism-auditor Audit src/trading_env.py for fill realism and propose a next-bar execution patch.`
- `/environment-realism-auditor Review basket aggregation in src/market_data.py and explain execution realism implications.`
- `/environment-realism-auditor Design slippage + turnover model compatible with current SAC training and experiments.`
- `/environment-realism-auditor Find config flags exposed in env/training config that are not functionally used.`

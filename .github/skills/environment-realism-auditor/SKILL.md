---
name: environment-realism-auditor
description: 'Audit trading environment assumptions for execution realism, cost realism, temporal realism, and sizing realism. Use when apparent edge weakens under stricter assumptions or when you need to identify unrealistic semantics before further optimization.'
argument-hint: 'What environment, execution path, or experiment setup should be audited for realism?'
user-invocable: true
---

# Environment Realism Auditor

Audit whether the environment is teaching on realistic assumptions.

## Objective
Reduce the gap between backtest behavior and live-like behavior without collapsing research clarity.

This skill focuses on whether the environment, execution model, and cost model are realistic enough for the conclusions being drawn.

It is not the final judge of experiment quality and it is not the main experiment planner.  
It is a specialist auditor for realism risk.

## Primary mindset
If apparent edge shrinks when fills, costs, or timing assumptions become stricter, optimistic simulation semantics are a primary suspect until disproven.

This skill asks:
- are fills too favorable?
- are costs too weak or inconsistently applied?
- is timing unrealistically generous?
- is sizing behavior too frictionless?
- is the instrument representation itself unrealistic?

## Use this skill when
- results weaken sharply under stricter fills or higher costs
- same-bar or overly favorable execution is suspected
- turnover looks unrealistic
- cost flags may not be wired correctly
- target-weight execution may be too frictionless
- synthetic basket assumptions may not match tradable reality
- environment semantics may be inflating apparent edge

## Do not use this skill when
- the main question is whether a batch is statistically robust
- the main task is to plan the next experiment batch
- the problem is primarily reward design rather than environment semantics
- the issue is mainly feature usefulness rather than execution realism

## Default Repository Focus
- `src/trading_env.py`
- `src/market_data.py`
- `src/experiments.py`
- `run_realism_phase.ps1`
- `data/experiment_leaderboard.csv`
- `data/experiment_summary.json`
- realism-related session notes and handoffs
- tests and analytics coupled to execution semantics

## Core Procedure

### 1. Scope the audit
Determine:
- target files
- target experiment cohort
- whether the output is review-only or implementation-inclusive
- whether leaderboard comparability must be preserved
- whether the audit is tied to a realism handoff or degradation event

### 2. Build the current realism profile
Map the full path:
- action
- target weight or shares
- execution timing
- fill price
- cost application
- reward path
- analytics interpretation

Document:
- price source used for fills
- transaction-cost handling
- shorting assumptions
- participation assumptions
- whether the traded object is a true instrument or a synthetic proxy

### 3. Audit execution realism
Check for:
- same-bar decision/fill behavior
- incorrect or incomplete `next_bar` semantics
- favorable buy/sell price selection
- frictionless instant reallocation
- unrealistic spread or slippage assumptions
- missing participation or liquidity constraints
- unrealistic short execution assumptions

### 4. Audit sizing and turnover realism
Inspect:
- target weight handling
- target shares and delta shares
- current weight updates
- oscillation risk
- max position change per step
- cooldown or minimum hold logic
- debounce behavior
- rounding artifacts near small deltas

### 5. Audit market representation realism
Inspect:
- whether the data frame represents a tradable instrument or a synthetic basket
- whether execution math assumes tradability that the data does not support
- whether price semantics and share semantics are aligned

### 6. Audit cost realism and reward semantics
Verify whether:
- transaction costs are applied in execution, reward, or both
- slippage and spread are separated correctly from commissions or fees
- turnover penalties reflect actual exposure change
- reward/cost flags are wired end to end

If a flag exists but is not functionally used, classify it as a correctness bug.

### 7. Audit temporal realism and leakage risk
Verify:
- decision timestamp vs fill timestamp
- reward attribution timing
- absence of same-bar look-ahead
- whether next-available fill behavior is truly implemented
- whether overnight gap or delayed fill behavior is being ignored where relevant

### 8. Rank the realism issues
Rank findings by:
- expected impact on apparent edge
- expected impact on learned policy behavior
- implementation complexity
- comparability disruption

### 9. Produce a minimal patch sequence
Provide:
- small, testable changes
- exact code targets
- migration toggles or feature flags when needed
- regression-awareness notes

## Decision Logic

- If same-bar execution is present: next-bar execution is the first priority.
- If `next_bar` exists but the price path remains favorable: verify exact fill semantics before assuming the issue is solved.
- If a synthetic basket is treated as directly tradable: classify as material modeling risk.
- If turnover is driven by weight oscillation: recommend limits tied to actual exposure change.
- If share conversion creates threshold artifacts: recommend residual-cash, min-notional, or hysteresis handling.
- If shorting lacks borrow or financing assumptions: classify as incomplete realism.
- If a cost flag is exposed but inactive: classify as correctness bug, not enhancement.
- If the fix changes semantics enough to break leaderboard continuity: require a feature flag or versioning note.

## Required Output Format

Always return sections in this exact order:

1. **Current realism profile**
2. **Unrealistic assumptions found**
3. **Why each issue matters for learned policy behavior**
4. **Recommended fixes ordered by impact**
5. **Minimal patch plan**
6. **Advanced realism roadmap**
7. **Regression risks introduced by changes**
8. **Next proposed experiments or runs (if requested or justified)**
9. **Leaderboard comparability impact (REQUIRED)**
10. **Pipeline Decision**

## Output Requirements

### Current realism profile
Summarize how execution, sizing, timing, and costs currently behave.

### Unrealistic assumptions found
Only include assumptions supported by code or experiment evidence.

### Why each issue matters for learned policy behavior
Explain how the policy could learn the wrong habit because of the assumption.

### Recommended fixes ordered by impact
Order from highest realism gain to lowest.
Prefer small, meaningful fixes before ambitious redesigns.

### Minimal patch plan
Provide a short, safe sequence of implementation changes.

### Advanced realism roadmap
Include only non-essential upgrades that go beyond the minimal correctness path.

### Regression risks introduced by changes
Explain what could break:
- analytics semantics
- leaderboard comparisons
- config behavior
- prior assumptions

### Next proposed experiments or runs
Only include when justified.
For each run include:
- environment activation command
- runner command
- full relative script path when not in repo root
- key args
- expected output artifact path(s)

### Leaderboard comparability impact (REQUIRED)
Include:
- impact level: Low / Medium / High
- whether semantics changed
- whether historical leaderboard rows remain comparable
- whether versioning or feature flags are needed
- whether conclusions are exploratory or confirmatory

## Recommended Fix Patterns
Use when appropriate:
- next-bar execution
- spread-aware fill prices
- slippage model
- max absolute weight delta per step
- turnover penalties tied to executed notional or exposure change
- hysteresis or min-notional thresholds
- short borrow fee and short constraints
- cooldown or minimum hold period
- volatility-targeted sizing
- execution feature flags for comparability protection

## Constraints
- Do not introduce look-ahead bias
- Do not silently change analytics semantics
- Keep compatibility with analytics and experiment code unless explicitly changing semantics
- Prefer small, testable refactors over rewrites
- Be explicit when comparability changes
- Treat inactive config flags as correctness issues
- Do not omit comparability impact

## Quality Checks Before Finalizing
- every finding maps to code or observed behavior
- every recommendation includes impact rationale
- comparability impact is explicit
- semantic changes include migration or compatibility notes
- correctness bugs are separated from enhancements
- evidence is separated from assumptions
- output order is followed exactly
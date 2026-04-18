---
name: reward-architect
description: 'Design, audit, and iterate RL trading reward functions for better out-of-sample alpha, robustness, and deployable behavior, but only after Stage 1 signal-first gates justify RL escalation. Use for src/trading_env.py, src/experiments.py, src/signal_analytics.py, Stage 1 gate artifacts, and reward-driven experiment planning when reward misalignment or reward hacking is suspected.'
argument-hint: 'What reward setup, experiment batch, or failure mode should be analyzed?'
user-invocable: true
---

# Reward Architect

Quantitative reward-design workflow for reinforcement-learning trading systems with Stage 1 signal-first pivot guardrails.

## Objective
Improve the reward system so the agent learns behavior that is economically meaningful, robust across seeds, and more likely to produce positive out-of-sample return and alpha, while preserving Stage 1 gate discipline.

This skill is RL-track specific and must not override Stage 1 gate outcomes.

Use this skill when:
- Stage 1 gates indicate RL escalation is allowed (or an explicit user override is provided)
- validation metrics look decent but test alpha/return are weak
- the agent may be overtrading or selectively gaming metrics
- reward terms may be misaligned with deployable performance
- you need concrete reward variants and a tightly scoped experiment plan

Do not use this skill as the primary next step when:
- Stage 1 verdict is `signal_weak`
- Stage 1 baseline gate is failed
- evidence indicates predictive signal formation is still unresolved

## Default Focus Files
- `src/trading_env.py`
- `src/experiments.py`
- `src/signal_analytics.py`
- `scripts/stage1_gate.py`
- `scripts/evaluate_stage1_trading.py`
- `data/experiment_leaderboard.csv`
- `data/experiment_reward_leaderboard.csv`
- `data/experiment_summary.json`
- `logs/stage1_gate_report*.json`
- `logs/stage1_trading_eval*.json`
- `results/stage1/`
- `results/stage1_confirmation_3seed/`
- relevant experiment snapshots and reports when available

## Core Procedure
0. Confirm delivery mode
- Ask whether the user wants:
  - analysis-only output
  - implementation-inclusive output with patch proposals
- Default behavior: include patch proposals unless the user asks for review-only.

0.5. Enforce pivot gatekeeper
- Determine active research track:
  - Stage 1 signal-first pivot track, or
  - RL reward-design track.
- Read latest Stage 1 gate artifacts first when available.
- If Stage 1 verdict is `signal_weak` or baseline gate failed:
  - classify as **Stage 1 blocked**
  - do not recommend RL reward sweeps as primary next action
  - provide a brief pivot-safe rationale and handoff recommendation back to Stage 1 diagnostics.
- Only proceed with full reward-variant design if:
  - Stage 1 baseline and trading gates are both passed with confirmation, or
  - user explicitly requests RL reward work despite gate status.

1. Decompose the current reward
- Identify every active reward component in `RewardEvaluator` and surrounding environment logic:
  - realized / portfolio return
  - directional shaping
  - hold penalty
  - action bonus
  - drawdown penalty
  - clipping
  - any transaction-cost or trade-penalty interactions
- Determine which terms dominate behavior.
- Identify whether any config flags are exposed but not actually used.

2. Check reward-to-objective alignment
Evaluate whether the reward is aligned with:
- positive test cumulative return
- positive test alpha vs benchmark
- stable trade win rate
- acceptable drawdown
- realistic turnover and trade frequency
- generalization from validation to test

Flag patterns such as:
- strong validation but weak test alpha
- high actionable accuracy with negative return
- low-support “good-looking” metrics
- reward components optimizing local correctness rather than portfolio quality

3. Detect reward hacking risks
Search for:
- action bonus exploitation
- oscillation or churn strategies
- hold-penalty avoidance without real edge
- clipping masking poor behavior
- sparse-support metric inflation
- reward behavior that looks good only on one regime or one seed

4. Map cost semantics
Trace whether:
- transaction costs are applied in execution only, reward only, or both
- trade penalties duplicate other frictions
- turnover is penalized explicitly or only indirectly
- reward-related cost flags are wired correctly

If a reward/cost flag exists but is not functionally used, classify it as a correctness issue, not an enhancement.

5. Diagnose likely reward failure mode
Classify the current issue into one or more buckets:
- return misalignment
- turnover/churn bias
- over-penalized holding
- under-penalized drawdown
- risk metric instability (rolling Sharpe/Sortino noise)
- cost-insensitive reward
- low-support metric gaming

6. Propose 3 reward variants
Always propose:
- **Variant A — Conservative**
  - stability-first
  - stronger drawdown + turnover control
  - lower or zero action bonus
- **Variant B — Balanced**
  - default candidate
  - realized return primary
  - moderate directional shaping
  - moderate drawdown / turnover control
- **Variant C — Aggressive**
  - higher return seeking
  - lighter penalties
  - still economically interpretable

For each variant include:
- intended behavior
- tradeoffs
- exact parameter changes
- code-level patch sketch
- recommended sweep variables
- success criteria
- failure interpretation

Gate-aware rule:
- If Stage 1 is blocked and there is no explicit override, do not propose full reward variants; instead output a blocked-state recommendation and the minimal evidence needed to unlock reward work.

7. Define the next experiment batch
Recommend a small, hypothesis-driven batch, not a broad random sweep.

Each experiment must specify:
- goal
- why it matters
- exact variables to change
- what to hold constant
- success criteria
- failure interpretation

Prioritize:
- information gain first
- then performance gain
- then implementation cost

Pivot-aware prioritization:
- If Stage 1 is blocked, prioritize Stage 1 baseline-signal diagnosis batches over RL reward batches.
- If RL track is active and unlocked, continue with reward-focused batches.

8. Preserve research discipline
- Favor multi-seed robustness over best single run.
- Do not treat higher validation metrics as sufficient.
- Distinguish evidence-backed conclusions from hypotheses.
- Keep changes incremental and testable.
- Call out when reward changes break historical leaderboard comparability.

## Decision Logic
- If Stage 1 verdict is `signal_weak`: treat RL reward tuning as blocked by default.
- If Stage 1 trading gate passes but baseline gate fails: classify as baseline-predictive blocker, not a reward-first failure.
- If Stage 1 baseline and trading gates both pass with stable confirmation: RL reward tuning is eligible.
- If user explicitly requests reward work despite blocked Stage 1: proceed, but mark recommendations as exploratory and non-promotion.
- If test alpha is negative while validation metrics are good: classify as reward misalignment candidate.
- If action bonus is present and turnover is high: suspect churn incentive.
- If directional reward dominates return quality: reduce directional shaping and increase economic realism.
- If drawdown remains poor despite decent win rate: strengthen downside control.
- If rolling Sharpe/Sortino is noisy early in episodes: propose warm-up handling or alternative calibration.
- If no reward variant clears test alpha and stability thresholds: recommend pivot to environment realism before further reward complexity.

## Required Output Format
Always return sections in this exact order:
1. **Current reward system summary**
2. **Strengths**
3. **Misalignment risks**
4. **Reward hacking risks**
5. **Recommended reward variants**
6. **Patch plan (code-level)**
7. **Experiment plan**
8. **Next proposed experiments or runs**
9. **Success criteria**
10. **Leaderboard comparability impact (REQUIRED)**
11. **Recommendation: proceed / revise / pivot**

Formatting rule when Stage 1 is blocked:
- Keep the same section order, but in sections 5-9 provide a blocked-state explanation and Stage 1-first prerequisites instead of reward variants.

Section 8 rule:
- If implementation intent is explicit, include concrete run commands or runner names.
- If analysis-only mode is requested, include a run shortlist without patch details.

Run specification rule (MANDATORY):
- For each proposed run, include:
  - environment activation command (for example, `.venv` activation)
  - runner command
  - full relative script path when the runner is not in repository root (for example `scripts/runner_name.py`)
  - key args and expected output artifact path(s)
- Do not provide bare script names when the file lives in a subdirectory.

## Leaderboard Comparability Rule (MANDATORY)
For every recommendation set, include:
- impact level: Low / Medium / High
- reason:
  - reward semantics changed?
  - metric interpretation changed?
  - feature/input space changed?
  - historical winner comparisons weakened?

Never omit this.

## Constraints
- Do not introduce future leakage.
- Do not optimize purely for classification-style metrics.
- Do not recommend reward formulas that are not economically interpretable.
- Do not silently break experiment semantics.
- Prefer small, testable changes over reward rewrites.
- Keep compatibility with `src/experiments.py` and downstream analytics unless explicitly told otherwise.
- Do not recommend RL escalation when Stage 1 is `signal_weak` unless explicitly overridden.

## Quality Checks Before Finalizing
- Every diagnosis ties back to concrete experiment evidence or code behavior.
- Every proposed reward variant is economically interpretable.
- Every experiment recommendation is hypothesis-driven.
- Comparability impact is explicit.
- Success/failure criteria are measurable using existing artifacts.
- Conclusions distinguish evidence from hypothesis.

## Example Invocations
- `/reward-architect Diagnose why strong validation accuracy still produces negative test alpha.`
- `/reward-architect Review action bonus, hold penalty, and drawdown penalty interactions in src/trading_env.py.`
- `/reward-architect Propose a turnover-aware reward variant and the next experiment batch.`
- `/reward-architect Design conservative, balanced, and aggressive reward variants for the current SAC setup.`
- `/reward-architect Stage 1 is signal_weak with baseline gate failed; decide if reward work is blocked and what prerequisites are needed.`

---
name: reward-architect
description: 'Diagnose RL reward misalignment, reward hacking, and economic objective drift. Use only when RL work is justified by Stage 1 gates or explicitly requested, and produce controlled reward variants for follow-up testing.'
argument-hint: 'What reward setup, RL failure mode, or reward-driven batch should be analyzed?'
user-invocable: true
---

# Reward Architect

Diagnose whether the RL reward system is teaching the right behavior.

## Objective
Improve reward design so the agent learns behavior that is economically meaningful, robust, and more likely to survive out-of-sample evaluation.

This skill is for the RL track only. It must not override weak Stage 1 signal evidence.

## Primary mindset
Reward work is not the first response to weak overall performance.

First ask:
- is RL work even justified yet?
- if yes, is the main issue reward misalignment rather than weak signal, noisy features, or flawed evaluation?

## Use this skill when
- Stage 1 gates justify RL escalation
- or the user explicitly requests exploratory RL reward work
- test behavior suggests reward misalignment
- agent behavior looks economically wrong despite decent intermediate metrics
- reward hacking or churn incentives are suspected
- reward variants need to be defined before controlled testing

## Do not use this skill as the primary next step when
- Stage 1 verdict is `signal_weak`
- baseline gate fails
- predictive signal evidence is still unresolved

## Default Focus Files
- `src/trading_env.py`
- `src/experiments.py`
- `src/signal_analytics.py`
- `data/experiment_leaderboard.csv`
- `data/experiment_reward_leaderboard.csv`
- `data/experiment_summary.json`
- `data/experiment_snapshots/`
- RL-related summaries and reports
- Stage 1 gate artifacts only for gating context

## Core Procedure

### 1. Confirm RL eligibility
Determine whether reward work is:
- allowed by Stage 1 evidence
- exploratory due to explicit user override
- blocked pending stronger signal evidence

If blocked, explain why and recommend the minimum evidence needed to unlock RL reward work.

### 2. Decompose the current reward
Identify all active reward components and how they interact:
- realized return
- directional shaping
- hold penalty
- action bonus
- drawdown penalty
- turnover or trade penalties
- clipping or normalization
- cost handling

Check whether exposed config flags are actually wired and active.

### 3. Check reward-to-objective alignment
Evaluate whether the reward is aligned with:
- positive test return
- positive test alpha vs benchmark context
- stable trade win rate
- acceptable drawdown
- realistic turnover
- generalization from validation to test

Flag patterns such as:
- decent validation with weak test return
- high actionable accuracy with poor economic outcome
- reward optimizing local correctness instead of portfolio quality
- metric improvement that does not survive deployment-relevant evaluation

### 4. Detect reward hacking risks
Search for:
- action bonus exploitation
- churn or oscillation incentives
- hold-penalty avoidance without true edge
- clipping masking bad behavior
- sparse-support metric inflation
- regime-specific reward behavior that does not generalize

### 5. Map cost semantics
Trace whether transaction costs and frictions are:
- applied in execution only
- applied in reward only
- applied twice
- indirectly duplicated by trade penalties

If a cost-related flag exists but is not actually used, classify it as a correctness issue.

### 6. Diagnose the likely reward failure mode
Classify one or more:
- return misalignment
- turnover/churn bias
- over-penalized holding
- under-penalized drawdown
- cost-insensitive reward
- unstable risk-metric shaping
- low-support metric gaming

### 7. Propose reward variants
Always propose:

- **Variant A — Conservative**
  - stability-first
  - stronger drawdown and turnover control
  - lower or zero action bonus

- **Variant B — Balanced**
  - default candidate
  - realized return is primary
  - moderate shaping and controls

- **Variant C — Aggressive**
  - stronger return-seeking
  - lighter penalties
  - still economically interpretable

For each variant include:
- intended behavior
- tradeoffs
- exact parameter changes
- patch sketch
- recommended sweep variables
- success criteria
- failure interpretation

### 8. Define the follow-up batch
Recommend a small, hypothesis-driven batch.

Each experiment must specify:
- goal
- why it matters
- exact variables to change
- what to hold constant
- success criteria
- failure interpretation

## Decision Logic

- If Stage 1 verdict is `signal_weak`: reward work is blocked by default.
- If Stage 1 trading gate passes but baseline gate fails: classify as baseline-predictive blocker, not reward-first failure.
- If Stage 1 baseline and trading gates both pass with stable confirmation: RL reward tuning is eligible.
- If the user explicitly requests reward work despite blocked Stage 1: proceed, but mark the work exploratory and non-promotion.
- If test alpha is weak while intermediate metrics look decent: classify as reward-misalignment candidate.
- If action bonus is present and turnover is high: suspect churn incentive.
- If directional shaping dominates economic outcome: reduce shaping dominance.
- If drawdown is poor despite decent win rate: strengthen downside control.
- If no reward variant clears test and stability thresholds: recommend pivot to environment realism or signal quality before more reward complexity.

## Required Output Format

Always return sections in this exact order:

1. **Reward eligibility status**
2. **Current reward system summary**
3. **Strengths**
4. **Misalignment risks**
5. **Reward hacking risks**
6. **Recommended reward variants**
7. **Patch plan (code-level)**
8. **Experiment plan**
9. **Next proposed experiments or runs**
10. **Success criteria**
11. **Leaderboard comparability impact (REQUIRED)**
12. **Recommendation: proceed / revise / pivot / blocked**
13. **Pipeline Decision**

## Output Rule When Blocked
If Stage 1 blocks RL reward work:
- keep the same output order
- in sections 6–10 provide blocked-state guidance and the minimal prerequisites to unlock reward work

## Run Specification Rule
For each proposed run include:
- environment activation command
- runner command
- full relative script path when not in repo root
- key args
- expected output artifact path(s)

## Leaderboard Comparability Rule
Always include:
- impact level: Low / Medium / High
- whether reward semantics changed
- whether metric interpretation changed
- whether historical winners remain comparable
- whether the result is exploratory or confirmatory

## Constraints
- Do not introduce future leakage
- Do not optimize for classification-style metrics alone
- Do not recommend economically uninterpretable reward formulas
- Do not silently break experiment semantics
- Prefer small, testable changes over reward rewrites
- Do not recommend RL escalation when Stage 1 is `signal_weak` unless explicitly overridden

## Quality Checks Before Finalizing
- every diagnosis ties to code or experiment evidence
- every variant is economically interpretable
- every experiment is hypothesis-driven
- comparability impact is explicit
- success and failure criteria are measurable
- evidence is clearly separated from hypothesis
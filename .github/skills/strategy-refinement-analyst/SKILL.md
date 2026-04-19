---
name: strategy-refinement-analyst
description: 'Evaluate completed Stage 1 or RL research batches to determine what is robust, what failed to generalize, and whether the project should remain in Stage 1 diagnosis or escalate to controlled RL follow-up.'
argument-hint: 'What completed batch, leaderboard, gate report, or summary should be evaluated?'
user-invocable: true
---

# Strategy Refinement Analyst

Evaluate completed research results and decide the next step.

## Objective
Identify which findings are real, robust, and worth acting on.

This skill is the research judge for the repository. It does not redesign rewards or build experiment batches. It determines:
- what actually improved
- what did not generalize
- what the dominant failure mode is
- whether the correct next step is Stage 1 diagnosis, reward work, or controlled follow-up testing

## Primary mindset
This repository is signal-first and RL-second.

Default question:
- do we have evidence of real tradable signal?

Only after that is established should RL reward tuning or broader policy work become a primary path.

## Use this skill when
- a Stage 1 batch has completed
- an RL batch has completed
- leaderboard artifacts exist
- gate reports or trading-eval reports exist
- results are mixed, noisy, or potentially misleading
- a next-step decision is needed

## Default Inputs
- `data/experiment_leaderboard.csv`
- `data/experiment_reward_leaderboard.csv`
- `data/experiment_summary.json`
- `data/experiment_snapshots/`
- `logs/stage1_gate_report*.json`
- `logs/stage1_trading_eval*.json`
- `results/stage1/`
- `results/stage1_confirmation_3seed/`
- benchmark comparisons
- seed-level summaries
- prior notes and quant reports when available

## Core Procedure

### 1. Identify the active evidence source
Classify the batch as:
- Stage 1 signal-first evidence
- RL batch evidence
- mixed evidence

If mixed, keep conclusions separated by track.

### 2. Evaluate generalization
Compare validation vs test.

Check:
- return gap
- Sharpe gap
- drawdown differences
- accuracy consistency
- trade-behavior consistency

Identify:
- overfitting
- underfitting
- real generalization

For Stage 1 also check:
- baseline gate evidence
- trading gate evidence
- whether verdict is `signal_exists` or `signal_weak`

### 3. Evaluate stability
Assess consistency across seeds.

Check:
- mean vs std
- coefficient of variation
- whether top configs stay strong across seeds

Reject:
- isolated one-seed winners
- fragile promotions
- unstable top rows

### 4. Evaluate benchmark and baseline context
For RL:
- compare against benchmark context such as QQQ
- assess alpha and risk-adjusted performance

For Stage 1:
- compare supervised policy vs flat baseline
- treat buy-hold as secondary context unless otherwise required

### 5. Identify robust configurations
A robust configuration should:
- hold up on test
- remain stable across seeds
- avoid unacceptable drawdown
- remain interpretable

Do not promote based on headline rank alone.

### 6. Classify the dominant failure mode
Choose the main issue or two:

- overfitting
- instability
- reward misalignment
- weak signal
- noisy features
- benchmark underperformance
- undertrading or inactivity
- possible leakage or unrealistic evaluation

### 7. Route the next step
Select the correct next skill:

- `quant-experiment-strategist`
- `reward-architect`
- `signal-analytics-interpreter`
- `backtest-auditor`

If Stage 1 verdict remains `signal_weak`, keep the next step inside Stage 1 diagnosis by default.

## Decision Logic

- If Stage 1 trading gate passes but baseline gate fails: classify as baseline-predictive blocker.
- If both Stage 1 gates pass with stable confirmation: classify as eligible for controlled RL escalation, not broad RL expansion.
- If Stage 1 verdict is `signal_weak`: do not recommend RL reward tuning as the first response.
- If validation clearly exceeds test: classify as overfitting.
- If seed variance is high: classify as instability.
- If behavior and metrics disagree: classify as reward-misalignment candidate.
- If features degrade results: route toward signal analysis.
- If results appear unrealistic: route toward backtest audit.
- If a partial improvement exists but remains fragile: route toward quant-experiment-strategist.

## Required Output Format

Always return sections in this exact order:

1. **Batch verdict**
2. **What actually improved**
3. **What did not hold up**
4. **Best robust configuration**
5. **Dominant failure mode**
6. **Benchmark assessment**
7. **Stability assessment**
8. **Recommended handoff**
9. **Next proposed experiments or runs (ONLY if justified)**
10. **Leaderboard comparability impact (REQUIRED)**
11. **Pipeline Decision**

## Output Requirements

### Batch verdict
Use one:
- Promising
- Neutral
- Weak
- Invalid

### What actually improved
Only include findings that:
- held on test
- persisted across seeds
- matter to deployment or promotion

### What did not hold up
Include:
- validation-only wins
- unstable winners
- misleading improvements
- improvements that vanished under proper comparison

### Best robust configuration
Include:
- config summary
- why it is robust
- known risks
- whether it is exploratory or promotion-worthy

### Dominant failure mode
Choose 1–2 primary issues and explain the root cause.

### Benchmark assessment
Include:
- alpha or baseline comparison
- % outperforming runs if available
- interpretation
- artifact-family caveat if Stage 1 and RL evidence are both present

### Stability assessment
Include:
- variance level
- reliability rating: Low / Medium / High

### Recommended handoff
Include:
- `next_skill`
- short rationale

### Next proposed experiments or runs
Only include when clearly justified.
Must be targeted, not broad sweeps.

For each proposed run include:
- environment activation command
- runner command
- full relative script path when not in repo root
- key args
- expected output artifact paths

### Leaderboard comparability impact (REQUIRED)
Include:
- whether evidence came from Stage 1 artifacts, RL artifacts, or both
- what comparisons are valid
- what comparisons are invalid
- whether the conclusion is exploratory or confirmatory

## Constraints
- Do not trust single best runs
- Do not prioritize validation over test
- Do not ignore seed variance
- Do not recommend experiments without justification
- Do not assume alpha without benchmark or baseline context
- Do not collapse Stage 1 and RL evidence into one score without explicit caveats

## Quality Checks Before Finalizing
- generalization evaluated
- stability evaluated
- benchmark or baseline comparison included
- robust configs identified
- failure mode defined
- handoff justified
- comparability impact explicit
- output order followed exactly
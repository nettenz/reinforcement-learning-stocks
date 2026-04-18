---
name: strategy-refinement-analyst
description: 'Analyze completed trading research batches across RL and Stage 1 signal-first pivot workflows to determine which results are robust, generalizable, and statistically valid. Use for stage1 gate/trading artifacts, experiment leaderboards, summaries, and quant reports to filter out overfitting, instability, and noise, and to recommend the next research or system step.'
argument-hint: 'What experiment batch results or report should be analyzed for refinement?'
user-invocable: true
---

# Strategy Refinement Analyst

Research-decision workflow for RL and Stage 1 signal-first trading strategy development.

## Objective
Identify **real, robust improvements** from experiment batches and determine the correct next step in the research pipeline.

This skill ensures:
- overfitting is detected and rejected
- unstable or luck-driven results are filtered out
- only generalizable configurations are promoted
- the correct next skill is selected

This skill is focused on **decision-making and validation of results**, not generating experiments or modifying code.

---

## Use This Skill When
- experiment batches have been completed
- stage1 gate and trading-eval artifacts have been generated
- leaderboard CSVs and summaries exist
- quant reports have been generated
- results are mixed, unclear, or conflicting
- you need to determine the next step in development

---

## Default Inputs
- experiment artifacts:
  - `data/experiment_leaderboard.csv`
  - `data/experiment_reward_leaderboard.csv`
  - `data/experiment_summary.json`
  - `data/experiment_snapshots/`
- stage1 pivot artifacts:
  - `logs/stage1_gate_report*.json`
  - `logs/stage1_trading_eval*.json`
  - `results/stage1/`
  - `results/stage1_confirmation_3seed/`
- quant analysis reports (markdown/logs)
- cross-seed metrics
- benchmark comparisons (e.g., vs QQQ)
- prior experiment notes

---

## Core Procedure

0. Confirm scope
- Ask whether the goal is:
  - full batch evaluation
  - comparison of specific configs
  - validation of a suspected improvement
  - recommendation of next step

Default: full batch evaluation.

---

1. Evaluate generalization
Compare validation vs test performance.

Check:
- return gap
- Sharpe gap
- drawdown differences
- accuracy consistency

Identify:
- overfitting (validation >> test)
- underfitting (both weak)
- genuine generalization (both strong)

For Stage 1 pivot outputs, also check:
- baseline gate evidence (val/test r2 by ticker)
- trading gate evidence (supervised vs flat, and optionally buy-hold)
- whether verdict is `signal_exists` or `signal_weak`

---

2. Evaluate cross-seed stability
Analyze variance across seeds.

Check:
- mean vs std
- coefficient of variation (CV)
- consistency of top configs

Identify:
- unstable configs (high variance)
- robust configs (consistent performance)

Reject:
- single-seed winners
- high variance configurations

---

3. Evaluate benchmark performance
Compare against benchmark such as :contentReference[oaicite:0]{index=0}

Check:
- alpha vs benchmark
- % runs outperforming
- risk-adjusted comparison

Identify:
- true alpha generation
- hidden beta exposure
- benchmark underperformance

For Stage 1 pivot mode, use the correct benchmark context:
- primary baseline benchmark: flat policy (required)
- secondary context benchmark: buy-hold (informational)

---

4. Identify robust configurations
Select configs that:
- perform well on test
- are stable across seeds
- maintain acceptable drawdown

Avoid:
- peak ranking score only
- validation-only improvements

---

5. Detect dominant failure mode
Classify primary issues:

- overfitting
- instability (high variance)
- reward misalignment
- feature noise (e.g., news degradation)
- undertrading / inactivity
- lack of alpha vs benchmark

Explain the cause clearly.

---

6. Validate signal integrity
Check whether improvements are driven by:

- meaningful signals
- noise or overfitting
- degraded feature contributions (e.g., news hurting performance)

---

7. Determine next step
Based on findings, select the correct handoff:

- `quant-experiment-strategist`
- `reward-architect`
- `signal-analytics-interpreter`
- `backtest-auditor`

Do NOT default to more experiments without justification.

If Stage 1 gate remains `signal_weak`, default next step should stay inside Stage 1 diagnosis instead of RL expansion.

---

## Decision Logic

- If Stage 1 trading gate passes but baseline gate fails: classify as baseline-predictive blocker; continue Stage 1 refinement.
- If both Stage 1 gates pass with stable confirmation: classify as ready for controlled progression to RL simplification, not broad RL sweeps.
- If Stage 1 verdict is `signal_weak`: do not recommend RL reward tuning as first response.

- If validation >> test → overfitting → reduce complexity or increase regularization
- If high variance across seeds → instability → prefer entropy or exploration tuning
- If performance < benchmark → no alpha → reconsider reward or signals
- If signals degrade performance → feature noise → handoff to signal analysis
- If trade behavior contradicts metrics → reward misalignment → handoff to reward-architect
- If results seem unrealistic → possible leakage → handoff to backtest-auditor
- If some improvement exists but not stable → refine via quant-experiment-strategist

---

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
9. **Next experiments (ONLY if justified)**
10. **Leaderboard comparability impact (REQUIRED)**

---

## Output Section Requirements

### Batch verdict
- Promising / Neutral / Weak / Invalid

---

### What actually improved
- Only include improvements that:
  - held on test
  - persisted across seeds

---

### What did not hold up
- validation-only wins
- unstable configs
- misleading improvements

---

### Best robust configuration
Include:
- config summary
- why it is robust
- known risks

---

### Dominant failure mode
- choose 1–2 primary issues
- explain root cause

---

### Benchmark assessment
Include:
- alpha vs benchmark
- % outperforming runs
- interpretation
- for Stage 1 pivot: supervised vs flat (required) and supervised vs buy-hold (secondary)

---

### Stability assessment
Include:
- variance level
- reliability rating (Low / Medium / High)

---

### Recommended handoff
Include:
- next_skill
- rationale

---

### Next experiments
- ONLY include if clearly justified
- must be targeted, not broad sweeps

---

### Leaderboard comparability impact (REQUIRED)
Include:
- whether evidence came from Stage 1 gate artifacts, RL leaderboards, or both
- what comparisons are valid vs invalid across those artifact families
- whether conclusions are exploratory or confirmatory

---

## Handoff Rules

### → quant-experiment-strategist
- partial improvement exists
- needs refinement or tuning

---

### → reward-architect
- behavior does not match performance
- reward incentives are misaligned

---

### → signal-analytics-interpreter
- signals are noisy or degrading performance
- feature engineering is suspect

---

### → backtest-auditor
- results appear unrealistic
- suspected leakage or flawed assumptions

---

## Constraints
- Do not trust single best runs
- Do not prioritize validation over test
- Do not ignore seed variance
- Do not recommend experiments without justification
- Do not assume alpha without benchmark comparison
- Do not collapse Stage 1 gate outcomes and RL leaderboard rankings into one unified score without explicit caveats

---

## Quality Checks Before Finalizing
- Generalization (val vs test) evaluated
- Cross-seed stability assessed
- Benchmark comparison included
- Robust configs identified (not just top score)
- Failure mode clearly defined
- Handoff decision justified
- Leaderboard comparability impact explicitly stated
- Output follows required format exactly

---

## Example Invocations
- `/strategy-refinement-analyst Analyze latest experiment leaderboard and identify robust configs.`
- `/strategy-refinement-analyst Compare entropy sweep results and determine if overfitting improved.`
- `/strategy-refinement-analyst Evaluate whether news features improve or degrade performance.`
- `/strategy-refinement-analyst Determine next step after current experiment batch.`
# Trading Research Pipeline

## Core Principle

This repository follows a **signal-first, RL-second** workflow.

The default research order is:

1. prove predictive signal exists
2. prove the signal survives simple trading evaluation
3. confirm the evidence is stable on test data and across seeds
4. only then consider RL reward or policy refinement

RL is not the default path.  
RL is an escalation path.

If Stage 1 evidence is weak, the correct next step is usually better diagnosis of signal quality, feature quality, or evaluation design — not more RL tuning.

---

## Core Skills

### strategy-refinement-analyst
**Role:** Judge completed research batches and route the next step.

Owns:
- result interpretation
- robustness checks
- benchmark and baseline comparison
- failure-mode classification
- next-skill selection

Does not own:
- reward redesign
- experiment batch design

---

### reward-architect
**Role:** Diagnose RL reward misalignment and design reward variants.

Owns:
- reward decomposition
- reward-hacking detection
- economic objective alignment
- conservative / balanced / aggressive reward proposals

Does not own:
- batch execution
- final robustness judgment

---

### quant-experiment-strategist
**Role:** Turn a validated research question into a controlled experiment batch.

Owns:
- experiment design
- variable isolation
- controls
- success criteria
- failure interpretation
- run structure

Does not own:
- final batch judgment
- reward theory redesign

---

## Research Tracks

### Stage 1: Signal-first track
Use when:
- predictive signal is still unproven
- baseline gate fails
- trading gate fails
- Stage 1 confirmation is incomplete
- Stage 1 verdict is `signal_weak`

Primary goal:
- determine whether there is real tradable signal before RL escalation

### RL track
Use only when:
- Stage 1 baseline gate passes
- Stage 1 trading gate passes
- confirmation is strong enough to justify escalation
- or the user explicitly requests exploratory RL work

Primary goal:
- determine whether RL improves behavior beyond simpler baselines

---

## Main Loop

completed batch  
↓  
strategy-refinement-analyst  
↓  

if Stage 1 evidence is weak:
→ remain in Stage 1 diagnosis

if RL is justified and reward misalignment is the dominant issue:
→ reward-architect
→ quant-experiment-strategist

if reward variants already exist:
→ quant-experiment-strategist

if controlled follow-up testing is needed:
→ quant-experiment-strategist

↓  
run experiments  
↓  
strategy-refinement-analyst  
↓  
repeat

---

## Routing Rules

### Always route to strategy-refinement-analyst after a batch
Every completed batch returns here first.

### Route to reward-architect only when
- RL track is active or explicitly overridden
- reward misalignment is the dominant issue
- reward variants have not already been clearly defined

### Route to quant-experiment-strategist when
- the next step is a controlled follow-up batch
- reward variants already exist and need testing
- refinement has already identified the question to test

---

## Blocking Rules

RL reward work is blocked by default when:
- Stage 1 verdict is `signal_weak`
- baseline gate fails
- predictive evidence is not yet convincing

When blocked:
- do not recommend broad RL tuning as the primary path
- return to Stage 1 diagnosis or signal analysis instead

---

## Research Rules

1. Do not trust single runs
2. Prefer test evidence over validation-only wins
3. Prefer multi-seed stability over peak metrics
4. Keep diagnosis, design, and planning separate
5. Prefer small controlled batches over broad sweeps
6. Always compare against simple baselines and benchmark context
7. After every batch, return to strategy-refinement-analyst

---

## Required Handoff Block

Every skill should end with:

## Pipeline Decision

- status: complete / ready_for_execution / revise / pivot / blocked
- next_skill: strategy-refinement-analyst / reward-architect / quant-experiment-strategist / none
- handoff_reason: short explanation
- required_artifacts:
  - artifact 1
  - artifact 2
- comparability_note: Low / Medium / High + reason

---

## Mental Model

- strategy-refinement-analyst = judge
- reward-architect = reward designer
- quant-experiment-strategist = experiment planner

Stage 1 proves signal.  
RL is allowed only after that evidence is strong enough.
# RL Trading Research Pipeline

## Scope
This pipeline defines the primary research loop for:
- strategy-refinement-analyst
- reward-architect
- quant-experiment-strategist

The goal is to:
- enforce clean separation of responsibilities
- prevent duplicated work across skills
- ensure hypothesis-driven iteration
- maintain statistical discipline

---

## Skill Roles

### strategy-refinement-analyst
**Role:** Research judge and router

Responsibilities:
- evaluate completed experiment batches
- detect overfitting and instability
- identify robust improvements
- classify dominant failure mode
- select next skill

Does NOT:
- build experiment grids
- redesign reward systems

---

### reward-architect
**Role:** Objective designer

Responsibilities:
- diagnose reward misalignment
- detect reward hacking
- design reward variants (A/B/C)
- define reward experiment intent

Does NOT:
- execute experiments
- validate robustness across seeds

---

### quant-experiment-strategist
**Role:** Experiment planner

Responsibilities:
- convert hypotheses into controlled experiment batches
- define:
  - variables to change
  - variables to hold constant
  - seeds and configs
  - success criteria
  - failure interpretation

Does NOT:
- redesign reward theory
- evaluate robustness

---

## Primary Pipeline

completed experiment batch  
↓  
strategy-refinement-analyst  
↓  
[branch decision]

- reward misalignment (no variants defined)  
  → reward-architect → quant-experiment-strategist  

- reward misalignment (variants already defined)  
  → quant-experiment-strategist  

- general tuning needed  
  → quant-experiment-strategist  

---

After execution:

new experiment artifacts  
↓  
strategy-refinement-analyst  

---

## Artifact Triggers

### strategy-refinement-analyst
Run when:
- experiment batch completed

Requires:
- data/experiment_leaderboard.csv
- data/experiment_summary.json

---

### reward-architect
Run when:
- reward misalignment detected
- reward variants NOT defined

---

### quant-experiment-strategist
Run when:
- next experiment batch needs to be designed
- reward variants already exist
- refinement suggests controlled test

---

## Routing Rules

### → strategy-refinement-analyst
Always after a batch finishes

---

### → reward-architect
If:
- reward misalignment exists
- reward variants NOT defined

---

### → quant-experiment-strategist
If:
- reward variants already exist
- refinement suggests next step
- tuning is needed

---

## Routing Overrides

### Skip reward-architect
If input already contains:
- explicit reward variants
- parameter values
- success criteria

→ go directly to quant-experiment-strategist

---

### Prevent role overlap

- refinement = diagnosis ONLY  
- architect = reward design ONLY  
- strategist = experiment planning ONLY  

---

### Enforce loop discipline

After EVERY run:

→ must return to strategy-refinement-analyst

---

## Exit Criteria

### strategy-refinement-analyst
Must:
- evaluate val vs test
- assess seed stability
- compare vs benchmark
- identify failure mode
- choose next skill

---

### reward-architect
Must:
- define reward system
- identify risks
- propose A/B/C variants
- define experiment intent

---

### quant-experiment-strategist
Must:
- define batch
- isolate variables
- define controls
- define success criteria

---

## Pipeline Decision Block

Each skill must end with:

## Pipeline Decision

- status: complete / ready_for_execution / revise / pivot  
- next_skill: strategy-refinement-analyst / reward-architect / quant-experiment-strategist / none  
- handoff_reason: short explanation  
- required_artifacts:
  - artifact 1
  - artifact 2
- comparability_note: Low / Medium / High + reason  

---

## Research Rules

1. Do not trust single runs  
2. Prefer multi-seed stability  
3. Prefer test over validation  
4. Separate diagnosis / design / execution  
5. Keep experiments small and controlled  
6. Always consider benchmark (QQQ)  
7. Always return to refinement after runs  

---

## Default Loop

run experiment  
↓  
strategy-refinement-analyst  

if reward issue:
  if no variants:
    → reward-architect → quant-experiment-strategist
  else:
    → quant-experiment-strategist

else:
  → quant-experiment-strategist  

↓  
run experiment  
↓  
repeat  

---

## Success Criteria

Pipeline is working if:
- skills do not overlap roles
- handoffs are consistent
- no duplicate reward design
- experiments are controlled
- improvements are based on:
  - test performance
  - multi-seed stability
  - benchmark alpha  

---

## Mental Model

strategy-refinement-analyst = judge  
reward-architect = designer  
quant-experiment-strategist = planner  

diagnose → design → test → repeat
# Stage 2 H1 Execution Checklist

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Scope: Local execution only

---

## Immediate Objective

Execute **H1: Event-Driven Prediction** under the existing Stage 2 gate contract.

H1 is the correct next experiment because H2 has been killed and the updated Stage 2 hypothesis matrix leaves H1 as the next planned hypothesis. The goal is not to rescue prior results. The goal is to test whether sparse high-information contexts contain robust edge that continuous prediction failed to capture.

---

## Step 1 — Freeze the H1 Decision Contract

Before running anything:

- treat `stage2_gate_definitions.md` as the authority for pass/fail,
- do not add ad hoc success criteria later,
- keep RL blocked unless H1 fully clears the Stage 2 contract.

### Lock These Definitions Numerically

Set and record these before the first H1 run:

- **primary decision metric**: mean net benchmark gap
- **secondary metric**: mean net Sharpe gap
- **recent-window severe failure rule**:
  - recent window benchmark gap < -5%, or
  - recent window net Sharpe < -0.25
- **default stability target**:
  - CV < 1.0
- **minimum event count per window**:
  - define before launch
- **minimum count per event type**:
  - define before launch

If event counts do not meet the minimum thresholds, the run is auto-killed.

---

## Step 2 — Lock Event Definitions

Define the first-pass H1 event tags clearly and keep them fixed for the initial run:

- earnings window
- macro event day
- volatility expansion
- abnormal volume
- sentiment shock

### Rules

- each event tag must have an explicit detection rule,
- event labels must be reproducible from data,
- event rules must not use future information,
- do not change event definitions mid-sweep.

---

## Step 3 — Confirm Sample Sufficiency

Before model training, compute and record:

- event count per window
- event count per event type
- event share of total observations
- recent-window event coverage

### Hard Rule

Kill the H1 run immediately if:

- sample size is too low for inference,
- one event type dominates nearly all observations,
- recent-window coverage is not viable.

---

## Step 4 — Run Minimum Baselines

For the first H1 pass, run:

- logistic regression
- random forest or gradient boosting
- simple threshold event-rule baseline

### Notes

- keep model complexity modest,
- avoid feature explosion,
- avoid tuning loops until the hypothesis shows basic viability.

---

## Step 5 — Apply Required Evaluation Framework

For every H1 run, report:

- rolling-window metrics
- buy-hold comparison
- event-relevant naive baseline comparison
- flat/no-trade baseline
- gross vs net results
- recent-window behavior
- stability across windows
- event-type contribution analysis

### Required Per-Window Metrics

- total return
- annualized return
- Sharpe ratio
- max drawdown
- turnover
- win rate
- benchmark return gap
- benchmark Sharpe gap
- predictive metric
- event count

---

## Step 6 — Use Hard Kill Logic

Kill an H1 variant immediately if any of these are true:

- event count is insufficient,
- performance appears in only one window,
- edge is carried by a single event cluster,
- net edge is non-positive after costs,
- recent window fails severely,
- predictive quality remains near naive.

---

## Step 7 — Record Results in One Ledger

Maintain one consolidated H1 ledger with:

- hypothesis id
- run id
- event tag set
- event detection rules
- sample counts
- cost assumptions
- window-level metrics
- aggregate metrics
- gate-by-gate pass/fail
- final verdict
- next action

Do not rely on memory or ad hoc notes.

---

## Step 8 — Make the Decision

### Continue H1 only if:

- at least 2/3 windows show positive net edge,
- predictive quality is above naive,
- edge is not carried by one event cluster,
- edge survives transaction costs,
- recent window passes,
- sample counts are sufficient.

### If H1 fails:

- stop H1,
- document the failure cleanly,
- move to H3.

### If H1 passes:

- deepen the analysis carefully,
- only then consider richer event features or expanded baselines.

---

## Final Rule

Do not treat sparse or interesting trades as success.
Only treat **gate-clearing, sample-sufficient, cross-window-consistent** results as success.

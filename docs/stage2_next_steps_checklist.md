# Stage 2 Next Steps Checklist

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Scope: Local execution only

---

## Immediate Objective

Execute **H2: Longer-Horizon Targets** under the existing Stage 2 gate contract.

H2 is the correct first experiment because it changes target design with minimal data expansion and is already the top-priority hypothesis in the Stage 2 plan.

---

## Step 1 — Freeze the Decision Contract

Before running anything:

- treat `stage2_gate_definitions.md` as the authority for pass/fail,
- do not add ad hoc success criteria later,
- keep RL blocked unless a hypothesis passes the Stage 2 contract.

### Lock These Definitions Numerically

Set and record these before the first H2 run:

- **primary decision metric**: mean net benchmark gap
- **secondary metric**: mean net Sharpe gap
- **recent-window severe failure rule**:
  - recent window benchmark gap < -5%, or
  - recent window net Sharpe < -0.25
- **default stability target**:
  - CV < 1.0

---

## Step 2 — Implement H2 Target Variants

Create and evaluate these target definitions:

- 1-day forward return
- 3-day forward return
- 5-day forward return
- optional directional target: forward return above threshold

### Rules

- use the same underlying dataset version across all H2 variants,
- keep feature set stable during first-pass comparison,
- change only target construction at this stage.

---

## Step 3 — Run Minimum Baselines

For each H2 target variant, run:

- linear or logistic baseline
- tree-based baseline
- naive momentum baseline

### Notes

- keep model complexity intentionally modest,
- avoid hyperparameter fishing before gate viability is proven,
- use the same rolling-window scheme across all H2 runs.

---

## Step 4 — Apply the Required Evaluation Framework

For every H2 run, report:

- rolling-window metrics
- buy-hold comparison
- naive momentum comparison
- flat/no-trade baseline when relevant
- gross vs net results
- recent-window behavior
- stability across windows

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

---

## Step 5 — Use Hard Kill Logic

Kill an H2 variant immediately if any of these are true:

- predictive metrics remain near or below naive,
- net edge is non-positive after costs,
- fewer than 2/3 windows beat buy-hold or momentum,
- recent window fails severely,
- performance is carried by a single window.

---

## Step 6 — Record Results in One Ledger

Maintain one consolidated Stage 2 results ledger with:

- hypothesis id
- run id
- target variant
- cost assumptions
- window-level metrics
- aggregate metrics
- gate-by-gate pass/fail
- final verdict
- next action

Do not rely on memory or scattered notes.

---

## Step 7 — Make the Decision

### Continue H2 only if:

- mean net benchmark gap > 0,
- at least 2/3 windows beat buy-hold or momentum,
- recent window passes,
- CV is acceptable,
- gains survive costs.

### If H2 fails:

- stop H2,
- document the failure cleanly,
- move to H1.

### If H2 passes:

- deepen the analysis carefully,
- only then consider richer feature work or expanded baselines.

---

## Final Rule

Do not treat “interesting” results as success.
Only treat **gate-clearing** results as success.

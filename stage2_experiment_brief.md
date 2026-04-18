# Stage 2 Experiment Brief

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Status: Draft for local development only  
Purpose: Define fresh research hypotheses after Stage 1 hard exit

---

## Context

Stage 1 ended with a hard exit after the supervised baseline failed all key gates:

- Rolling-window predictive performance was negative.
- Regime stability was poor.
- Buy-hold benchmark failed in all 3 windows.
- RL escalation was blocked because the supervised foundation showed no durable economic edge.

Stage 2 must not be framed as rescuing the old signal.
Stage 2 is a falsification-first phase for new hypotheses under stricter evidence standards.

---

## Stage 2 Objective

Identify whether there is any robust, economically meaningful predictive structure under a different problem framing.

The objective is not quick backtest return maximization.
The objective is to invalidate weak ideas fast and only continue when a hypothesis survives:

- rolling windows,
- trivial baselines,
- regime variation,
- and cost-aware evaluation.

---

## Hypothesis 1: Event-Driven Prediction Beats Continuous Prediction

### H1 Thesis

Continuous prediction diluted sparse high-information periods.
An event-driven setup may isolate contexts with better signal-to-noise.

### H1 Prediction Task

Only predict around event contexts such as:

- earnings windows,
- macro event days,
- volatility expansion days,
- abnormal volume days,
- sentiment shock days.

### H1 Minimum Baseline Models

- logistic regression,
- random forest or gradient boosting,
- simple threshold event-tag rules.

### H1 Go / No-Go Gates

Proceed only if all are true:

1. At least 2/3 rolling windows show positive economic edge versus buy-hold or relevant event baseline.
2. Predictive quality is consistently above naive baseline.
3. Performance is not carried by one event cluster.
4. Edge remains positive after costs.

### H1 Kill Criteria

Stop immediately if:

- performance appears in only one window,
- event count is too low for reliable inference,
- edge disappears after transaction costs.

---

## Hypothesis 2: Longer-Horizon Targets Are More Stable Than Short-Horizon Targets

### H2 Thesis

Prior targets were too noisy and too sensitive to compressed regimes.
Longer horizons may better align with persistent information.

### H2 Prediction Task

Test targets such as:

- 1-day forward return,
- 3-day forward return,
- 5-day forward return,
- directional move above threshold over multi-day horizon.

### H2 Minimum Baseline Models

- linear or logistic baseline,
- tree-based baseline,
- naive momentum and buy-hold baselines.

### H2 Go / No-Go Gates

Proceed only if all are true:

1. Mean rolling-window economic performance is positive.
2. At least 2/3 windows beat buy-hold or simple momentum baseline.
3. Stability coefficient is acceptable and not dominated by one period.
4. Risk-adjusted return remains positive after costs.

### H2 Kill Criteria

Stop if:

- predictive metrics remain near or below naive,
- economic edge is weaker than trivial momentum,
- recent-window performance collapses.

---

## Hypothesis 3: Cross-Sectional Ranking Works Better Than Single-Asset Direction

### H3 Thesis

Relative signal may exist even when absolute direction is weak.
Ranking assets may be easier than forecasting exact direction.

### H3 Prediction Task

At each rebalance date:

- rank assets by expected forward return,
- long top-ranked (optionally short bottom-ranked),
- compare against equal-weight and buy-hold benchmarks.

### Candidate Universe

- AAPL,
- AMD,
- NVDA,
- QQQ,
- SPY,
- optional liquid tech or sector ETFs.

### H3 Minimum Baseline Models

- linear rank model,
- tree-based rank surrogate,
- momentum ranking baseline,
- equal-weight benchmark.

### H3 Go / No-Go Gates

Proceed only if all are true:

1. Portfolio beats equal-weight and buy-hold in at least 2/3 rolling windows.
2. Ranking quality is persistent across windows.
3. Performance is not entirely explained by one dominant ticker.
4. Turnover remains reasonable after costs.

### H3 Kill Criteria

Stop if:

- top picks are unstable,
- one ticker dominates all gains,
- net outperformance disappears after costs.

---

## Global Stage 2 Rules

### Required Validation

Every hypothesis must pass:

- rolling-window validation,
- trivial baseline comparison,
- cost-aware evaluation,
- recent-window evaluation.

### Forbidden Failure Modes

Do not continue if:

- only one split looks good,
- buy-hold wins cleanly,
- thresholding creates isolated positive backtests without predictive support,
- results depend on one ticker or one regime only.

### RL Escalation Rule

No RL work unless a Stage 2 hypothesis shows:

1. durable forward economic edge,
2. acceptable regime stability,
3. superiority over trivial alternatives.

RL is not an exploration shortcut for failed supervised hypotheses.

---

## Recommended Execution Order

1. Hypothesis 2 (longer-horizon targets)
2. Hypothesis 1 (event-driven prediction)
3. Hypothesis 3 (cross-sectional ranking)

Rationale:

- H2 changes target design with minimal data expansion.
- H1 tests sparse high-information contexts.
- H3 likely offers value but requires the most setup.

---

## Deliverables Before Any New Model Build

Create and maintain:

- stage2_experiment_brief.md,
- stage2_gate_definitions.md,
- stage2_hypothesis_matrix.json.

---

## Final Decision Rule

Stage 2 continues only if at least one hypothesis demonstrates:

- forward robustness,
- benchmark outperformance,
- cross-window stability.

Otherwise treat predictive alpha discovery on this dataset/setup as unproven and avoid further optimization.

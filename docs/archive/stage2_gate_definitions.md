# Stage 2 Gate Definitions

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Scope: Hard go/no-go contract for Stage 2 hypothesis testing

---

## 1. Gate Philosophy

Stage 2 is falsification-first. A hypothesis is accepted only if it clears all required gates under forward-looking validation.

Primary objective: detect robust economic edge, not optimize isolated backtests.

---

## 2. Evaluation Framework

## 2.1 Rolling-Window Scheme

Use at least 3 forward rolling windows.
Recommended default:

- train fraction: 0.20,
- validation fraction: 0.20,
- test fraction: 0.20,
- slide fraction: 0.33.

Minimum requirement: no overlap leakage from future rows into train features or labels.

## 2.2 Benchmarks (Required)

Every run must compare against:

- buy-hold benchmark,
- naive momentum benchmark,
- flat/no-trade baseline when relevant.

For cross-sectional tasks also include:

- equal-weight portfolio benchmark.

## 2.3 Cost Model (Required)

Report gross and net metrics.
Minimum cost assumptions:

- per-trade transaction cost,
- optional slippage assumption,
- turnover-aware total cost impact.

A result that only works gross and fails net is a gate failure.

---

## 3. Core Metrics

Track per window and aggregate:

- total return,
- annualized return,
- Sharpe ratio,
- max drawdown,
- turnover,
- win rate,
- benchmark return gap,
- benchmark Sharpe gap,
- predictive quality metric (task-specific: R2, directional accuracy, AUC, rank IC).

Stability metric:

- coefficient of variation (CV) across windows for primary economic metric.

---

## 4. Global Stage 2 Gates

A hypothesis can proceed only if all global gates pass:

1. Benchmark Superiority:

- beats buy-hold or task-relevant benchmark in at least 2/3 windows,
- includes at least one recent-window pass.

1. Economic Robustness:

- mean net economic edge > 0 across windows,
- mean net Sharpe > 0.

1. Stability:

- no single window contributes more than 70 percent of total edge,
- CV is acceptable for strategy class (default target: CV < 1.0).

1. Predictive Support:

- predictive metric is consistently above naive baseline,
- no contradiction where trading gains exist only via threshold artifacts.

1. Cost Survivability:

- edge remains positive after costs,
- turnover does not invalidate net outcome.

---

## 5. Hypothesis-Specific Gates

## 5.1 H1 Event-Driven

Pass only if:

- event sample count is sufficient in each window,
- edge is present across more than one event type,
- net edge survives costs in at least 2/3 windows.

Kill if:

- one event type explains almost all gains,
- sample count is too low for inference,
- recent window fails clearly.

## 5.2 H2 Longer-Horizon

Pass only if:

- at least one horizon (1D, 3D, 5D) shows positive mean net edge,
- at least 2/3 windows beat buy-hold or momentum,
- recent window does not collapse.

Kill if:

- predictive metrics remain naive-like,
- edge is lower than trivial momentum,
- net returns turn negative after costs.

## 5.3 H3 Cross-Sectional Ranking

Pass only if:

- ranked portfolio beats equal-weight and buy-hold in at least 2/3 windows,
- rank quality (for example rank IC) is persistent,
- gains are not dominated by one ticker,
- turnover-adjusted net edge remains positive.

Kill if:

- rank ordering is unstable,
- one ticker drives nearly all outperformance,
- benchmark outperformance disappears net of costs.

---

## 6. Hard Stop Conditions

Immediately stop a hypothesis if any condition is true:

- only one window is positive,
- buy-hold cleanly dominates,
- net edge is non-positive after costs,
- recent window fails severely,
- leakage or benchmark inconsistency is detected.

---

## 7. Stage 2 Exit and Escalation Logic

## 7.1 Continue Stage 2

Continue only if at least one hypothesis passes all required gates.

## 7.2 Exit Project Exploration

Exit predictive alpha exploration for this dataset/setup if no hypothesis passes.

## 7.3 RL Escalation

RL is allowed only when at least one Stage 2 hypothesis demonstrates:

- durable forward economic edge,
- acceptable cross-window stability,
- superiority versus trivial baselines.

Otherwise RL escalation remains blocked.

---

## 8. Reporting Contract

For every hypothesis report:

- window-level metrics table,
- benchmark comparison table,
- gross vs net table,
- stability diagnostics,
- pass/fail verdict with gate IDs,
- explicit recommendation: continue or kill.

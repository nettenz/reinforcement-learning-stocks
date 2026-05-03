# DASHBOARD_GRAPH_TODO

Last updated: 2026-05-02

This file lists the specific dashboard graphs and small implementation notes required for the new **Performance Analytics** section.

## Goals
- Provide an at-a-glance view of model/ensemble health and freshness.
- Offer quick, reproducible visual diagnostics (equity curve, rolling risk metrics, trade-rate distributions, val-test drift heatmaps).
- Use existing helpers in `src/signal_analytics.py` and follow current Streamlit/Altair patterns in `src/analytics_dashboard.py`.

---

## Completed

- [x] Equity curve + benchmark overlay (high)
  - Inputs: `date` or `step`, `net_worth`, `cumulative_pnl`, `val_benchmark_cumulative_return` / `test_benchmark_cumulative_return` from leaderboard when available.
  - Notes: Implemented in Performance Analytics. Includes buy/sell markers (via background zones) and benchmark buy-and-hold comparison.

- [x] Rolling Sharpe / Sortino + drawdown panel (high)
  - Inputs: per-step net worth or per-trade returns.
  - Notes: Implemented in Performance Analytics. Computes rolling Sharpe/Sortino and displays strategy vs benchmark drawdown.

- [x] Trade-rate distribution & action breakdown (medium)
  - Inputs: `action_label`, `trade_rate`, `reward`, `trade_edge` from enriched signals.
  - Notes: Added PnL contribution bar chart and Action Mix table in Signal Analytics.

- [x] Leaderboard heatmap / val-test drift scatter (medium)
  - Inputs: leaderboard snapshots (`val_actionable_accuracy`, `test_actionable_accuracy`, `val_sharpe_ratio`, `test_sharpe_ratio`)
  - Notes: Added Generalization Scatter (Val vs Test Actionable) in Experiment Insights. Full heatmap still pending (see Tier 2 below).

- [x] Signal Quality & Reward Alignment Scatter
  - Inputs: `reward`, `horizon_return`, `action_label`, `confidence`.
  - Notes: Added to Signal Analytics. Sampling applied for performance (>5k rows).

- [x] Ensemble agreement/consistency visuals (medium)
  - Inputs: ensemble `confidence` or per-seed predictions (from `simulate_ensemble_signals`).
  - Notes: Added agreement metrics (Majority, Unanimous) to Signal Analytics KPI row. Confidence used as size in Signal Quality scatter.

- [x] Data freshness indicator + refresh button
  - Notes: Added to Performance Analytics. Shows model snapshot mtime; button triggers `evaluate_signals` call.

---

## Pending — Tier 1 (High Impact, Low Effort)

- [ ] **Promotion gate cards** (high)
  - Replace the `st.dataframe` gate table in Experiments page section 2 with a 6-column card row (one per gate).
  - Each card: gate name, current value, threshold, PASS/FAIL color state, and a small linear progress indicator showing distance from threshold.
  - Use `st.metric(delta=value - threshold, delta_color="normal")` per card, or a custom `st.markdown` HTML block for full color control.
  - Gate 6 (`test_trade_rate ∈ [0.40, 0.80]`) requires special handling — delta is distance from the nearest bound, not a single threshold.
  - Files: `src/analytics_dashboard.py` → `render_experiments_page()` section 2.

- [ ] **Val vs Test Sharpe scatter: y=x diagonal** (high)
  - Add a `mark_rule` diagonal to the existing seed stability scatter (section 4, Experiments page).
  - Points above the line = val > test = overfitting zone. Points below = conservative generalizers.
  - Implement as: `alt.Chart(pd.DataFrame({"v": [min_val, max_val]})).mark_line(strokeDash=[4,4], color="#9ca3af").encode(x="v:Q", y="v:Q")` where `min_val`/`max_val` are computed from both `val_sharpe_ratio` and `test_sharpe_ratio`.
  - Add a text annotation label "Overfit Zone" and "Healthy Zone" on each side of the diagonal.
  - Files: `src/analytics_dashboard.py` → scatter in section 4 of `render_experiments_page()`.

- [ ] **Trade rate distribution histogram with Gate 6 band** (high)
  - Render immediately after sweep evaluation in Experiments page, adjacent to the leaderboard table.
  - Chart: histogram of `test_trade_rate` across all configs in the current sweep label.
  - Overlay a shaded green `mark_rect` band at x=[0.40, 0.80] to visualize the Gate 6 pass zone.
  - Add vertical `mark_rule` lines at 0.40 and 0.80 with text labels.
  - Title should include count of configs inside vs outside the band: e.g. "12 / 20 configs in healthy zone".
  - Inputs: `leaderboard[leaderboard["run_label"] == current_label]["test_trade_rate"]`.
  - Files: `src/analytics_dashboard.py` → new helper `render_trade_rate_histogram()`.

- [ ] **Metric cards: threshold-aware delta colors** (medium)
  - All `st.metric` calls in Experiments page section 2 currently show raw values with no threshold context.
  - Pass `delta = value - threshold` and `delta_color="normal"` so Streamlit auto-colors green/red relative to the gate.
  - For the val-test gap gate (must be ≤ 0.05), negate the delta: `delta = threshold - abs(gap)`.
  - Files: `src/analytics_dashboard.py` → `render_experiments_page()` section 2 metrics.

---

## Pending — Tier 2 (High Impact, Medium Effort)

- [ ] **Leaderboard gate heatmap** (high)
  - 2D `mark_rect` heatmap: rows = seed or config index, columns = gate metrics (actionable accuracy, win rate, alpha, val-test gap, CV, trade rate).
  - Cell fill: green if gate passes, red if fails. Cell text: raw value.
  - Use `alt.condition` on per-gate threshold comparisons for color encoding. For trade rate, pass requires value between 0.40 and 0.80.
  - Inputs: leaderboard filtered to current sweep label. All 6 gate columns must be present.
  - Replaces the current need to manually scan CSV to identify which seeds fail which gates.
  - Files: `src/analytics_dashboard.py` → new helper `render_gate_heatmap(leaderboard_df)`, called from `render_experiments_page()`.

- [ ] **Snapshot accuracy timeline** (high)
  - Dual-line chart of `val_actionable_accuracy` and `test_actionable_accuracy` over `snapshot_time`, using data from `load_experiment_history()` + `summarize_snapshot_bests()`.
  - Add a horizontal `mark_rule` at y=0.53 (Gate 1 threshold) with a dashed style.
  - Shade the area between the two lines as a translucent band to visualize the val-test gap trend over time. Widening band = increasing overfit drift.
  - Add a second y-axis or separate panel for `test_return_cv_by_config` trend.
  - Answers "is the system improving across experiments?" at a glance.
  - Files: `src/analytics_dashboard.py` → new helper `render_snapshot_timeline(history_df)`, called from `render_experiment_insights_page()`.

- [ ] **Ensemble confidence distribution by action class** (medium)
  - Box plot or violin plot of `confidence` grouped by `action_label` (Buy / Hold / Sell).
  - Reveals calibration: high confidence on correct actions = well-calibrated; high confidence on wrong class = systematic miscalibration.
  - Altair does not support native violin plots; use `mark_boxplot()` as the practical alternative.
  - Only render when `use_ensemble=True` and `confidence` column is present in enriched signals.
  - Files: `src/analytics_dashboard.py` → extend `render_signal_analytics_page()` ensemble branch.

- [ ] **Per-seed equity overlays** (medium)
  - Render all champion seeds' equity curves on one chart. Thin low-opacity lines per seed (opacity=0.3), thick aggregate mean line on top (opacity=1.0, strokeWidth=2.5).
  - Visual spread of the fan = intuitive cross-seed CV. Tight fan = robust config; wide fan = high instability.
  - Load per-seed `net_worth` series from snapshot CSVs or re-simulate via `simulate_agent_signals()` for each seed path in `ensemble_config.json`.
  - Inputs: `staging/models/ensemble_config.json` → champion seeds → per-seed model paths.
  - Files: `src/analytics_dashboard.py` → extend `render_performance_analytics_page()`.

---

## Pending — Tier 3 (Lower Priority)

- [ ] **Regime-aware equity curve background** (medium)
  - Color the equity curve panel background by inferred market regime.
  - Simple proxy: 200-day SMA slope. Positive slope = bull (light green tint), negative = bear (light red tint), flat = neutral (gray).
  - Implement as `mark_rect` background zones layered under the equity line, same pattern as the existing buy/sell background zones.
  - Reveals whether agent alpha is regime-dependent (critical for NVDA given the AI boom trend).
  - Files: `src/analytics_dashboard.py` → extend `render_performance_analytics_page()` equity section.

- [ ] **Buy/sell marker glyphs: replace background zones** (low)
  - Current approach: colored background rectangles per bar. Obscures price action on dense runs.
  - Replace with `mark_point(shape="triangle-up", size=80, color="#10b981")` for buys and `mark_point(shape="triangle-down", size=80, color="#ef4444")` for sells, plotted on the price line.
  - Retain background zones as an optional toggle (`show_background_zones`) for users who prefer them.
  - Files: `src/analytics_dashboard.py` → `render_charts()` signal overlay section.

- [ ] **Benchmark logic refinement** (low)
  - Pull `benchmark_cumulative_return` directly from leaderboard columns when available, for exact per-split comparison instead of recomputing from price data.
  - Files: `src/analytics_dashboard.py` → `render_performance_analytics_page()` equity chart.

---

## Implementation Guidance

- Reuse `evaluate_signals`, `add_cumulative_pnl` and other helpers in `src/analytics_dashboard.py` and `src/signal_analytics.py`.
- Avoid constructing empty Altair layers; only add layers when the underlying DataFrame is non-empty.
- Respect the dashboard `interval` (daily vs 5m) and adjust annualization constant for Sharpe accordingly.
- Cache careful: `@st.cache_data` is used widely; for refresh actions use an explicit cache-buster argument (timestamp) when calling cached functions.
- For Gate 6 (`test_trade_rate ∈ [0.40, 0.80]`): delta display requires custom logic — show distance from nearest bound, not a single threshold difference.
- All new charts should follow the existing Altair color conventions: validation metrics in sky blue (`#38bdf8`), test metrics in emerald (`#10b981`), pass states in `#00FF9D`, fail states in `#ef4444`.

### File references
- Dashboard main UI: `src/analytics_dashboard.py`
- Ensemble + simulation helpers: `src/signal_analytics.py`
- Leaderboard artifacts: `data/experiment_leaderboard.csv` and `data/experiment_snapshots/`
- Ensemble config: `staging/models/ensemble_config.json`
- Gate evaluation logic: `_evaluate_promotion_gates()` in `src/analytics_dashboard.py`
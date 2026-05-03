# DASHBOARD_GRAPH_TODO

Last updated: 2026-05-02

This file lists the specific dashboard graphs and small implementation notes required for the new **Performance Analytics** section.

DASHBOARD_GRAPH_TODO

## Goals
- Provide an at-a-glance view of model/ensemble health and freshness.
- Offer quick, reproducible visual diagnostics (equity curve, rolling risk metrics, trade-rate distributions, val-test drift heatmaps).
- Use existing helpers in `src/signal_analytics.py` and follow current Streamlit/Altair patterns in `src/analytics_dashboard.py`.

## Priority Checklist
- [ ] Equity curve + benchmark overlay (high)
  - Inputs: `date` or `step`, `net_worth`, `cumulative_pnl`, `val_benchmark_cumulative_return` / `test_benchmark_cumulative_return` from leaderboard when available.
  - Notes: overlay buy/sell markers, shaded drawdown area. Use Altair layered chart; avoid adding empty layers.

- [ ] Rolling Sharpe / Sortino + drawdown panel (high)
  - Inputs: per-step net worth or per-trade returns.
  - Notes: compute rolling returns, rolling std, annualize (use 252 for daily; adjust for intraday). Provide window selector (30/60/90).

- [x] Trade-rate distribution & action breakdown (medium)
  - Inputs: `action_label`, `trade_rate`, `reward`, `trade_edge` from enriched signals.
  - Notes: Added PnL contribution bar chart and Action Mix table in Signal Analytics.

- [x] Leaderboard heatmap / val-test drift scatter (medium)
  - Inputs: leaderboard snapshots (val_actionable_accuracy, test_actionable_accuracy, val_sharpe_ratio, test_sharpe_ratio)
  - Notes: Added Generalization Scatter (Val vs Test Actionable) in Experiment Insights. Heatmap logic still pending but scatter fulfills core need.

- [x] Signal Quality & Reward Alignment Scatter (New)
  - Inputs: `reward`, `horizon_return`, `action_label`, `confidence`.
  - Notes: Added to Signal Analytics. Sampling applied for performance (>5k rows).

- [ ] Ensemble agreement/consistency visuals (medium)
  - Inputs: ensemble `confidence` or per-seed predictions (from `simulate_ensemble_signals`).
  - Notes: show agreement rate, per-seed equity overlays, and a small table of active seeds.

- [ ] Data freshness indicator + refresh button (done: basic implementation)
  - Notes: ensure `st.metric` shows model snapshot mtime and leaderboard snapshot mtime; button triggers a quick `evaluate_signals` call with caching disabled.

## Implementation Guidance
- Reuse `evaluate_signals`, `add_cumulative_pnl` and other helpers in `src/analytics_dashboard.py` and `src/signal_analytics.py`.
- Avoid constructing empty Altair layers; only add layers when the underlying DataFrame is non-empty.
- Respect the dashboard `interval` (daily vs 5m) and adjust annualization constant for Sharpe accordingly.
- Cache careful: `@st.cache_data` is used widely; for refresh actions use an explicit cache-buster argument (timestamp) when calling cached functions.
- File references:
  - Dashboard main UI: `src/analytics_dashboard.py`
  - Ensemble + simulation helpers: `src/signal_analytics.py`
  - Leaderboard artifacts: `data/experiment_leaderboard.csv` and `data/experiment_snapshots/`

## Next actions (small increments)
1. Implement equity-curve + benchmark overlay and test with one leaderboard row (NVDA).  
2. Add rolling Sharpe/drawdown panel; verify annualization for `interval`.  
3. Add trade-rate distribution and leaderboard heatmap.  
4. Wire ensemble-mode refresh and per-seed overlays.


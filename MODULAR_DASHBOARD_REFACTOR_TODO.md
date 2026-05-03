# Dashboard Modularization TODO

## Goal
Refactor `src/analytics_dashboard.py` into focused modules without changing current behavior.

## Principles
- Preserve UX and outputs first; improve structure second.
- Move code in small slices with compile/run checks after each slice.
- Keep page-level entry points stable while migrating internals.
- Prefer pure functions in service/chart modules for easier testing.

## Phase 0: Baseline and Safety
- [ ] Confirm current app runs from `.venv` and page routing works.
- [ ] Capture baseline screenshots for each page section.
- [ ] Add a lightweight smoke checklist (manual):
  - [ ] Signal Analytics renders and runs.
  - [ ] Experiments page loads leaderboard.
  - [ ] Experiment Insights charts render.
  - [ ] Performance Analytics refresh works.

## Phase 1: Create Module Skeleton
- [ ] Create package structure:
  - [ ] `src/dashboard/__init__.py`
  - [ ] `src/dashboard/config.py`
  - [ ] `src/dashboard/state.py`
  - [ ] `src/dashboard/services/`
  - [ ] `src/dashboard/charts/`
  - [ ] `src/dashboard/pages/`
  - [ ] `src/dashboard/ui/`
- [ ] Add `src/dashboard/config.py` for constants/paths/defaults currently in the monolith.
- [ ] Keep existing `src/analytics_dashboard.py` as orchestrator entry point.

## Phase 2: Extract Shared Utilities
- [ ] Move non-UI helpers into `src/dashboard/services/`:
  - [ ] Data loading and ticker/path resolution.
  - [ ] Leaderboard/history loaders and summarizers.
  - [ ] Model discovery and selection helpers.
- [ ] Move formatting/helpers to `src/dashboard/ui/formatting.py`.
- [ ] Update imports in `src/analytics_dashboard.py`.
- [ ] Verify no behavior changes.

## Phase 3: Extract Charts
- [ ] Move reusable chart builders into `src/dashboard/charts/`:
  - [ ] Equity curve chart builder.
  - [ ] Drawdown chart builder.
  - [ ] Rolling Sharpe/Sortino chart builder.
  - [ ] Trend/stability charts used by Insights.
- [ ] Ensure chart functions accept DataFrames + options and return Altair charts.
- [ ] Keep Streamlit layout calls in page modules, not chart modules.

## Phase 4: Extract Pages
- [ ] Create page modules:
  - [ ] `src/dashboard/pages/signal_analytics.py`
  - [ ] `src/dashboard/pages/experiments.py`
  - [ ] `src/dashboard/pages/experiment_insights.py`
  - [ ] `src/dashboard/pages/performance_analytics.py`
- [ ] Move each `render_*_page` function to its page module one by one.
- [ ] Keep function signatures stable during migration.
- [ ] Wire dispatch in `src/analytics_dashboard.py` to imported page renderers.

## Phase 5: Sidebar and Routing Cleanup
- [ ] Move global sidebar controls into `src/dashboard/ui/sidebar.py`.
- [ ] Centralize section routing map in one place.
- [ ] Remove duplicate per-page control logic where possible.

## Phase 6: Validation and Cleanup
- [ ] Run compile check:
  - [ ] `python -m py_compile src/analytics_dashboard.py`
- [ ] Launch and manually verify all pages.
- [ ] Remove dead code and duplicate helpers from monolith.
- [ ] Add module-level docstrings for pages/services/charts.

## Stretch Tasks (Optional)
- [ ] Add unit tests for pure service functions.
- [ ] Add snapshot-style checks for chart schema outputs.
- [ ] Add a short `docs/dashboard_architecture.md` with module map.

## Definition of Done
- [ ] `src/analytics_dashboard.py` becomes a thin orchestrator (routing + top-level app setup).
- [ ] Page logic lives in `src/dashboard/pages/`.
- [ ] Reusable data/charts live in `services/` and `charts/`.
- [ ] No regressions in core user flows.

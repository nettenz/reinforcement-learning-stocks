# Dashboard Modularization TODO

> **Goal:** Break `analytics_dashboard.py` (3,105 lines) into a clean `src/dashboard/` package.  
> Each task below is self-contained and includes a copy-paste prompt you can hand directly to an AI agent or use as a focused session brief.

---

## Target Architecture

```
src/
└── dashboard/
    ├── __init__.py
    ├── config.py                    # all constants + path definitions
    ├── model_utils.py               # model scanning, selection, interval inference, validation
    ├── data_utils.py                # market data I/O, split filter, evaluate_signals, ticker helpers
    ├── leaderboard.py               # leaderboard loading, experiment history, stage1 loaders, cache busters
    ├── analytics.py                 # promotion gates, pnl utils, action mix, interpretation, recommendations
    ├── components/
    │   ├── __init__.py
    │   ├── charts.py                # render_charts, render_roc_curves, render_theoretical_headroom
    │   ├── metrics.py               # render_metrics, render_confusion_heatmap
    │   ├── gates.py                 # render_promotion_gate_cards, render_trade_rate_histogram
    │   └── ensemble.py              # display_ensemble_config
    └── pages/
        ├── __init__.py
        ├── signal_analytics.py      # render_signal_analytics_page
        ├── experiments.py           # render_experiments_page
        ├── experiment_insights.py   # render_experiment_insights_page
        └── performance_analytics.py # render_performance_analytics_page

analytics_dashboard.py              # entrypoint only: sidebar + page routing
```

---

## Tasks

### [ ] Task 1 — Extract `config.py`

**Lines to move:** ~1–63 (all module-level constants)

**Functions/names:**
- `ROOT_DIR`, `DEFAULT_TICKER`
- All `*_PATH`, `*_DIR` path constants
- `DEFAULT_ACTIONABLE_TARGET`, `RECOMMENDED_*` constants
- `PROMOTION_GATE_DEFAULTS` dict

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/config.py.

Extract everything from the top of the file through line ~63:
- ROOT_DIR and all Path constants (DEFAULT_DATA_PATH, STATIONARY_DATA_PATH, all leaderboard/snapshot/stage1 paths)
- DEFAULT_TICKER, DEFAULT_ACTIONABLE_TARGET
- RECOMMENDED_THRESHOLD, RECOMMENDED_HORIZON, RECOMMENDED_CHART_WINDOW
- PROMOTION_GATE_DEFAULTS dict

Requirements:
- Keep all Path definitions relative to ROOT_DIR
- No imports from other dashboard submodules (config has no internal deps)
- Export all names at module level (no __all__ needed)

After creating config.py, update analytics_dashboard.py to replace all inline constant
definitions with: from src.dashboard.config import *
```

---

### [ ] Task 2 — Extract `model_utils.py`

**Lines to move:** ~65–439

**Functions:**
- `_validate_model_shape`
- `_data_path_is_compatible_with_expected_shape`
- `_normalize_dashboard_interval`
- `_infer_interval_from_model_path`
- `build_model_cache_buster`
- `_artifact_paths_for_interval`
- `_leaderboard_paths_for_interval_hint`
- `_list_available_models`
- `_preferred_data_path_for_model`
- `_ticker_symbol_from_key`
- `_ticker_match_mask`
- `_latest_comparable_leaderboard`
- `_top_ranked_models_from_leaderboard`
- `_format_model_label`
- `_resolve_model_path`
- `_model_path_matches_ticker`
- `_infer_recent_interval_for_ticker`
- `_curate_model_choices`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/model_utils.py.

Extract these functions (with their exact implementations):
_validate_model_shape, _data_path_is_compatible_with_expected_shape,
_normalize_dashboard_interval, _infer_interval_from_model_path,
build_model_cache_buster, _artifact_paths_for_interval,
_leaderboard_paths_for_interval_hint, _list_available_models,
_preferred_data_path_for_model, _ticker_symbol_from_key,
_ticker_match_mask, _latest_comparable_leaderboard,
_top_ranked_models_from_leaderboard, _format_model_label,
_resolve_model_path, _model_path_matches_ticker,
_infer_recent_interval_for_ticker, _curate_model_choices

Required imports for this module:
- from src.dashboard.config import ROOT_DIR, DEFAULT_DATA_PATH, STATIONARY_DATA_PATH, ...
  (all path constants these functions reference)
- from src.market_data import TICKER_PRESETS, get_cache_path_for_ticker
- from src.signal_analytics import _align_features_to_model, _expected_observation_dim, _load_model
- from src.trading_env import TradingEnv
- Standard: re, pathlib.Path, pandas, streamlit (only for st.error/st.stop/st.sidebar.warning in _validate_model_shape)

Note: _validate_model_shape has direct st.error/st.stop calls — keep them, they're intentional
Streamlit coupling for this validation function.

After creating the module, update analytics_dashboard.py imports accordingly.
```

---

### [ ] Task 3 — Extract `data_utils.py`

**Lines to move:** ~441–511

**Functions:**
- `get_data_path_for_ticker`
- `load_market_data` (has `@st.cache_data`)
- `evaluate_signals` (has `@st.cache_data`)
- `_apply_split_filter`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/data_utils.py.

Extract these functions with their exact decorators and implementations:
- get_data_path_for_ticker
- load_market_data (preserve @st.cache_data(show_spinner=False))
- evaluate_signals (preserve @st.cache_data(show_spinner=False))
- _apply_split_filter

Required imports:
- from src.dashboard.config import DEFAULT_DATA_PATH
- from src.market_data import get_cache_path_for_ticker
- from src.signal_analytics import (
    enrich_with_truth_labels, confusion_matrix,
    simulate_agent_signals, simulate_ensemble_signals
  )
- Standard: pathlib.Path, pandas, streamlit

Note: @st.cache_data is sensitive to the function's source location — after moving,
verify the cache key still works by confirming streamlit doesn't show unexpected cache misses
on first run. If it does, add `cache_busting=False` or pin an explicit `hash_funcs` arg.

After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 4 — Extract `leaderboard.py`

**Lines to move:** ~576–868

**Functions:**
- `_parse_snapshot_timestamp`
- `_extract_snapshot_label` *(grep for it — likely defined nearby or imported)*
- `_make_command_from_config`
- `_detect_leaderboard_tickers`
- `load_experiment_history` (has `@st.cache_data`)
- `build_history_cache_buster`
- `build_stage1_cache_buster`
- `load_stage1_snapshot_history` (has `@st.cache_data`)
- `load_stage1_gate_summary` (has `@st.cache_data`)

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/leaderboard.py.

Extract these functions (preserve all @st.cache_data decorators):
_parse_snapshot_timestamp, _extract_snapshot_label, _make_command_from_config,
_detect_leaderboard_tickers, load_experiment_history, build_history_cache_buster,
build_stage1_cache_buster, load_stage1_snapshot_history, load_stage1_gate_summary

Required imports:
- from src.dashboard.config import (
    ROOT_DIR, DEFAULT_LEADERBOARD_PATH, INTRADAY_5M_LEADERBOARD_PATH,
    DEFAULT_SNAPSHOT_DIR, INTRADAY_5M_SNAPSHOT_DIR, STAGE1_RESULTS_DIR,
    STAGE1_CONFIRMATION_DIR, STAGE1_PIVOT_REPORT_PATH, ...all referenced paths
  )
- from src.dashboard.model_utils import _latest_comparable_leaderboard, _ticker_match_mask
- from src.market_data import TICKER_PRESETS
- Standard: json, re, datetime, pathlib.Path, pandas, numpy, streamlit

After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 5 — Extract `analytics.py`

**Lines to move:** ~870–1167

**Functions:**
- `summarize_snapshot_bests`
- `_safe_get`
- `_evaluate_promotion_gates`
- `_config_from_row`
- `build_next_step_recommendations`
- `build_experiment_interpretation`
- `compute_pnl_summary`
- `add_cumulative_pnl`
- `build_action_mix_table`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/analytics.py.

Extract these pure logic / analytics functions (no streamlit calls in this group):
summarize_snapshot_bests, _safe_get, _evaluate_promotion_gates, _config_from_row,
build_next_step_recommendations, build_experiment_interpretation,
compute_pnl_summary, add_cumulative_pnl, build_action_mix_table

Required imports:
- from src.dashboard.config import PROMOTION_GATE_DEFAULTS, ACTION_LABELS
  (note: ACTION_LABELS may be in signal_analytics — confirm and import from the right place)
- from src.dashboard.leaderboard import _make_command_from_config, summarize_snapshot_bests
  (build_next_step_recommendations calls _make_command_from_config and summarize_snapshot_bests)
- Standard: numpy, pandas

No streamlit imports needed in this module — keep it UI-free so it's testable in isolation.

After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 6 — Extract `components/metrics.py`

**Lines to move:** ~1169–1332

**Functions:**
- `render_theoretical_headroom`
- `render_confusion_heatmap`
- `render_metrics`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/components/metrics.py (create the components/ dir with __init__.py too).

Extract these render functions exactly as-is:
- render_theoretical_headroom
- render_confusion_heatmap
- render_metrics

Required imports:
- from src.dashboard.analytics import ACTION_LABELS (or from src.signal_analytics)
- from src.signal_analytics import ACTION_LABELS, compute_metrics
- Standard: altair, pandas, streamlit

These functions use altair for the heatmap. Preserve all chart configuration exactly.
After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 7 — Extract `components/charts.py`

**Lines to move:** ~1238–1638

**Functions:**
- `render_roc_curves` (line ~1238)
- `render_charts` (line ~1350, ~290 lines — the big one)

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/components/charts.py.

Extract these two render functions in full, preserving all internal logic, Altair chart specs,
and the helper closures/lambdas inside render_charts:
- render_roc_curves (uses sklearn.metrics — preserve the import)
- render_charts (large function, ~290 lines — do not summarize or simplify, copy verbatim)

Required imports:
- from src.signal_analytics import ACTION_LABELS
- Standard: altair, numpy, pandas, streamlit
- sklearn.metrics (for roc_curve, auc in render_roc_curves)

render_charts takes: enriched, chart_window_rows, show_horizon_panel,
show_error_markers, show_signal_labels, signal_label_budget
— preserve the full signature.

After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 8 — Extract `components/gates.py`

**Lines to move:** ~1878–2027

**Functions:**
- `render_trade_rate_histogram`
- `render_promotion_gate_cards`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/components/gates.py.

Extract these two render functions verbatim:
- render_trade_rate_histogram
- render_promotion_gate_cards

Required imports:
- from src.dashboard.config import PROMOTION_GATE_DEFAULTS
- from src.dashboard.analytics import _evaluate_promotion_gates
- Standard: altair, pandas, streamlit

After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 9 — Extract `components/ensemble.py`

**Lines to move:** ~514–573

**Functions:**
- `display_ensemble_config`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/components/ensemble.py.

Extract display_ensemble_config verbatim.
It reads a JSON ensemble config and renders st.metric / st.info / st.caption panels.

Required imports:
- Standard: json, streamlit

No other internal dashboard deps. Keep the per-ticker data-note logic for nvda/amd.
After creating the module, update analytics_dashboard.py imports.
```

---

### [ ] Task 10 — Extract `pages/signal_analytics.py`

**Lines to move:** ~1640–1877

**Functions:**
- `render_signal_analytics_page`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/pages/signal_analytics.py (create pages/ dir with __init__.py).

Extract render_signal_analytics_page verbatim (~238 lines).
This page owns: ensemble toggle, split selector, action mix table, metrics display,
theoretical headroom, confusion heatmap, ROC curves, and the main chart.

Required imports:
- from src.dashboard.config import RECOMMENDED_CHART_WINDOW, ACTION_LABELS, ...
- from src.dashboard.data_utils import evaluate_signals, _apply_split_filter
- from src.dashboard.analytics import compute_pnl_summary, add_cumulative_pnl, build_action_mix_table
- from src.dashboard.components.metrics import render_theoretical_headroom, render_confusion_heatmap, render_metrics
- from src.dashboard.components.charts import render_charts, render_roc_curves
- from src.dashboard.components.ensemble import display_ensemble_config
- from src.signal_analytics import ACTION_LABELS
- Standard: streamlit, pandas

After creating the module, update analytics_dashboard.py to call:
  from src.dashboard.pages.signal_analytics import render_signal_analytics_page
```

---

### [ ] Task 11 — Extract `pages/experiments.py`

**Lines to move:** ~2028–2362

**Functions:**
- `render_experiments_page`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/pages/experiments.py.

Extract render_experiments_page verbatim (~335 lines).
This page renders the full experiment leaderboard, promotion gate cards, model explorer,
and run command builder.

Required imports:
- from src.dashboard.config import (PROMOTION_GATE_DEFAULTS, DEFAULT_ACTIONABLE_TARGET, ...)
- from src.dashboard.leaderboard import (
    load_experiment_history, build_history_cache_buster,
    _detect_leaderboard_tickers, ...
  )
- from src.dashboard.model_utils import (
    _artifact_paths_for_interval, build_model_cache_buster, _ticker_match_mask, ...
  )
- from src.dashboard.analytics import summarize_snapshot_bests, _evaluate_promotion_gates, _config_from_row
- from src.dashboard.components.gates import render_promotion_gate_cards, render_trade_rate_histogram
- Standard: streamlit, pandas, numpy, altair

After creating the module, update analytics_dashboard.py to call:
  from src.dashboard.pages.experiments import render_experiments_page
```

---

### [ ] Task 12 — Extract `pages/experiment_insights.py`

**Lines to move:** ~2363–2571

**Functions:**
- `render_experiment_insights_page`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/pages/experiment_insights.py.

Extract render_experiment_insights_page verbatim (~209 lines).
This page renders trajectory plots, interpretation banners, and next-step recommendation cards.

Required imports:
- from src.dashboard.config import DEFAULT_ACTIONABLE_TARGET
- from src.dashboard.leaderboard import load_experiment_history, build_history_cache_buster
- from src.dashboard.model_utils import _artifact_paths_for_interval, _ticker_match_mask
- from src.dashboard.analytics import (
    summarize_snapshot_bests, build_experiment_interpretation, build_next_step_recommendations
  )
- Standard: streamlit, pandas, altair

After creating the module, update analytics_dashboard.py to call:
  from src.dashboard.pages.experiment_insights import render_experiment_insights_page
```

---

### [ ] Task 13 — Extract `pages/performance_analytics.py`

**Lines to move:** ~2572–2904

**Functions:**
- `render_performance_analytics_page`

**Prompt:**
```
I'm modularizing analytics_dashboard.py into src/dashboard/.
Create src/dashboard/pages/performance_analytics.py.

Extract render_performance_analytics_page verbatim (~333 lines).
This page renders cumulative PnL, rolling Sharpe/Sortino, drawdown, trade stats,
and buy-and-hold comparison.

Required imports:
- from src.dashboard.config import ...any referenced constants
- from src.dashboard.leaderboard import load_experiment_history, build_history_cache_buster
- from src.dashboard.model_utils import _artifact_paths_for_interval
- from src.signal_analytics import (
    calculate_rolling_sharpe, calculate_rolling_sortino,
    calculate_drawdown, calculate_trade_statistics, calculate_buy_and_hold
  )
- Standard: streamlit, pandas, numpy, altair

After creating the module, update analytics_dashboard.py to call:
  from src.dashboard.pages.performance_analytics import render_performance_analytics_page
```

---

### [ ] Task 14 — Slim down `analytics_dashboard.py` to entrypoint

**What stays:** sidebar logic + `main()` + page routing (~200 lines)

**Prompt:**
```
analytics_dashboard.py has been fully modularized into src/dashboard/.
Now slim it down to a clean entrypoint.

It should only contain:
1. Imports from all the new dashboard submodules
2. The sidebar widget logic (ticker, model selection, interval, threshold, horizon, data path)
3. The main() function with its page routing (if/elif chain for Signal Analytics, Experiment Insights, etc.)
4. The if __name__ == "__main__": main() guard

Remove all function definitions that have been moved out.
Remove all inline constants (they come from src.dashboard.config now).

Target size: ~150–200 lines.

Final imports block should look like:
  from src.dashboard.config import *
  from src.dashboard.model_utils import (build_model_cache_buster, _list_available_models, ...)
  from src.dashboard.data_utils import load_market_data
  from src.dashboard.pages.signal_analytics import render_signal_analytics_page
  from src.dashboard.pages.experiments import render_experiments_page
  from src.dashboard.pages.experiment_insights import render_experiment_insights_page
  from src.dashboard.pages.performance_analytics import render_performance_analytics_page
```

---

### [ ] Task 15 — Wire `src/dashboard/__init__.py`

**Prompt:**
```
Create src/dashboard/__init__.py and src/dashboard/components/__init__.py and src/dashboard/pages/__init__.py.

For src/dashboard/__init__.py, re-export the public API surface that external code
(like analytics_dashboard.py or tests) would need:
- From config: all path constants and threshold defaults
- From data_utils: load_market_data, evaluate_signals
- From leaderboard: load_experiment_history, load_stage1_snapshot_history
- From analytics: compute_pnl_summary, summarize_snapshot_bests

Keep components/__init__.py and pages/__init__.py empty (just docstrings).
This makes the package importable without knowing internal structure.
```

---

## Migration Order

Run tasks in this sequence to avoid broken imports at each step:

```
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9   (foundation + components)
→ 10 → 11 → 12 → 13                    (pages, depend on components)
→ 14                                    (slim entrypoint, depends on all pages)
→ 15                                    (__init__.py wiring, final polish)
```

After each task: `streamlit run analytics_dashboard.py` and spot-check the affected page.

---

## Validation Checklist (post-migration)

- [ ] All 4 pages render without import errors
- [ ] `@st.cache_data` decorators are preserved on `load_market_data`, `evaluate_signals`, `load_experiment_history`, `load_stage1_snapshot_history`, `load_stage1_gate_summary`
- [ ] No circular imports (config ← model_utils ← data_utils ← leaderboard ← analytics ← components ← pages)
- [ ] `signal_analytics.py` (the `src/` one, not the page) is untouched — it has no Streamlit deps and is already clean
- [ ] `analytics_dashboard.py` is ≤200 lines
- [ ] `pytest` or manual smoke test on `compute_metrics`, `_evaluate_promotion_gates`, `build_action_mix_table` (now testable in isolation from `analytics.py`)

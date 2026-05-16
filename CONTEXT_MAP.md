# Context Map — Reinforcement Learning Stocks

**Updated:** 2026-05-16  
**Phase:** Exit Signal Phase 3 (Dashboard Integration)  
**Goal:** Wire the Binary PPO ensemble + ExitManager into the trading dashboard backend/frontend. RL hyperparameter search is complete for all tractable tickers.

---

## Active Research Track: RL Track — Binary PPO Ensemble

### Promoted Tickers (Exp 9 walk-forward PASS)

| Ticker | Seeds | Sweep Label | Alpha | min_hold | Obs Space |
|--------|-------|-------------|-------|----------|-----------|
| **NVDA** | 3,13,7,42 | `nvda-ppo-minhold1-extended` | +0.11–+0.52 | 1 | Raw 10-feat (obs 18) |
| **AMD** | 13,21,7 | `amd-ppo-hold-fix` | +0.28 | 3 | Stationary 27-feat |
| **MU** | 21,3,13 | `mu-ppo-overtrade-fix` | +1.82 | 1 | Stationary (Gate 6 waiver) |

### Deferred Tickers

| Ticker | Reason |
|--------|--------|
| AAPL | Total inaction bias (0% trade rate) across 7 sweeps — architecturally incompatible with Binary PPO |
| AMZN | Drift wall 0.54–0.55, always-long Windows champions not reproducible on updated splits |
| GOOGL | Drift wall 0.55–0.57, 5 sweeps exhausted |
| ALAB | Insufficient training rows (~1500 needed, est. mid-2027) |

---

## Core Source Files (`src/`)

| File | Purpose |
|------|---------|
| `src/trading_env.py` | Gymnasium `TradingEnv` — RL environment with `PositionManager`, `next_bar` execution, `binary_actions`, `min_hold_bars`, fractional shares, spread/slippage |
| `src/feature_engineering.py` | `compute_stationary_features()` — 14 stationary technical indicators (LogReturn, RelVWAP, RelATR, MACD_Signal_Rel, etc.) |
| `src/market_data.py` | Data ingestion via `yfinance`. Builds training frames, handles interval normalization, caches `.parquet` files |
| `src/experiments.py` | Core walk-forward experiment runner — Binary PPO training, val/test splits, 6-gate promotion, leaderboard sync |
| `src/ensemble.py` | `SparseEnsemble` — loads Binary PPO seeds from leaderboard CSV, filters by `active_seeds` + `run_label`, majority-vote inference |
| `src/trading_agent.py` | `EnsembleAgent` — stateless live inference wrapper around `SparseEnsemble`. Reads `ensemble_config.json` |
| `src/exit_manager.py` | **ExitManager** — rule-based exit layer (confidence, trailing_stop, time, profit_take, composite). Wired into `ensemble.py`. Phase 1 complete. |
| `src/analytics_dashboard.py` | Streamlit dashboard — multi-tab signal analytics UI |
| `src/signal_analytics.py` | Signal analysis library — model loading, confusion matrices, action simulation |
| `src/quant_report.py` | Quant interpretation report generator |
| `src/news_data.py` | News sentiment ingestion — LLM-scored tech news features per ticker |
| `src/baseline_agents.py` | Supervised baseline policy wrappers (LR, RF, XGBoost) |

---

## Experiment Runner Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `scripts/evaluate_sweep.py` | Post-sweep evaluation — applies 6-gate promotion logic, computes clean CV over active seeds only |
| `scripts/run_exp9_walkforward.py` | Walk-forward backtest for SparseEnsemble Exp 9 validation. Per-ticker `use_stationary_features`, `sweep_label` filter |
| `scripts/backtest_exit_rules.py` | **ExitManager ablation** — val sweep across 14 rule configs → selects best → evaluates on test. Supports `--ticker {nvda,amd}`, `--config`, `--test-only`, `--voting-method`. **Bugs fixed 2026-05-16:** (1) Windows→Mac model_path remapping, (2) `run_label_filter` now wired from `ensemble_config.json`, (3) `_pick_market_cols` respects `use_stationary` flag (NVDA=10 cols, AMD=14 cols) |
| `scripts/analyze_exit_signals.py` | Analyzes ensemble exit signal diversity per ticker |
| `scripts/analyze_reward_divergence.py` | **12-section** diagnostic comparing NVDA vs AMD reward/exit divergence. Sections 1–8: cap, look-ahead, config, audit, performance, root cause, risk, recommendation. Sections 9–12: market regime, confidence distributions, per-seed breakdown, voting suppression. `--plot` flag generates `divergence_dashboard.png`. |
| `scripts/plot_divergence.py` | **6-panel dark dashboard PNG** (`data/audit/divergence_dashboard.png`). Panels: regime cumulative return, daily return violin, confidence distribution, val-Sharpe ablation, Phase 2B scorecard, signal composition. Run standalone or via `analyze_reward_divergence.py --plot`. |
| `scripts/reward_divergence_diagnostic.py` | Compact human-readable version of reward divergence analysis (sections 1–8 only) |
| `scripts/audit_exit_signals.py` | Per-bar exit signal audit — outputs `data/audit/exit_signal_sweep/*.csv` |
| `scripts/export_signals_for_dashboard.py` | Exports signal arrays for dashboard consumption |
| `scripts/generate_ensemble_config.py` | Generates `staging/models/ensemble_config.json` — label filter unreliable, manually maintained |
| `scripts/run_diagnostics.py` | Environment/feature sanity diagnostics |
| `scripts/sanitize_apply.py` | Applies model/data sanitization rules |

---

## Tests (`tests/`)

| File | Coverage |
|------|---------|
| `tests/test_e2e_reward_fix.py` | End-to-end reward fix validation |
| `tests/test_experiments_integration.py` | Full experiment loop integration |
| `tests/test_mps_acceleration.py` | MPS (Apple Silicon) GPU acceleration |
| `tests/test_reward_no_lookahead.py` | No look-ahead leakage in reward |
| `tests/test_signal_alignment.py` | Feature/observation alignment |
| `tests/test_weight_delta_cap.py` | Position weight delta cap enforcement |
| ❌ `tests/test_exit_manager.py` | **NOT YET WRITTEN** — ExitManager boundary conditions, reset(), exit-overrides-hold |

---

## Data & Artifacts

| Path | Purpose |
|------|---------|
| `data/tech_training_data_<ticker>.parquet` | Raw OHLCV training cache per ticker |
| `data/tech_training_data_<ticker>_stationary.parquet` | Pre-computed stationary feature cache |
| `data/experiment_leaderboard.csv` | Rolling master leaderboard — 1042 rows. Contains both Windows (`D:\code\...`) and Mac (`/Users/nettenz/...`) model_path values. Script remaps Windows paths at load time. |
| `data/experiment_snapshots/model_*.zip` | Trained model zips. Only Mac-native models (trained ≥ 2026-05-12) are physically present on disk. Windows-trained models referenced in old leaderboard rows do not exist locally. |
| `data/audit/exit_backtest/` | ExitManager backtest outputs: `{nvda,amd}_{val,test}_result*.csv`, `backtest_summary.md` |
| `data/audit/exit_signal_sweep/` | Per-bar exit signal analysis: `nvda_exit_audit.csv`, `amd_exit_audit.csv`, `exit_signal_summary.csv` |
| `data/audit/divergence_dashboard.png` | **6-panel divergence dashboard** generated by `scripts/plot_divergence.py` |
| `staging/models/ensemble_config.json` | **Manually maintained** — declares active_seeds, run_label, use_stationary_features per ticker. `generate_ensemble_config.py` label filter unreliable. |
| `staging/models/` | Production model zips (NVDA seeds 3,13,7,42; AMD seeds 13,21,7; MU seeds 21,3,13) |

---

## Observation Space Ground Truth

| Ticker | `use_stationary_features` | Market Cols | Obs Shape | Notes |
|--------|--------------------------|-------------|-----------|-------|
| NVDA | `False` | 10 (RAW_MARKET_COLS) | 18 | Raw parquet, no stationary preprocessing |
| AMD | `True` | 14 (STATIONARY_COLS) | ~22 | Stationary parquet |
| MU | `True` | 14 (STATIONARY_COLS) | ~22 | Stationary parquet |

> **Critical:** `backtest_exit_rules.py` must pass `use_stationary` to `_pick_market_cols()` to avoid feeding 14 cols to a 10-col model — this was the root cause of NVDA backtest producing avg_hold=1.0 bars and near-zero trade rates.

---

## Exit Signal State (May 2026)

| Phase | Status | Key Output |
|-------|--------|------------|
| Phase 1 — ExitManager implementation | ✅ Complete | `src/exit_manager.py`, wired into `src/ensemble.py` |
| Phase 2 — Backtest & tuning (Binary PPO) | ✅ Complete (re-run May 2026 against Binary PPO ensemble) | See results below |
| Phase 3 — Dashboard integration | ❌ Not started | Signal contract undefined, no `backend/signals/agent.py` |
| Phase 4 — Alpaca live feed | ❌ Not started | Dependent on Phase 3 |

### Phase 2 Backtest Results (Binary PPO ensemble — May 2026)

> **Note:** Previous Phase 2 results (documented pre-May-2026) used the old SAC ensemble. These results use the Binary PPO `nvda-ppo-minhold1-extended` ensemble and are not comparable to the SAC baseline.

**NVDA** (`nvda-ppo-minhold1-extended`, seeds 3/13/7/42, voting method):

| Config | Val Sharpe | Val ExitRate | Val Trades | Val WinRate |
|--------|-----------|-------------|-----------|------------|
| profit_take_8pct | **0.673** | 0.5% | 75 | 57.3% |
| profit_take_2pct | 0.636 | 6.1% | 73 | 56.2% |
| profit_take_3pct | 0.636 | 3.8% | 73 | 56.2% |
| no_exit (baseline) | 0.588 | 0.0% | 76 | 56.6% |

Selected by val sweep (highest Sharpe within exit_rate [0.02, 0.15]): **`profit_take_2pct`**

| Config | Test Sharpe | Test MaxDD | Test CumRet | Test ExitRate | AvgHold | WinRate |
|--------|------------|-----------|------------|--------------|---------|---------|
| profit_take_2pct ✅ | 0.061 | -15.9% | -0.7% | 4.4% | 1.2 bars | 53.7% |
| **no_exit (baseline)** | **0.301** | -16.1% | +6.6% | 0.0% | 1.2 bars | 56.1% |

> 🚨 **Critical finding (2026-05-16):** `profit_take_2pct` DEGRADES vs no_exit: Sharpe −0.240, CumRet −7.3pp, WinRate −2.4pp. The exit rule is net-negative in the 2024–2026 NVDA bull regime. Do NOT deploy. Consider wider thresholds (10–15%) or trailing_stop on a new val sweep.

> `BASELINES` dict in `scripts/backtest_exit_rules.py` updated 2026-05-16 — now uses Binary PPO no_exit actuals; success criteria are now relative (delta-Sharpe, ±2pp drawdown, exit_rate [0.02,0.15], win_rate non-regression).

**AMD** — not yet re-run against Binary PPO ensemble. Old SAC results still in `EXIT_SIGNAL_TODO.md`.

---

## Key Dependency Graph

```
market_data.py
  └─→ feature_engineering.py  (compute_stationary_features)
  └─→ news_data.py             (sentiment features)

trading_env.py
  └─ depends on: raw OHLCV + stationary features from market_data
  └─ binary_actions=True, min_hold_bars per ticker

experiments.py (Binary PPO training)
  └─→ market_data.py
  └─→ trading_env.py           (TradingEnv, Discrete(2) action space)
  └─→ signal_analytics.py      (post-run metrics)

ensemble.py ← trading_agent.py ← (live inference)
exit_manager.py ← ensemble.py   (exit override layer)
signal_analytics.py ← analytics_dashboard.py  (Streamlit UI)

scripts/backtest_exit_rules.py
  └─→ src/ensemble.py          (SparseEnsemble)
  └─→ src/exit_manager.py      (ExitManager)
  └─→ src/trading_env.py       (TradingEnv for simulation)
  └─→ staging/models/ensemble_config.json  (active seeds + run_label)
  └─→ data/experiment_leaderboard.csv      (model_path lookup)

scripts/analyze_reward_divergence.py  [--plot]
  └─→ data/experiment_leaderboard.csv      (reward config comparison)
  └─→ staging/models/ensemble_config.json  (active seed lookup)
  └─→ data/audit/exit_signal_sweep/        (confidence + audit CSVs)
  └─→ data/tech_training_data_*.parquet    (regime comparison)
  └─→ scripts/plot_divergence.py           (dashboard PNG, via --plot flag)

scripts/plot_divergence.py  (standalone or called via --plot)
  └─→ data/tech_training_data_*.parquet    (regime / return distribution)
  └─→ data/audit/exit_signal_sweep/        (confidence dist, voting)
  └─→ data/audit/divergence_dashboard.png  (OUTPUT)
```

---

## Promotion Gate Reference (6/6 required)

| Gate | Metric | Threshold | Notes |
|------|--------|-----------|-------|
| 1 | `test_actionable_accuracy` | ≥ 0.525 | Lowered for Binary PPO |
| 2 | `test_trade_win_rate` | ≥ 0.50 | Lowered for Binary PPO |
| 3 | `test_alpha_vs_qqq` | ≥ 0.0005 | Alpha-first |
| 4 | `\|val_acc - test_acc\|` | ≤ 0.05 | |
| 5 | `test_return_cv_by_config` | < 0.50 | PPO stability |
| 6 | `test_trade_rate` | ∈ [0.40, 1.00] | Gate 6 ceiling waivable for confirmed momentum tickers |

---

## Open Work Items

| Priority | Item | File |
|----------|------|------|
| ✅ | Capture NVDA no_exit test baseline | Done — Sharpe=0.301, MaxDD=-16.1%, CumRet=+6.6% |
| ✅ | Update `BASELINES` dict + success criteria | Done — relative to no_exit, SAC-era removed |
| 1 | Re-run AMD exit backtest against Binary PPO ensemble | `scripts/backtest_exit_rules.py --ticker amd` |
| 2 | Reassess NVDA exit strategy (profit_take_2pct degrades) | Consider wider thresholds or trailing_stop val sweep |
| 3 | Write ExitManager unit tests | `tests/test_exit_manager.py` |
| 4 | Define Phase 3 signal contract | Cross-repo payload: `{date, action, confidence, exit_fired, exit_rule}` |
| 5 | Create `backend/signals/agent.py` | Per-ticker feature pipeline routing (NVDA=raw, AMD=stationary) |
| 6 | Update `PPO_BINARY_STRATEGY.md` | Still shows NVDA/AMD as `[ ]` retrofit — both are ✅ promoted |
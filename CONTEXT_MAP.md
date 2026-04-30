# Context Map — Reinforcement Learning Stocks

**Generated:** 2026-04-30  
**Phase:** Base Architecture Grounding & Live Alpha Tuning  
**Goal:** Train multi-ticker SAC RL agents to beat QQQ benchmark using stationary features and sparse episodic rewards. Current blocker: overtrade friction on NVDA destroying alpha.

---

## Core Source Files (`src/`)

| File | Purpose |
|------|---------|
| `src/trading_env.py` | Gymnasium `TradingEnv` — the RL environment. Implements `PositionManager` for portfolio math, fractional shares, spread/slippage, and `next_bar` execution to prevent look-ahead leakage |
| `src/feature_engineering.py` | `compute_stationary_features()` — 14 stationary technical indicators (LogReturn, RelVWAP, RelATR, MACD_Signal_Rel, etc.) computed from OHLCV. Ground truth for observation space |
| `src/market_data.py` | Data ingestion via `yfinance`. Builds training frames, handles interval normalization, caches `.parquet` files, routes to feature engineering and news data |
| `src/experiments.py` | Core walk-forward experiment runner — orchestrates data loading, train/val/test splits, parallelized SAC training, out-of-sample simulation, 5-gate promotion evaluation, and leaderboard sync |
| `src/train_bot.py` | Standalone training entry point — thin wrapper over `experiments.py` for single-ticker training runs |
| `src/ensemble.py` | `SparseEnsemble` — loads multiple SAC seeds from a leaderboard CSV, filters collapsed seeds, ranks by Sharpe, performs majority-vote/averaging inference |
| `src/trading_agent.py` | `EnsembleAgent` — stateless live inference wrapper around `SparseEnsemble`. Reads `ensemble_config.json`, validates production-readiness flag per ticker |
| `src/analytics_dashboard.py` | Streamlit dashboard — multi-tab signal analytics UI consuming `signal_analytics.py` and Altair charts |
| `src/signal_analytics.py` | Core signal analysis library — model loading, observation alignment, confusion matrices, action simulation for single agents and ensembles |
| `src/quant_report.py` | Automated quant interpretation report generator — reads leaderboard CSVs, outputs professional markdown analysis with stats and next-step recs |
| `src/news_data.py` | News sentiment ingestion — fetches and caches LLM-scored tech news sentiment features per ticker |
| `src/baseline_agents.py` | Supervised baseline policy wrappers (LR, RF, XGBoost) compatible with the trading env `predict()` interface for Stage 1 signal validation |
| `src/supervised_baseline.py` | Stage 1 supervised regression baseline — predicts next-step returns and converts to a trading policy |
| `src/supervised_baseline_classification.py` | Stage 1 supervised classification baseline — class-probability proxy for gate-compatible metrics |
| `src/buyhold_benchmark.py` | Buy-and-hold decision gate comparison against supervised baseline across rolling windows |
| `src/rolling_window_validation.py` | Rolling walk-forward validation for Stage 1 — tests signal robustness across market regimes |
| `src/stage2_h1_runner.py` | Stage 2 Hypothesis 1 — LogisticRegression/RandomForest classifier for cross-sectional signal |
| `src/stage2_h2_runner.py` | Stage 2 Hypothesis 2 — Directional classification with RF/RF regressor variant |
| `src/stage2_h3_runner.py` | Stage 2 Hypothesis 3 — Spearman rank-correlation signal with `RandomForestRegressor` |
| `src/stage2_h4_runner.py` | Stage 2 Hypothesis 4 — Concentration-capped cross-sectional ranking (fork of H3) |

---

## Experiment Runner Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `scripts/run_diagnostics.py` | Environment/feature sanity diagnostics |
| `scripts/run_exp9_walkforward.py` | Walk-forward backtest for SparseEnsemble validation |
| `scripts/generate_ensemble_config.py` | Generates `staging/models/ensemble_config.json` from leaderboard CSVs |
| `scripts/sanitize_apply.py` | Applies model/data sanitization rules from quarantine reports |
| `scripts/sanity_scan.py` | Scans experiment results for anomalies and produces quarantine reports |
| `scripts/prepare_refinement_context.py` | Prepares context bundles for LLM-assisted experiment analysis |
| `scripts/check_output.py` | Quick leaderboard output inspector |
| `scripts/research/analyze_finalist.py` | Post-hoc analysis on finalist/champion seeds |
| `scripts/research/analyze_rewards.py` | Reward signal diagnostic plots |
| `scripts/archive/` | All superseded experiment launch scripts (PowerShell + Python), organized by date batch |

---

## Tests (`tests/`)

| File | Coverage |
|------|---------|
| `tests/test_e2e_reward_fix.py` | End-to-end reward fix validation |
| `tests/test_event_research_pipeline.py` | Event research data ingestion pipeline |
| `tests/test_experiments_integration.py` | Full experiment loop integration |
| `tests/test_mps_acceleration.py` | MPS (Apple Silicon) GPU acceleration |
| `tests/test_reward_no_lookahead.py` | Asserts no look-ahead leakage in reward computation |
| `tests/test_signal_alignment.py` | Feature/observation alignment correctness |
| `tests/test_weight_delta_cap.py` | Position weight delta cap enforcement |

---

## Data & Artifacts (`data/`, `models/`, `results/`, `staging/`, `reports/`)

| Path | Purpose |
|------|---------|
| `data/tech_training_data_<ticker>.parquet` | Raw OHLCV training cache per ticker |
| `data/tech_training_data_<ticker>_stationary.parquet` | Pre-computed stationary feature cache |
| `data/tech_news_sentiment_<ticker>.csv` | Cached LLM-scored news sentiment per ticker |
| `data/exp_1_nvda_10seed_foundation_*` | Exp 1 NVDA 10-seed leaderboard + snapshots |
| `data/exp_2_aapl_10seed_foundation_*` | Exp 2 AAPL 10-seed leaderboard + snapshots |
| `data/exp_3_amd_10seed_foundation_*` | Exp 3 AMD 10-seed leaderboard + snapshots |
| `data/experiment_leaderboard*.csv` | Rolling master leaderboards (daily + intraday variants) |
| `models/` | Saved model zips organized by experiment stage (stage1–stage2_h4, plus root ppo/sac zips) |
| `staging/models/` | Production-ready model zips per ticker (AAPL/AMD/NVDA top seeds) |
| `staging/models/ensemble_config.json` | Ensemble config declaring production-ready tickers and top seeds |
| `staging/src/` | Frozen snapshot of src files at last staging gate |
| `staging/metrics/` | Per-ticker leaderboard CSVs at staging time |
| `results/` | Stage 1–2 hypothesis output directories |
| `reports/` | Sanity scan and quarantine JSON reports |

---

## Event Research (`event-research/`)

| Path | Purpose |
|------|---------|
| `event-research/scripts/run_pipeline.py` | Main event research ingestion pipeline |
| `event-research/scripts/smoke_test.py` | Smoke test for pipeline integrity |
| `event-research/data/raw/` | Raw event data files |
| `event-research/config/` | YAML configs: `labels.yaml`, `sessions.yaml`, `sources.yaml`, `tickers.yaml` |
| `event-research/schemas/` | JSON schemas: event panel, event table, news raw/normalized |

---

## Documentation (`docs/`, root `.md` files)

| File | Purpose |
|------|---------|
| `PROJECT_STATE.md` | **Current authoritative state** — phase, feature engineering ground truth, NVDA overtrade diagnosis, next steps |
| `STAGE1_GUIDE.md` | Stage 1 signal-first pivot guide and gate definitions |
| `QUICK_REFERENCE.md` | Experiment execution checklist, promotion gates, key metrics snippets |
| `docs/HANDOFF.md` | AI handoff document (compact project summary for next session) |
| `docs/TIER2_EXECUTION_PLAN.md` | Tier 2 / RL training execution checklist |
| `docs/ENVIRONMENT_REALISM_AUDIT_2026_04_02.md` | Environment realism audit results |
| `docs/SANITIZE_APPLY_GUIDE.md` | Guide for applying model sanitization |
| `docs/INDEX.md` | Documentation index |
| `docs/archive/` | Superseded planning docs and handoffs from prior sessions |
| `sessions/` | Per-session quant reports and analysis notes (historical) |
| `sessions/CURRENT_IMPLEMENTATION_PLAN.md` | Active implementation plan |

---

## Key Dependency Graph

```
market_data.py
  └─→ feature_engineering.py  (compute_stationary_features)
  └─→ news_data.py             (sentiment features)

trading_env.py
  └─ depends on: raw OHLCV + stationary features from market_data

experiments.py
  └─→ market_data.py
  └─→ trading_env.py           (TradingEnv)
  └─→ signal_analytics.py      (post-run metrics generation)

ensemble.py ← trading_agent.py ← (live inference path)
signal_analytics.py ← analytics_dashboard.py  (Streamlit UI)
```

---

## Promotion Gate Definitions (5/5 required)

| Gate | Metric | Threshold |
|------|--------|-----------|
| 1 | `test_actionable_accuracy` | ≥ 0.53 |
| 2 | `test_trade_win_rate` | ≥ 0.52 |
| 3 | `test_alpha_vs_qqq` | ≥ 0.00 |
| 4 | `\|val_acc - test_acc\|` | ≤ 0.05 |
| 5 | `test_return_cv_by_config` | < 1.0 |

---

## Risk / Current Blockers

- **Active:** `sweep_overtrade_fix_nvda` sweep running — tuning `reward_hold_penalty_scale` down and `reward_turnover_penalty_scale` up to drop trade rate from 99.5% → 60–75%
- **Gate status:** 4/5 promotion gates pass; **Test Alpha** gate fails (agent overtrading against QQQ trend)
- **NVDA baseline:** CV = 0.0683 (excellent stability), val/test drift = 0.0025, win rate 54%+ — only alpha blocked by overtrade drag
- **Next action:** Evaluate sweep leaderboard → promote champion → integrate into `EnsembleAgent` in `src/trading_agent.py`
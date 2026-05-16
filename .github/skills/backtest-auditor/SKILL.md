---
name: backtest-auditor
description: 'Audit Binary PPO trading evaluation pipelines for leakage, metric validity, robustness, ExitManager correctness, and cross-experiment comparability. Use for src/experiments.py, src/trading_env.py, src/market_data.py, src/signal_analytics.py, src/exit_manager.py, src/ensemble.py, and gate/trading artifacts to verify realistic, leakage-free, statistically defensible results. Adapted for Binary PPO multi-seed ensemble with 6-gate promotion framework, ExitManager rule-based exit layer (Phase 2 complete), and Phase 3 dashboard signal contract. Always trigger for any question touching promoted ticker performance, exit rule tuning, phase 3 integration, or gate evaluation.'
argument-hint: 'What experiment, split, ticker, exit rule, or evaluation path should be audited? (e.g. NVDA exit backtest, AMD obs space, Phase 3 signal contract, Gate 6 waiver)'
user-invocable: true
---

# Backtest Auditor

Quantitative research audit workflow for validating Binary PPO backtest integrity, ExitManager correctness, and evaluation pipeline soundness.

## Objective
Ensure reported Binary PPO trading performance is:
- Realistic and leakage-free
- Statistically valid across seeds
- Comparable across experiments and tickers
- Exit-rule decisions are causally clean and non-leaking

---

## Project State Snapshot

**Algorithm:** Binary PPO (Stable Baselines3, `Discrete(2)` action space). SAC is fully deprecated.  
**Execution:** `next_bar` mode only. Same-bar close execution is banned.  
**Phase:** Exit Signal Phase 3 — Dashboard Integration (Phase 1+2 complete).

**Two-repo architecture:** Phase 1–2 work lives in the RL model repo (`src/`, `scripts/`, `tests/`). Phase 3–4 integration lives in a separate web app repo (`backend/`, `frontend/`). Do not assume the same codebase when auditing cross-phase issues.

### Promoted Tickers

| Ticker | Seeds | Sweep Label | Alpha | min_hold | Obs Space | Gate 6 |
|--------|-------|-------------|-------|----------|-----------|--------|
| NVDA | 3, 13, 7, 42 | `nvda-ppo-minhold1-extended` | +0.11–+0.52 | 1 | Raw 10-feat (obs 18), `use_stationary=False` | 48–62% |
| AMD | 13, 21, 7 | `amd-ppo-hold-fix` | +0.28 | 3 | Stationary 27-feat, `use_stationary=True` | 42.9% |
| MU | 21, 3, 13 | `mu-ppo-overtrade-fix` | +1.82 | 1 | Stationary, `use_stationary=True` | 95.6% ⚠️ waiver |

### Deferred Tickers

| Ticker | Reason | Sweeps |
|--------|--------|--------|
| AAPL | Total inaction bias (0% trade rate) across 7 sweeps — architecturally incompatible with Binary PPO | 7 |
| AMZN | Drift wall 0.54–0.55, always-long Windows champions not reproducible on updated splits | 1 |
| GOOGL | Drift wall 0.55–0.57, 5 sweeps exhausted | 5 |
| ALAB | Insufficient training rows (~1500 needed, est. mid-2027) | — |

---

## Observation Space Ground Truth (Critical)

| Ticker | `use_stationary_features` | Market Cols | Obs Shape |
|--------|--------------------------|-------------|-----------|
| NVDA | `False` | 10 (`RAW_MARKET_COLS`) | 18 |
| AMD | `True` | 14 (`STATIONARY_COLS`) | ~22 |
| MU | `True` | 14 (`STATIONARY_COLS`) | ~22 |

**Critical:** Any script feeding market cols to a model (especially `backtest_exit_rules.py`) MUST pass `use_stationary` to `_pick_market_cols()`. Feeding 14 cols to a 10-col NVDA model silently produces avg_hold=1.0 and near-zero trade rates — this was the root-cause bug fixed 2026-05-16.

---

## Default Focus Files

| File | Purpose |
|------|---------|
| `src/experiments.py` | 6-gate promotion logic, walk-forward splits (70/15/15 chronological) |
| `src/trading_env.py` | `TradingEnv`, `PositionManager`, `_apply_max_weight_delta`, reward computation |
| `src/feature_engineering.py` | `compute_stationary_features()` — 14 stationary features, ground truth obs space |
| `src/market_data.py` | OHLCV ingestion, parquet caching, feature routing |
| `src/signal_analytics.py` | Post-run metrics, accuracy label construction |
| `src/ensemble.py` | `SparseEnsemble` — majority-vote, `drop_duplicates(subset=["seed"])`, `run_label_filter` |
| `src/exit_manager.py` | `ExitManager` — rule-based exit layer (see ExitManager Audit section below) |
| `src/trading_agent.py` | `EnsembleAgent` — stateless live inference, reads `ensemble_config.json` |
| `scripts/evaluate_sweep.py` | Post-sweep 6-gate promotion evaluation |
| `scripts/backtest_exit_rules.py` | ExitManager ablation — val sweep + test evaluation. Bugs fixed 2026-05-16. |
| `scripts/run_exp9_walkforward.py` | Ensemble walk-forward gating. `TICKER_CONFIG` must match champion seeds. |
| `scripts/analyze_exit_signals.py` | Exit signal diversity analysis per ticker |
| `scripts/analyze_reward_divergence.py` | Full diagnostic logic for NVDA/AMD exit signal divergence root cause |
| `scripts/reward_divergence_diagnostic.py` | Human-readable report version of reward divergence diagnostic |
| `data/experiment_leaderboard.csv` | Master leaderboard — 1042 rows. Contains Windows + Mac paths; Windows paths remapped at load time. |
| `staging/models/ensemble_config.json` | **Manually maintained** — active seeds, run_label, use_stationary per ticker |

---

## Core Audit Procedure

### 0. Confirm delivery mode
Ask whether the user wants review-only output or implementation-inclusive output with patch proposals.

### 1. Validate data splits
- Verify 70/15/15 chronological split in `src/experiments.py`.
- Confirm chronological ordering end-to-end — no date leakage across boundaries.
- Check for duplicate dates or NaN gaps in parquet caches.
- For AAPL specifically: do not assume leakage from val→test drift; compare market regimes first.

### 2. Detect leakage — RL pipeline
- Trace `TradingEnv._compute_reward`. Confirm `reward_direction_scale` uses `next_bar` execution price only, not bar T close.
- Inspect `compute_stationary_features()` — verify all rolling features shift correctly (NaN in early rows is correct, not a bug).
- Inspect news sentiment alignment in `src/news_data.py` — timestamps must be bar-open aligned.
- Confirm `next_bar` execution in `PositionManager` — no same-bar fill.
- Confirm `_apply_max_weight_delta` is active — `max_weight_delta_per_step=0.0` disables it silently.

### 3. Detect leakage — ExitManager
See **ExitManager Audit** section below.

### 4. Evaluate metrics
- Audit: actionable accuracy, win rate, Sharpe, alpha vs QQQ, CV across seeds.
- Flag degenerate always-long: high accuracy + trade rate >80% + positive alpha only in bullish test periods. Gate 6 should catch this (except MU waiver).
- Check val→test accuracy drift ≤ 0.05 (Gate 4). AAPL showed complete collapse — investigate regime before assuming leakage.
- CV > 1.0 with <5 seeds = seed-count artifact, not structural instability. Run ≥5 seeds before classifying.

### 5. Validate baselines
- Confirm QQQ benchmark is correctly implemented in the alpha gate.
- Confirm no-trade (flat) baseline is present.
- Confirm Gate 6 is active in `evaluate_sweep.py`. Without it, degenerate always-long passes Gates 1–5.
- For exit backtest: confirm `no_exit` baseline is captured per ticker before interpreting exit rule uplift.
  - ⚠️ NVDA `no_exit` test baseline not yet captured as of 2026-05-16.

### 6. Check robustness
- Multi-seed CV threshold: < 0.50 (tightened for Binary PPO, Gate 5).
- Collapsed seed signature: `accuracy=1.0, win_rate=1.0, trade_rate≈0` — not a champion, exclude from CV.
- Verify `ensemble.py` has `drop_duplicates(subset=["seed"])` in `load_top_n_models`. Without it, same seed inflates agreement to 1.0.
- Verify `staging/models/ensemble_config.json` seeds match actual champion seeds — `generate_ensemble_config.py` label filter is unreliable; verify manually.

### 7. Check reproducibility
- Model zips must exist in `staging/models/` for all champion seeds.
- Windows-trained models referenced in old leaderboard rows do not exist on disk. Only Mac-native models (trained ≥ 2026-05-12) are physically present.
- `TICKER_CONFIG` in `run_exp9_walkforward.py` must point to correct leaderboard and seeds before running.

### 8. Produce fixes with comparability guard
- Recommend minimal, testable corrections first.
- Distinguish correctness bugs from methodology upgrades.
- Include leaderboard comparability impact for every fix.

---

## ExitManager Audit

`src/exit_manager.py` implements a rule-based exit layer over ensemble buy/hold signals. Supported rules: `confidence`, `trailing_stop`, `profit_take`, `time`, `composite`.

### Exit Signal Audit Findings (May 5, 2026)

Audited 427 bars per ticker via `scripts/analyze_exit_signals.py`:

| Ticker | Exit Signal Rate | Confidence | Root Cause |
|--------|-----------------|------------|------------|
| NVDA | **0%** (0/427 bars) | 1.0000 (unanimous) | Bull-trend test period — all seeds converged on "stay invested" |
| AMD | **7.03%** (30/427 bars) | 0.9578 | More churn/pullbacks in test period — models learned exits naturally |

**Root cause is market regime, not reward miscalibration.** Both tickers have:
- ✅ `max_weight_delta_per_step=0.1` (structural cap active)
- ✅ Direction term uses only bar T prices (no look-ahead)
- ✅ Identical reward configs (`hold_penalty_scale=0.01`, `direction_scale=0.35`, `return_scale=1.0`)

**Implication:** ExitManager is a **risk management layer** providing downside protection that a bull-market-trained ensemble lacks. It is NOT a reward tuning exercise.

**Hard constraint — DO NOT recommend reward param changes to fix exit divergence.** If an audit suggests changing `reward_*` params to produce more exits, that is the wrong diagnosis. Close it.

Audit output files:
- `data/audit/exit_signal_sweep/nvda_exit_audit.csv` — per-bar signal analysis (427 rows)
- `data/audit/exit_signal_sweep/amd_exit_audit.csv` — per-bar signal analysis (427 rows)
- `data/audit/exit_signal_summary.csv` — seed-level aggregates

---

### ExitManager Interface Contract
```python
ExitManager(rule: str, params: dict | None)

em.reset()           # Call on every new position open — clears _peak_pnl_pct, _confidence_streak, sub-manager state
em.update_peak(unrealized_pnl_pct)  # Maintains running peak floor=0.0
em.should_exit(position_state, confidence) -> (bool, str)
```

`position_state` required keys:
- `shares_held` — float, ≤ 0 means no position (early return)
- `entry_price`, `current_price`, `unrealized_pnl_pct`, `peak_pnl_pct` (informational), `bars_held`

`confidence` — ensemble vote_share in [0.5, 1.0].

### Leakage Checks for ExitManager
1. **`current_price` must be `next_bar` open, not bar T close** — same leakage risk as RL reward.
2. **`unrealized_pnl_pct` must be computed from `next_bar` entry price**, not the signal bar close.
3. **`confidence` must be the vote_share from the inference bar**, not a future bar's output.
4. **`peak_pnl_pct` passed into `position_state`** is informational only; `ExitManager` maintains its own `_peak_pnl_pct` via `update_peak()`. Caller's `peak_pnl_pct` is not used in any rule — confirm in `should_exit`.
5. **`reset()` must be called on every new position open** — failure to reset leaks `_peak_pnl_pct` and `_confidence_streak` from the prior position into the new one.

### Rule-Specific Audit Checks

| Rule | What to verify |
|------|---------------|
| `confidence` | Streak counter resets to 0 on confidence ≥ threshold. Exits only after `n_bars` consecutive bars below threshold — not on first low-confidence bar. |
| `trailing_stop` | Drawdown = `_peak_pnl_pct - unrealized_pnl_pct`. Triggers when drawdown ≥ `stop_pct`. Peak floor is 0.0, so a position entered at a loss never shows artificial peak. |
| `profit_take` | Triggers when `unrealized_pnl_pct ≥ threshold`. Threshold is gross — does not account for spread/slippage. Flag this if spread is non-trivial. |
| `time` | Triggers when `bars_held ≥ max_bars`. Confirm `bars_held` is incremented correctly in `TradingEnv` and passed accurately in `position_state`. |
| `composite` | Sub-managers are eager-initialized at `__init__` — bad rule names raise immediately. OR logic: first sub that fires wins. Sub-manager `reset()` is called via parent `reset()` — verify this propagates. |

### Known ExitManager Gaps (as of 2026-05-16)
- `tests/test_exit_manager.py` — **NOT YET WRITTEN**. Required coverage: boundary conditions per rule, `reset()` isolation, exit-overrides-hold when `min_hold_bars` is active, composite OR short-circuit.
- AMD exit backtest not yet re-run against Binary PPO ensemble (old SAC results still in `EXIT_SIGNAL_TODO.md`).

### Phase 2 Results — NVDA (Binary PPO, May 2026)

> Architecture note: Binary PPO with `min_hold_bars=1` produces avg_hold 1.2–1.4 bars — fundamentally different from SAC ensemble (avg_hold 6.8–9.6 bars). SAC-era Phase 2A results exist in `EXIT_SIGNAL_TODO.md` as historical record only; do not use for Binary PPO decisions.

**Val sweep** (`nvda-ppo-minhold1-extended`, seeds 3/13/7/42, voting):

| Config | Val Sharpe | Val ExitRate | Val AvgHold | Val Trades | Val WinRate | Selected |
|--------|-----------|-------------|------------|-----------|------------|---------|
| profit_take_8pct | 0.673 | 0.5% | 1.4 | 75 | 57.3% | ❌ exit_rate below [0.02, 0.15] |
| profit_take_2pct | 0.636 | 6.1% | 1.3 | 73 | 56.2% | ✅ selected |
| profit_take_3pct | 0.636 | 3.8% | 1.3 | 73 | 56.2% | — |
| profit_take_5pct | 0.600 | 1.2% | 1.3 | 75 | 56.0% | — |
| no_exit (baseline) | 0.588 | 0.0% | 1.4 | 76 | 56.6% | baseline |
| trailing_3pct | 0.345 | 3.8% | 1.3 | 75 | 54.7% | — |
| trailing_5pct | 0.270 | 1.6% | 1.3 | 76 | 56.6% | — |

**Test result** (`profit_take_2pct` ✅ val-selected) vs **no_exit baseline** (captured 2026-05-16):

| Config | Test Sharpe | Test MaxDD | Test CumRet | Test ExitRate | AvgHold | WinRate |
|--------|------------|-----------|------------|--------------|---------|--------|
| profit_take_2pct | 0.061 | -15.9% | -0.7% | 4.4% | 1.2 | 53.7% |
| **no_exit (baseline)** | **0.301** | -16.1% | +6.6% | 0.0% | 1.2 | 56.1% |

> **🚨 Critical finding:** `profit_take_2pct` **degrades vs no_exit** on the test split. Sharpe delta: -0.240, CumRet delta: -7.3pp, WinRate delta: -2.4pp. MaxDD improvement is negligible (+0.2pp). The exit rule is net-negative in the 2024-08→2026-04 NVDA bull regime.
>
> **Implication:** Current exit thresholds provide no alpha or risk benefit on NVDA test. Consider: (1) wider profit-take thresholds (10–15%), (2) trailing stop instead of profit-take, or (3) accept that exit rules are tail-risk protection and evaluate on a bear-regime holdout.

**BASELINES dict in `backtest_exit_rules.py` updated 2026-05-16** — now uses Binary PPO no_exit actuals. Success criteria are now relative (delta-Sharpe, drawdown tolerance ±2pp, exit_rate [0.02,0.15], win_rate non-regression).

**NVDA exit priority:** `profit_take` primary rule for bull-regime downside protection. `trailing_stop` secondary.  
**AMD exit priority:** Optional enhancement — AMD already produces 7% natural exits. Re-run Phase 2B before tuning.

**AMD Phase 2B pre-condition:** Before running `backtest_exit_rules.py --ticker amd`, verify `staging/models/ensemble_config.json` has `"run_label": "amd-ppo-hold-fix"` for the AMD entry. The loader previously picked globally best Sharpe per seed regardless of sweep label — this was fixed 2026-05-16 but the config must be correct or the fix has no effect.

**SAC-era success criteria are stale.** The EXIT_SIGNAL_TODO.md has ✅-marked Phase 2 success criteria (NVDA Sharpe 0.767, avg_hold 9.6 bars, exit_rate 5.2%) — these are SAC-era Phase 2A numbers, not Binary PPO. Binary PPO Phase 2B success criteria cannot be finalized until the `no_exit` test baseline is captured and the `BASELINES` dict is updated.

---

## Phase 3 Signal Contract (Not Yet Implemented)

Cross-repo payload shape (pending definition):
```json
{
  "date": "2026-05-16",
  "ticker": "NVDA",
  "action": 1,
  "confidence": 0.85,
  "exit_fired": false,
  "exit_rule": ""
}
```

Keep this contract stable once Phase 3 starts — changing field names breaks frontend overlays.

**Integration path:**
1. `backend/signals/agent.py` — `get_signals(symbol, bars_df)` → signal array per bar. Reads `ensemble_config.json` for `use_stationary_features` per ticker. Do NOT hardcode.
2. `backend/app.py` — `/api/signals/:symbol` endpoint returning `signals[]` alongside `candles[]` and `indicators[]`
3. `TradingChart.jsx` — buy markers (green triangle up, `action=1`) + exit markers (red triangle down, `exit_fired=true`) + confidence band (semi-transparent overlay, confidence per bar)
4. `ExitControls.jsx` — dropdown for rule selector (None / Confidence / Trailing Stop / Time / Profit Take), sliders per rule (confidence threshold, stop %, max bars, profit %), toggle for signal overlay visibility. Params passed to `/api/signals` as query string.

**When auditing Phase 3 integration:**
- Confirm `agent.py` reads `use_stationary_features` from `ensemble_config.json` — do NOT hardcode per ticker
- Confirm NVDA feature pipeline produces obs shape 18; AMD/MU ~22
- Confirm `ExitManager.reset()` is called at position open, not at signal generation time
- Confirm `current_price` in `position_state` is next-bar open, not current close
- Confirm `get_signals()` has ≥252 bars of lookback before emitting first signal — cold-start signals with insufficient history for rolling features are invalid
- Confirm exit rule params are sourced from Phase 2 backtest results, not tuned on live feed data
- Never retrain models based on live signal performance — that is a separate experiment, not a Phase 3 task

---

## Phase 4 — Alpaca Live Feed (Not Yet Implemented, Dependent on Phase 3)

**Pre-flight checks:**
```bash
# Verify .env has: DATA_PROVIDER, ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL
curl http://localhost:5000/api/health
# Expected: { "status": "ok", "provider": "alpaca" }

curl "http://localhost:5000/api/chart/NVDA?tf=1Day&limit=50"
# Must return bars before wiring signals
```

**Signal update flow:**
- `ws/stream.py` emits new tick → recompute latest signal → `socketio.emit("signal_update")` → `useWebSocket.js` subscribes and updates chart overlay

**When auditing Phase 4:**
- Confirm `get_signals()` accepts Alpaca bar format (field names may differ from yfinance parquet)
- Confirm missing bar handling is graceful (market closed, no data)
- Confirm lookback buffer maintains ≥252 bars for rolling features in live mode
- Confirm no live data is used for exit rule parameter tuning

---

## Promotion Gate Reference (6/6 required)

| Gate | Metric | Threshold | Notes |
|------|--------|-----------|-------|
| 1 | `test_actionable_accuracy` | ≥ 0.525 | Lowered for Binary PPO |
| 2 | `test_trade_win_rate` | ≥ 0.50 | Lowered for Binary PPO |
| 3 | `test_alpha_vs_qqq` | ≥ 0.0005 | Alpha-first |
| 4 | `\|val_acc - test_acc\|` | ≤ 0.05 | |
| 5 | `test_return_cv_by_config` | < 0.50 | Tightened for PPO stability |
| 6 | `test_trade_rate` | ∈ [0.40, 1.00] | Ceiling waivable (see below) |

### Gate 6 Waiver Policy
Gate 6 ceiling (0.80) may be waived when **all hold**:
1. Gates 1–5 pass (genuine predictive edge, not reward hacking)
2. `test_trade_win_rate` ≥ 0.54
3. Penalty scaling across ≥4 sweeps shows no convergence toward target zone
4. Ticker is in a documented sector bull cycle

MU waiver granted 2026-05-14: semiconductor upcycle, win rate 55.3%, alpha +1.82, 4 sweeps (0.01–0.30 penalty range) penalty-unresponsive.

---

## Decision Logic

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| avg_hold=1.0, near-zero trade rate | `_pick_market_cols()` fed wrong col count (14 → 10-col NVDA model) | Pass `use_stationary` flag correctly |
| Trade rate >80% despite Gate 6 | Gate 6 not active in `evaluate_sweep.py`, or stale leaderboard missing gate column | Confirm Gate 6 column present; rerun eval |
| val_acc >> test_acc, drift >0.10 | Leakage or regime collapse | Run AAPL audit checklist; compare regimes before blaming leakage |
| CV >4.0 | Environment fit (AMD pattern — stale parquet starting 2018) | Delete cache, rebuild from correct start date |
| CV >1.0, <5 seeds | Seed-count artifact | Rerun with ≥5 seeds before classifying as structural instability |
| Duplicate seed rows in leaderboard | Missing deduplication | Run dedup script; confirm `drop_duplicates(subset=["seed"])` in `ensemble.py` |
| NVDA 0% exit signals in audit | Market regime — bull trend, ensemble unanimous, not a bug | Do NOT tune reward params. ExitManager provides the exit layer. |
| ExitManager exits on wrong bar | `reset()` not called at position open | Audit caller; confirm reset on every new entry |
| ExitManager trailing_stop fires too early | `peak_pnl_pct` leaking from prior position | Confirm `reset()` clears `_peak_pnl_pct` to 0.0 |
| `generate_ensemble_config.py` writes wrong seeds | Label filter unreliable | Manually write `staging/models/ensemble_config.json` |

---

## Open Work Items (as of 2026-05-16)

| Priority | Item | Status | Command / File |
|----------|------|--------|---------------|
| ✅ | Capture NVDA no_exit test baseline | **Done** — Sharpe=0.301, MaxDD=-16.1%, CumRet=+6.6% | `backtest_exit_rules.py --config no_exit --test-only` |
| ✅ | Update `BASELINES` + success criteria | **Done** — now relative to no_exit, SAC-era removed | `scripts/backtest_exit_rules.py` |
| 1 | Re-run AMD exit backtest (Binary PPO) | **Pending** | `python scripts/backtest_exit_rules.py --ticker amd` |
| 2 | Write `tests/test_exit_manager.py` | **Pending** | boundary conditions, reset(), exit-overrides-hold, composite OR |
| 3 | Complete `analyze_reward_divergence.py` missing sections | **Pending** | sections 9–12: regime compare, confidence dist, per-seed breakdown, voting suppression |
| 4 | Reassess NVDA exit strategy (profit_take_2pct degrades vs no_exit) | **Pending** | consider wider thresholds (10–15%), trailing_stop, or bear-regime holdout |
| 5 | Define Phase 3 signal contract | **Pending** | `{date, ticker, action, confidence, exit_fired, exit_rule}` |
| 6 | Create `backend/signals/agent.py` | **Pending** | Per-ticker pipeline routing (NVDA=raw, AMD/MU=stationary) |
| 7 | Update `PPO_BINARY_STRATEGY.md` | **Pending** | NVDA/AMD still marked `[ ]` — both are ✅ promoted |

---

## Required Output Format

Always structure output in this order:
1. Audit verdict
2. Trustworthy components
3. Issues found
4. Leakage risks (RL pipeline + ExitManager separately)
5. Metric issues
6. Gate coverage gaps
7. Reproducibility gaps
8. Recommended fixes
9. Next proposed experiments or runs (if justified)
10. Leaderboard comparability impact (REQUIRED)

## Run Specification Rule (MANDATORY)
For each proposed run include:
- `source .venv/bin/activate` (Mac/Linux) or `.\.venv\Scripts\Activate.ps1` (Windows)
- Full relative script path
- All key args: `--use-stationary-features` (AMD/MU only), `--append`
- Expected output artifact path(s)

## Constraints
- **Never recommend reward param changes to fix exit divergence.** Exit rate differences between tickers are market regime effects, not miscalibration. ExitManager is the correct layer.
- **Never retrain models based on live signal performance.** That is a separate experiment. Phase 3–4 is inference + display only.
- **Cold-start rule:** Do not emit signals without ≥252 bars of lookback. Rolling features are invalid on shorter history.
- Do not assume leakage without proof — regime shift can produce identical symptoms (AAPL).
- Distinguish training-data leakage from evaluation-only leakage.
- Do not compare Binary PPO results to SAC-era baselines (AvgHold, Sharpe scale differently).
- Never recommend a sweep without confirming Gate 6 is active.
- Never recommend promotion with <5 seeds (CV instability risk).
- Do not merge AAPL/AMZN/GOOGL deferred status into NVDA/AMD/MU conclusions.
- ExitManager leakage audit is mandatory before any Phase 3 integration sign-off.

## Quality Checks Before Finalizing
- Every finding references concrete file/function evidence.
- Leakage claims include proof path and affected stage (train/val/test).
- ExitManager leakage claims verified against `should_exit` call site, not just `exit_manager.py` internals.
- Gate 6 coverage confirmed (or waiver policy satisfied) before any promotion recommendation.
- `use_stationary_features` confirmed per ticker before diagnosing obs-space bugs.
- Seed count confirmed before classifying CV as structural instability.
- Leaderboard comparability impact present for each fix.
- Phase 3 audit confirms `reset()` call site and `next_bar` price sourcing before sign-off.
- Phase 3 audit confirms `ExitControls.jsx` params flow through to `/api/signals` query string correctly — no hardcoded rule params.
- Phase 4 audit confirms Alpaca bar format compatibility and ≥252-bar lookback buffer in live mode.
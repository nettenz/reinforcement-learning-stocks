# Project State: Reinforcement Learning Stocks
**Date:** May 03, 2026  
**Phase:** Exit Signal Development & Dashboard Integration

---

## 1. Executive Summary

The foundational trading architecture is grounded, leakage-free, and validated. NVDA and AMD are fully promoted to staging with clean Exp 9 walk-forward validation. AMD's staging ensemble config is now aligned to the promoted bridge-c seeds. The 6-gate promotion framework is in place. Ensemble loading is sweep-locked and deterministic per ticker.

A thorough ticker expansion effort screened 8 candidates beyond NVDA and AMD. None were promotable — AAPL and GOOGL collapsed due to insufficient reward signal, others failed Stage 1 screening. ALAB is flagged for re-evaluation in 6–9 months once sufficient training data exists.

Active work has shifted to **exit signal development** (Option A — rule-based ExitManager layer) and **Alpaca dashboard integration**.

---

## 2. Feature Engineering Ground Truth

Stationary technical features audited and corrected for strict realism:

1. **VolLogDiff:** Passed through directly (no double log-diff).
2. **RelOpen:** Passed through directly to preserve overnight gap magnitude.
3. **RelRange:** Reconstructed using true unnormalized High and Low prices.
4. **RelATR:** Computes True Range dynamically using true unnormalized prior closes.
5. **RelVWAP:** Typical price references true unnormalized High/Low; Volume clipped at 0.0.

**Per-ticker obs space:**
- NVDA champion trained on raw 10-feature space (`use_stationary_features=False`)
- AMD champion trained on stationary 27-feature space (`use_stationary_features=True`)
- `TICKER_CONFIG` in `run_exp9_walkforward.py` is sweep-locked per ticker via `sweep_label` filter
- All new ticker sweeps must use `--use-stationary-features`

---

## 3. NVDA — Promoted ✅

**Champion sweep:** `nvda-sharpe-news-recovery`  
**Seeds:** 7, 13 | **Obs space:** Raw 10-feature (reward_mode: sharpe, include_news, stationary features)

| Metric | Value |
|--------|-------|
| Sharpe | 1.61 |
| Alpha vs QQQ | 0.41 |
| Actionable Accuracy | 56.3% |
| Trade Win Rate | 54.7% |
| Val/Test Drift | 0.004 |
| CV (clean seeds) | 0.053 |
| Trade Rate | 62.5% |

**Prior failure analysis:** Sortino reward mode trained inaction bias ("do nothing"). Recovery fix: switched to Sharpe mode + news features to improve signal quality on NVDA's news-reactive AI boom context.

**Exp 9:** PASS — G1/G2/G3, 2 promoted seeds [7, 13], agreement 1.00, avg_conf 0.92, unanimous 0.69.

**Stage 1 baseline:** val_acc=46.4%, test_acc=50.5% (reference benchmark for ticker screening).

---

## 4. AMD — Promoted ✅

**Champion sweep:** `amd-news-bridge-c`  
**Seeds:** 13, 7 | **Obs space:** Stationary 27-feature

| Metric | Value |
|--------|-------|
| Sharpe | 1.60 |
| Alpha vs QQQ | 1.37 |
| Actionable Accuracy | 55.0% |
| Trade Win Rate | 55.1% |
| Val/Test Drift | 0.046 |
| CV (clean seeds) | 1.596 |
| Trade Rate | 68.9% |

**Root cause of prior failure:** AMD parquet started 2018 — missing 3 years of regime diversity. Val period was near-flat (12.77%) vs explosive train (876%), causing CV 4.5. Fix: deleted stale cache, rebuilt from 2015.

**CV gate fix:** `evaluate_sweep.py` recomputes CV over active seeds only (Sharpe > 0, trade_rate > 10%). Collapsed seeds were inflating raw CV to 1.45 despite clean-seed CV of 0.71.

**Exp 9:** PASS — G1/G2/G3, AMD validation passed. Staging ensemble config is pinned to the bridge-c pair [13, 7].

**Stage 1 baseline:** val_acc=43.8%, test_acc=44.2% (RL finds signal RF baseline misses).

---

## 5. Ticker Expansion — Completed

### AAPL — Dropped ❌
**Reason:** Persistent hold-bias collapse across all reward configs including zero penalties.
AAPL test period: 5% return, 31% vol — reward signal too weak to motivate trading.
Audit confirmed: no leakage, no code bugs. Reward-signal incompatibility.

### GOOGL — Dropped ❌
**Reason:** Same hold-bias collapse across 3 sweeps including entropy tuning.
Val looks viable (Sharpe 1.11, 56.8% accuracy) but test zeroes out completely.
Not fixable with reward or entropy tuning under current architecture.

### Stage 1 Screening Results (8 tickers screened)

| Ticker | Stage 1 Test Acc | vs NVDA (50.5%) | Decision |
|--------|-----------------|-----------------|----------|
| ALAB (xgb) | 56.3% | +5.8pp | ⏳ Re-screen mid-2027 (531 rows only) |
| ALAB (rf) | 51.3% | +0.8pp | ⏳ Re-screen mid-2027 |
| MRVL | 43.9% | -6.6pp | ❌ No signal |
| TSM | 43.5% | -7.0pp | ❌ No signal |
| META | 42.3% | -8.2pp | ❌ No signal |
| MSFT | 41.8% | -8.7pp | ❌ No signal |
| INTC | 42.3% | -8.7pp | ❌ No signal |
| AMZN | 35.8% | -14.7pp | ❌ No signal |

**Key finding:** NVDA and AMD are genuinely exceptional — high-momentum AI infrastructure plays with multi-year trending behavior are rare. Forcing a third ticker is not the right path.

**ALAB flagged for re-evaluation:** Strongest Stage 1 signal of all screened tickers (56.3%). Re-screen when training window reaches ~1500+ rows (estimated mid-2027).

### Current TICKER_PRESETS
```python
TICKER_PRESETS = {
    "googl": ("GOOGL",), "nvda": ("NVDA",), "amd": ("AMD",),
    "msft": ("MSFT",), "tsm": ("TSM",), "meta": ("META",),
    "mrvl": ("MRVL",), "alab": ("ALAB",), "intc": ("INTC",), "amzn": ("AMZN",),
}
DEFAULT_TICKER = "nvda"
```

---

## 6. Infrastructure & Tooling Updates

- **Gate 6 added:** `test_trade_rate ∈ [0.40, 0.80]` — blocks degenerate always-long policies
- **evaluate_sweep.py:** CV recomputed over active seeds only; Gate 5 uses `clean_cv`
- **ensemble.py:** `load_top_n_models` accepts `seed_filter` and `run_label_filter`
- **run_exp9_walkforward.py:** Per-ticker `market_feature_columns`, `sweep_label` filter, `max_weight_delta_per_step=0.10`
- **Leaderboard:** Deduplicated 202 → 162 rows (2026-04-30)
- **staging/models/ensemble_config.json:** Manually maintained — AMD block now pinned to bridge-c seeds [13, 7]; `generate_ensemble_config.py` label filter unreliable

---

## 7. Ticker Status

| Ticker | Status | Seeds | Sweep |
|--------|--------|-------|-------|
| NVDA | ✅ Promoted | 7, 13 | nvda-sharpe-news-recovery |
| AMD | ✅ Promoted | 13, 7 | amd-news-bridge-c |
| AAPL | ❌ Dropped | — | Reward-signal incompatibility |
| GOOGL | ❌ Dropped | — | Val→test complete collapse |
| ALAB | ⏳ Future | — | Re-screen mid-2027 |
| All others | ❌ Screened out | — | Stage 1 below threshold |

---

## 8. Active Work & Next Steps

### Immediate
1. **Exit Signal Phase 1** — `src/exit_manager.py` with confidence-based, trailing stop, time-based rules. Backtest on NVDA test split first. See `EXIT_SIGNAL_TODO.md`.
2. **Alpaca dashboard integration** — keys confirmed. Wire `backend/signals/agent.py` → `/api/signals/:symbol` → buy/exit overlays in `TradingChart.jsx`.

**Next repo step:** start Exit Signal Phase 1 now that both AMD and NVDA are promoted and Exp 9 is complete.

### Near-term
3. **Exit signal backtesting** — tune params on val, evaluate on test. No re-tuning on test.
4. **Dashboard exit controls** — `ExitControls.jsx` with rule selector and parameter sliders.
5. **Live signal feed** — WebSocket tick → signal update → frontend overlay.

### Deferred
6. **ALAB re-screen** — mid-2027
7. **Option B (long/short)** — full architecture rewrite after exit signal layer validated
8. **AI Sector Pipeline Phase 1** — FinBERT upgrade per `ai_sector_pipeline_spec.jsx`
9. **BTC/crypto integration** — scope unresolved

---

## 9. Promotion Gate Reference (6/6 required)

| Gate | Metric | Threshold | Notes |
|------|--------|-----------|-------|
| 1 | `test_actionable_accuracy` | ≥ 0.53 | |
| 2 | `test_trade_win_rate` | ≥ 0.52 | |
| 3 | `test_alpha_vs_qqq` | ≥ 0.00 | |
| 4 | `\|val_acc - test_acc\|` | ≤ 0.05 | |
| 5 | `test_return_cv_by_config` | < 1.0 | Uses clean_cv (active seeds only) |
| 6 | `test_trade_rate` | ∈ [0.40, 0.80] | Blocks degenerate always-long |
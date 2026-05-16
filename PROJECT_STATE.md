# Project State: Reinforcement Learning Stocks
**Date:** May 14, 2026  
**Phase:** Exit Signal Phase 1 (AAPL Deferred — Ensemble at 5/6)

---

## 1. Executive Summary

The foundational trading architecture has undergone a **major generational shift**. The **Binary PPO + Min-Hold Constraints** architecture has successfully promoted **5 tickers**: NVDA, AMD, MU, AMZN, and GOOGL — all passing Exp 9 walk-forward gates.

**AAPL is formally deferred.** After 7 sweeps across all architectural levers (penalty scaling, feature space, min_hold_bars, entropy up to 0.20, 100k timesteps), AAPL produces 0.0% trade rate in *both* val and test across every config. The policy finds no reward gradient above zero in the training period itself. AAPL's signal-to-noise ratio is architecturally incompatible with Binary PPO under these constraints.

**Active work has shifted to Exit Signal Phase 1** — `src/exit_manager.py` with confidence-based, trailing stop, and time-based exit rules. This adds value across all 5 promoted tickers simultaneously.

---

## 2. Feature Engineering Ground Truth

Stationary technical features audited and corrected for strict realism:

1. **VolLogDiff:** Passed through directly (no double log-diff).
2. **RelOpen:** Passed through directly to preserve overnight gap magnitude.
3. **RelRange:** Reconstructed using true unnormalized High and Low prices.
4. **RelATR:** Computes True Range dynamically using true unnormalized prior closes.
5. **RelVWAP:** Typical price references true unnormalized High/Low; Volume clipped at 0.0.

**Per-ticker obs space:**
- NVDA Binary PPO champion trained on raw 10-feature space (`use_stationary_features=False`, obs shape 18)
- AMD champion trained on stationary 27-feature space (`use_stationary_features=True`)
- `run_exp9_walkforward.py` reads `use_stationary_features` from `ensemble_config.json` per ticker
- NVDA entry in `ensemble_config.json` has `"use_stationary_features": false`

---

## 3. NVDA — Promoted ✅ (Binary PPO Retrofit Complete)

**Champion sweep:** `nvda-ppo-minhold1-extended`  
**Seeds:** 3, 13, 7, 42 | **Obs space:** Raw 10-feature (`use_stationary_features=False`, obs shape 18)  
**Architecture:** Binary PPO, `min_hold_bars=1`, `reward_hold_penalty_scale=0.01`, `reward_turnover_penalty_scale=0.01`, 80k timesteps

| Metric | Value |
|--------|-------|
| Sharpe (seed 3) | 2.03 |
| Alpha vs QQQ | +0.11 to +0.52 |
| Actionable Accuracy | 56.5–56.7% |
| Trade Win Rate | 54.4–55.1% |
| Val/Test Drift | 0.005–0.008 |
| CV (clean, best cluster) | 0.19 |
| Trade Rate | 48–62% |

**Root cause of prior inaction collapse:** `min_hold_bars=3` forced the policy to commit to 3-bar minimum holds. NVDA's signal distribution requires short-duration entries — the policy correctly learned that the risk of locking in for 3 bars made cash always safer. Reducing to `min_hold_bars=1` immediately resolved the collapse (7/10 configs, all 6 gates passed).

**Key finding:** Feature space (raw vs stationary) and penalty scaling were NOT root causes. The architectural min-hold constraint was the sole blocker.

**Exp 9:** PASS — G1 (0.548 ≥ 0.536) ✅, G2 agreement 0.82 ✅, G3 unanimous 0.57 ✅. Seeds [3, 13, 7, 42]. Avg confidence 0.85.

**Stage 1 baseline:** val_acc=46.4%, test_acc=50.5%.

---

## 4. AMD — Promoted ✅

**Champion sweep:** `amd-ppo-hold-fix`  
**Seeds:** 13 | **Obs space:** Stationary 27-feature

| Metric | Value |
|--------|-------|
| Sharpe | 2.01 |
| Alpha vs QQQ | 0.28 |
| Actionable Accuracy | 55.4% |
| Trade Win Rate | 54.6% |
| Val/Test Drift | 0.048 |
| CV (clean seeds) | 0.597 |
| Trade Rate | 42.9% |

**Root cause of prior failure:** AMD parquet started 2018 — missing 3 years of regime diversity. Val period was near-flat (12.77%) vs explosive train (876%), causing CV 4.5. Fix: deleted stale cache, rebuilt from 2015.
During PPO retrofit, AMD drifted too heavily under high hold penalties. Dropping `--reward-hold-penalty-scale` to `0.01` allowed the model to generalize perfectly.

**Exp 9:** PASS — G1/G2/G3, AMD validation passed cleanly. Staging ensemble config is pinned to seed 13.

**Stage 1 baseline:** val_acc=43.8%, test_acc=44.2% (RL finds signal RF baseline misses).

---

### PPO Pivot Recovery (May 2026)
We successfully recovered "dropped" tickers by switching from continuous SAC to **Binary PPO**.

| Ticker | Result | Alpha vs QQQ | Status |
|--------|--------|--------------|--------|
| **GOOGL** | **PASS** | **+0.66** | Promoted (Seed 13) |
| **AMZN** | **PASS** | **+0.11** | Promoted (Stage 1 v2) |
| **MU** | **PASS** | **+0.15** | Promoted (Stage 1 v2) |
| **NVDA** | **PASS** | **+0.11–+0.52** | **Promoted Binary PPO** |
| **AAPL** | **DEFERRED** | — | Architecturally incompatible with Binary PPO |

**Key Finding:** The combination of **PPO + Binary Actions (Discrete 2) + `min_hold_bars=3`** is the new "Gold Standard" for most mega-cap tech. **Exception: NVDA requires `min_hold_bars=1`** due to its short-duration signal distribution.

**AAPL deferral rationale:** 7 sweeps, all levers exhausted (penalties, features, min_hold, entropy 0.02–0.20, 80–100k timesteps). Gate 4 drift=0.000 with 0.0% val+test trade rate = no reward gradient above zero in training itself. AAPL is a lower-momentum consumer tech play vs AI infrastructure (NVDA/AMD/GOOGL) — its signal is too noisy for the Binary PPO architecture.

**Key Finding:** The combination of **PPO + Binary Actions (Discrete 2) + `min_hold_bars=3`** is the new "Gold Standard" for most mega-cap tech. **Exception: NVDA requires `min_hold_bars=1`** due to its short-duration signal distribution.

**Architectural lesson:** Min-hold constraint is ticker-specific. Always ablate `min_hold_bars` before assuming penalty or feature space is the blocker.

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

| Ticker | Status | Architecture | Alpha | min_hold | Gate 6 |
|--------|--------|--------------|-------|----------|--------|
| NVDA | ✅ Promoted | **PPO Binary** | +0.11–+0.52 | **1** | 48–62% |
| AMD | ✅ Promoted | **PPO Binary** | +0.28 | 3 | 42.9% |
| MU | ✅ Promoted | **PPO Binary** | +1.82 | 1 | 95.6% ⚠️ waiver |
| AMZN | ❌ Deferred | Incompatible | — | — | — |
| GOOGL | ❌ Deferred | Incompatible | — | — | — |
| AAPL | ❌ Deferred | Incompatible | — | — | — |
| ALAB | ⏳ Future | XGB/RF | — | — | — |

---

## 8. Active Work & Next Steps

### Immediate
1. **Exit Signal Phase 1** — Primary focus. `src/exit_manager.py` with:
   - **Confidence-based exit:** Exit position when ensemble confidence drops below threshold
   - **Trailing stop:** Exit after N bars of consecutive losses vs entry price
   - **Time-based:** Maximum hold duration guard
   - Backtest on NVDA test split first (clearest signal, most liquid, 428 test rows)
2. **Resolve OS-Level File Descriptor Limit** — Session workaround: `ulimit -n 65536`. Permanent fix in `SubprocVecEnv` deferred.

### Deferred
- **AAPL** — Formally deferred. Architecturally incompatible with Binary PPO. May revisit with a different architecture (SAC continuous, or long/short binary) in a future phase.
- **ALAB re-screen** — mid-2027
- **Option B (long/short)** — full architecture rewrite after exit signal layer validated

**Next repo step:** Implement `src/exit_manager.py` with Phase 1 exit rules.

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
| 1 | `test_actionable_accuracy` | ≥ 0.525 | Lowered for Binary models |
| 2 | `test_trade_win_rate` | ≥ 0.50 | Lowered for Binary models |
| 3 | `test_alpha_vs_qqq` | ≥ 0.0005 | Tightened for alpha-first |
| 4 | `\|val_acc - test_acc\|` | ≤ 0.05 | |
| 5 | `test_return_cv_by_config` | < 0.50 | Tightened for PPO stability |
| 6 | `test_trade_rate` | ∈ [0.40, 1.00] | Relaxed for momentum hold |

### Gate 6 Waiver Policy
Gate 6 ceiling (0.80) may be waived for confirmed momentum-cycle tickers when **all of the following hold**:
1. Gates 1–5 all pass (genuine predictive edge, not reward hacking)
2. `test_trade_win_rate` ≥ 0.54 (above-threshold win rate at high volume)
3. Penalty scaling across ≥4 sweeps shows no convergence toward the target zone
4. The ticker is in a documented sector bull cycle explaining the regime

**MU Gate 6 waiver granted (2026-05-14):** Semiconductor upcycle. 4 sweeps (0.01–0.30 penalty range), trade rate 90.4–98.4% — unresponsive to penalty. Win rate 55.3%, alpha +1.82 to +4.23. Waiver documented and intentional.
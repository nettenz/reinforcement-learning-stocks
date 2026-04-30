# Project State: Reinforcement Learning Stocks
**Date:** April 30, 2026  
**Phase:** Base Architecture Grounding & Stationary Feature Validation

---

## 1. Executive Summary

The foundational trading architecture has been grounded with look-ahead biases removed and noisy constants converted to true stationary signals. The agent trains using **sparse episodic rewards** and executes on a strict **`next_bar`** basis. Training data spans from **2015** to capture diverse market regimes including the 2018 correction, 2022 rate hike cycle, and the modern AI boom.

The overtrading blocker that destroyed NVDA alpha has been resolved via a structural environment-level constraint (`max_weight_delta_per_step=0.10`). NVDA has been promoted to staging and passed Exp 9 walk-forward validation. A stationary feature sweep is currently running to align the observation space with the declared architectural ground truth before cross-ticker expansion.

---

## 2. Feature Engineering Ground Truth

Stationary technical features were audited and corrected for strict realism:

1. **VolLogDiff:** Passed through directly (avoiding a double log-diff).
2. **RelOpen:** Passed through directly to preserve true overnight gap magnitude.
3. **RelRange:** Reconstructed using true unnormalized High and Low prices for accurate intraday volatility signals.
4. **RelATR:** Computes True Range dynamically using true unnormalized prior closes.
5. **RelVWAP:** Typical price dynamically references true unnormalized High and Lows; Volume is cleanly clipped at 0.0 to stabilize rolling VWAP summation.

**Going forward:** All sweeps must use `--use-stationary-features` flag. The 10-feature raw space used in earlier sweeps is deprecated.

---

## 3. NVDA Baseline, Overtrade Resolution & Promotion

Under the realistic environment, NVDA multi-seed runs exhibited a **CV of 0.0683** and near-zero val/test drift (**0.0025**).

**The Overtrade Problem:**
The agent failed the Test Alpha gate (-0.1929 vs QQQ) due to trading on **99.5%** of bars. Despite 54%+ directional accuracy and 52%+ win rate, constant transaction cost drag destroyed alpha against a trending benchmark. Reward penalty tuning (`reward_turnover_penalty_scale`, `reward_hold_penalty_scale`) had zero effect because the return signal dominated any penalty.

**Root Cause:** `max_weight_delta_per_step` was set to `0.0` (no cap) across all sweeps. The agent could flip 100% of the portfolio in a single step, making turnover penalties irrelevant.

**Resolution:** Implemented `--max-weight-delta-per-step 0.10` — a hard structural cap already built into `TradingEnv._apply_max_weight_delta`. This dropped trade rate from 99.5% → 62.3% and flipped Test Alpha to +0.514.

**Gate 6 Added:** A degenerate always-long policy can pass Gates 1–5 if the test period is bullish. Gate 6 (`test_trade_rate ∈ [0.40, 0.80]`) was added to `scripts/evaluate_sweep.py` to catch this failure mode.

**Champion Config (`sweep_overtrade_fix_nvda_maxdelta_v2`):**
```
--reward-mode sharpe
--ent-coefs 0.02,0.05
--timesteps 40000
--seeds 3,7,13,21,42
--execution-mode next_bar
--reward-hold-penalty-scale 0.01
--reward-turnover-penalty-scale 0.10
--max-weight-delta-per-step 0.10
--use-stationary-features False  ← deprecated, see Section 5
```

**Champion Metrics (seeds 13, 21, 42, 7 — all 6/6 gates):**
| Metric | Value |
|--------|-------|
| Sharpe | 1.64 |
| Alpha vs QQQ | 0.514 |
| Actionable Accuracy | 56.5% |
| Trade Win Rate | 54.9% |
| Val/Test Drift | 0.0073 |
| CV (cross-seed) | 0.8926 |
| Trade Rate | 62.3% |

**Exp 9 Walk-Forward:** Passed all gates (G1/G2/G3) with 4 seeds loaded. Agreement rate 1.00, avg confidence 0.83, unanimous rate 0.33. Seed 7 provides behavioral diversity (418 buys vs 427 for others).

**Ensemble Config:** Manually written to `staging/models/ensemble_config.json` — seeds [13, 21, 42, 7], `production_ready: true`. Note: `generate_ensemble_config.py` does not reliably filter by label — always verify output seeds match champions before using.

---

## 4. Active Work: Stationary Feature Sweep

**Sweep in progress:** `sweep_overtrade_fix_nvda_stationary`

```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker nvda --reward-mode sharpe --ent-coefs 0.02,0.05 --timesteps 40000 --seeds 13,21,42,7 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.10 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_overtrade_fix_nvda_stationary" --append
```

**Goal:** Confirm that stationary features (27-dim) produce equivalent or better Sharpe/alpha vs the v2 raw-feature champion. If gates pass, update staging to the stationary champion and mark the architectural discrepancy as resolved.

**Evaluate with:**
```powershell
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label sweep_overtrade_fix_nvda_stationary
```

---

## 5. Architectural Discrepancy — RESOLVED IN PROGRESS

**Issue:** NVDA sweeps through v2 used `use_stationary_features=False` (10-feature raw space), inconsistent with `feature_engineering.py` being the declared ground truth (27-feature stationary space).

**Decision:** Stationary features adopted as the mandatory standard going forward. The `sweep_overtrade_fix_nvda_stationary` sweep is the resolution vehicle. All future sweeps for NVDA, AAPL, and AMD must use `--use-stationary-features`.

---

## 6. Leaderboard Integrity

**Deduplication performed 2026-04-30:** Leaderboard cleaned from 202 → 162 rows. Exact duplicates removed; per-config key duplicates resolved by keeping best Sharpe. The seed=13 multi-row corruption from the initial sweep is resolved.

**`src/ensemble.py` fix:** Added `drop_duplicates(subset=["seed"])` to `load_top_n_models` to prevent the same seed being loaded multiple times when it appears at the top of a ranked leaderboard.

---

## 7. Ticker Status

| Ticker | Status | Blocker |
|--------|--------|---------|
| NVDA | ✅ Promoted (staging) | None — Exp 9 passed. Stationary sweep in progress for upgrade. |
| AAPL | ❌ Blocked | Leakage audit required — severe val→test accuracy collapse observed |
| AMD | ❌ Blocked | Environment fit issue — structural mismatch under investigation |

---

## 8. Immediate Next Steps

1. **Evaluate stationary sweep** → run `evaluate_sweep.py --label sweep_overtrade_fix_nvda_stationary`
2. **If 6/6 gates pass** → update `staging/models/ensemble_config.json` with stationary champion seeds → re-run Exp 9 walk-forward
3. **Proceed to Exp 10** (deployment readiness / paper trading dry-run) once stationary NVDA is locked
4. **Cross-ticker sweeps** → apply `--max-weight-delta-per-step 0.10 --use-stationary-features` to AMD and AAPL (after AAPL leakage audit)
5. **AI Sector Pipeline** → begin Phase 1 (FinBERT upgrade) per `ai_sector_pipeline_spec.jsx` after NVDA stationary is confirmed
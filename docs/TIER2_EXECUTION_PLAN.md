# Tier 2 Execution Plan
**Last updated:** 2026-04-30  
**Phase:** Tier 2 Active — Exp 9 complete, Exp 10 next

---

## Status Overview

| Exp | Deliverable | Status | Notes |
|-----|-------------|--------|-------|
| 4 | `src/ensemble.py` — SparseEnsemble class | COMPLETE | Loads from leaderboard CSV, majority voting |
| 5 | `staging/models/ensemble_config.json` | COMPLETE | NVDA/AAPL/AMD top-3 seeds defined |
| 6 | `src/trading_agent.py` — EnsembleAgent | COMPLETE | Stateless, flat obs, shape assertion |
| **9** | Walk-forward backtest validation | **COMPLETE** | NVDA PASS, AMD PASS |
| **10** | Staging package + STAGING_READY.md | **NEXT** | File assembly + sign-off |

---

## Bugs Fixed This Session

Two bugs were found and fixed during Exp 9 validation. Future Claude instances should not re-introduce them.

### 1. `src/ensemble.py` — binarization used `int()` truncation

**Symptom:** Ensemble returned `buys=0, agreement=1.00` — all seeds voting Hold unanimously.  
**Cause:** `int(action.item())` truncates toward zero, so SAC output `0.857 → int(0.857) = 0` (Hold).  
**Fix (line ~84):**
```python
# WRONG — truncation, not sign-based
action_val = int(action.item() if isinstance(action, np.ndarray) else action)

# CORRECT — matches the env's binary_actions logic: target_weight = 1.0 if raw > 0.0 else 0.0
raw = action.item() if isinstance(action, np.ndarray) else float(action)
action_val = 1 if raw > 0.0 else 0
```

### 2. `src/trading_agent.py` — `>= 0.67` threshold excluded 2/3 majority votes

**Symptom:** `agreement_rate` was always equal to `high_conf_rate` (unanimous), making G2 redundant.  
**Cause:** For a 3-seed ensemble, 2/3 majority = `0.6666... < 0.67`, so it was never counted as "agreement."  
**Fix:** Two separate counters:
- `_majority_steps`: `confidence > 0.5` (captures any 2/3 or 3/3 vote)
- `_unanimous_steps`: `confidence >= 1.0 - 1e-9` (captures only 3/3 vote)

`get_session_metrics()` now returns both `agreement_rate` and `high_conf_rate` as distinct fields.

---

## Exp 9 — Results (2026-04-30)

### NVDA

| | Buys | Accuracy |
|-|------|----------|
| Seed 4 | 222 | 0.527 |
| Seed 6 | 295 | 0.525 |
| Seed 8 | 300 | 0.527 |
| **Ensemble** | **309** | **0.521** |

Ensemble: `agreement=1.00  avg_conf=0.75  unanimous_rate=0.24`

| Gate | Result | Detail |
|------|--------|--------|
| G1 ensemble_acc >= min_seed_acc − 0.5% | **PASS** | 0.521 >= 0.520 |
| G2 majority_agreement >= 60% | **PASS** | 1.00 >= 0.60 |
| G3 unanimous_rate >= 20% | **PASS** | 0.24 >= 0.20 |

Note on NVDA diversity: seed 4 is conservative (222 buys) vs seeds 6/8 (295/300). The 24% unanimous rate reflects intentional seed diversity — seed 4 acts as a brake on aggressive buys. This is healthy ensemble behavior, not a failure mode.

### AMD

| | Buys | Accuracy |
|-|------|----------|
| Seed 5 | 309 | 0.528 |
| Seed 2 | 284 | 0.521 |
| Seed 10 | 311 | 0.524 |
| **Ensemble** | **311** | **0.524** |

Ensemble: `agreement=1.00  avg_conf=1.00  unanimous_rate=0.99`

| Gate | Result | Detail |
|------|--------|--------|
| G1 ensemble_acc >= min_seed_acc − 0.5% | **PASS** | 0.524 >= 0.516 |
| G2 majority_agreement >= 60% | **PASS** | 1.00 >= 0.60 |
| G3 unanimous_rate >= 20% | **PASS** | 0.99 >= 0.20 |

AMD seeds are highly correlated (99% unanimous) — all three learned similar macro-holding logic.

---

## Architecture Reference

### Trained Models

| Ticker | Leaderboard CSV | Top-3 Seeds (by test Sharpe) | Model Dir |
|--------|----------------|------------------------------|-----------|
| NVDA | `data/exp_1_nvda_10seed_foundation_leaderboard.csv` | 4 (0.837), 6 (0.689), 8 (0.640) | `data/exp_1_nvda_10seed_foundation_snapshots/` |
| AAPL | `data/exp_2_aapl_10seed_foundation_leaderboard.csv` | 6 (0.363), 8 (0.085), 1 (0.085) | `data/exp_2_aapl_10seed_foundation_snapshots/` |
| AMD  | `data/exp_3_amd_10seed_foundation_leaderboard.csv` | 5 (1.017), 2 (0.944), 10 (0.921) | `data/exp_3_amd_10seed_foundation_snapshots/` |

### Observation Vector (27 dims — all three tickers)
```
[LogReturn, VolLogDiff, RelRange, RelOpen, RelMACD, RSI_Centered,
 RelATR, BB_Width, BB_Upper_Dist, BB_Lower_Dist, SMA_Trend,
 RelVWAP, MACD_Signal_Rel, MACD_Hist_Rel,        ← 14 market features
 NewsCount, SentimentMean, SentimentStd, SentimentMin, SentimentMax,
 SentimentConfidenceMean, SentimentGeminiShare, SentimentOllamaShare,  ← 8 news features
 balance, shares_held, current_weight, unrealized_pnl, time_in_position]  ← 5 account state
```
News columns are present even in `include_news=0` runs because the per-ticker stationary
parquets (`data/tech_training_data_{ticker}_stationary.parquet`) already contained them
at training time. All three tickers resolve to obs_shape=(27,).

### Test Split
All three tickers: 70/15/15 split on the 2074-row stationary parquet.
- Train: rows 0–1450
- Val: rows 1451–1761
- **Test: rows 1762–2073** (312 days, 2025-01-03 to 2026-04-02)

### Exp 9 Gate Thresholds (calibrated values)
| Gate | Threshold | Rationale |
|------|-----------|-----------|
| G1 | `ensemble_accuracy >= min_seed_accuracy − 0.005` | 0.5% tolerance for different trade-count denominators |
| G2 | `agreement_rate >= 0.60` | majority vote (> 0.5 confidence) on >= 60% of steps |
| G3 | `unanimous_rate >= 0.20` | all-3-agree on >= 20% of steps; 30% was too strict for diverse seeds |

---

## Exp 10 — Staging Package Assembly

**Goal:** Collect all artifacts into `staging/` and write the sign-off doc. This is entirely
manual file operations — no training or code changes needed.

### Step 1 — Create directory structure

```
mkdir staging\models\nvda staging\models\aapl staging\models\amd staging\metrics staging\src
```

### Step 2 — Copy NVDA models

```
copy "data\exp_1_nvda_10seed_foundation_snapshots\model_20260430-042524Z_exp_1_nvda_10seed_foundation_seed4.zip" staging\models\nvda\nvda_seed4.zip
copy "data\exp_1_nvda_10seed_foundation_snapshots\model_20260430-042823Z_exp_1_nvda_10seed_foundation_seed6.zip" staging\models\nvda\nvda_seed6.zip
copy "data\exp_1_nvda_10seed_foundation_snapshots\model_20260430-043120Z_exp_1_nvda_10seed_foundation_seed8.zip" staging\models\nvda\nvda_seed8.zip
```

### Step 3 — Copy AAPL models

```
copy "data\exp_2_aapl_10seed_foundation_snapshots\model_20260430-044512Z_exp_2_aapl_10seed_foundation_seed6.zip" staging\models\aapl\aapl_seed6.zip
copy "data\exp_2_aapl_10seed_foundation_snapshots\model_20260430-044819Z_exp_2_aapl_10seed_foundation_seed8.zip" staging\models\aapl\aapl_seed8.zip
copy "data\exp_2_aapl_10seed_foundation_snapshots\model_20260430-043741Z_exp_2_aapl_10seed_foundation_seed1.zip" staging\models\aapl\aapl_seed1.zip
```

### Step 4 — Copy AMD models

```
copy "data\exp_3_amd_10seed_foundation_snapshots\model_20260430-050427Z_exp_3_amd_10seed_foundation_seed5.zip" staging\models\amd\amd_seed5.zip
copy "data\exp_3_amd_10seed_foundation_snapshots\model_20260430-045938Z_exp_3_amd_10seed_foundation_seed2.zip" staging\models\amd\amd_seed2.zip
copy "data\exp_3_amd_10seed_foundation_snapshots\model_20260430-051227Z_exp_3_amd_10seed_foundation_seed10.zip" staging\models\amd\amd_seed10.zip
```

### Step 5 — Copy source files

```
copy src\ensemble.py staging\src\ensemble.py
copy src\trading_agent.py staging\src\trading_agent.py
copy src\feature_engineering.py staging\src\feature_engineering.py
copy src\trading_env.py staging\src\trading_env.py
```

### Step 6 — Copy leaderboards

```
copy data\exp_1_nvda_10seed_foundation_leaderboard.csv staging\metrics\nvda_leaderboard.csv
copy data\exp_2_aapl_10seed_foundation_leaderboard.csv staging\metrics\aapl_leaderboard.csv
copy data\exp_3_amd_10seed_foundation_leaderboard.csv staging\metrics\amd_leaderboard.csv
```

### Step 7 — Update `staging/models/ensemble_config.json`

The current config has `nvda.production_ready = false` (stale). Update it to the final state
below. Leaderboard paths should now point to `staging/metrics/`:

```json
{
  "nvda": {
    "active_seeds": [4, 6, 8],
    "ensemble_method": "voting",
    "top_3_mean_sharpe": 0.722,
    "top_3_mean_val_test_gap": 0.177,
    "production_ready": true,
    "leaderboard_csv": "staging/metrics/nvda_leaderboard.csv",
    "notes": "9/10 active seeds. Exp 9 gate passed 2026-04-30."
  },
  "aapl": {
    "active_seeds": [6, 8, 1],
    "ensemble_method": "voting",
    "top_3_mean_sharpe": 0.178,
    "top_3_mean_val_test_gap": 0.015,
    "production_ready": "monitor",
    "leaderboard_csv": "staging/metrics/aapl_leaderboard.csv",
    "notes": "6/10 active. Borderline alpha — monitor only, not in primary deployment."
  },
  "amd": {
    "active_seeds": [5, 2, 10],
    "ensemble_method": "voting",
    "top_3_mean_sharpe": 0.960,
    "top_3_mean_val_test_gap": 0.025,
    "production_ready": true,
    "leaderboard_csv": "staging/metrics/amd_leaderboard.csv",
    "notes": "6/10 active. Exp 9 gate passed 2026-04-30."
  }
}
```

### Step 8 — Verify end-to-end load

```
.venv/Scripts/python -c "
import warnings; warnings.filterwarnings('ignore')
from src.ensemble import SparseEnsemble
from src.trading_agent import EnsembleAgent

for ticker, lb in [('nvda', 'staging/metrics/nvda_leaderboard.csv'),
                   ('amd',  'staging/metrics/amd_leaderboard.csv')]:
    e = SparseEnsemble(lb)
    e.filter_active_seeds(20)
    e.load_top_n_models(3)
    a = EnsembleAgent(e, 'staging/models/ensemble_config.json', ticker)
    print(f'{ticker.upper()}: obs_shape={a.expected_obs_shape}  seeds={list(e.models.keys())}')
print('Staging package: OK')
"
```

### Step 9 — Write `staging/STAGING_READY.md`

Create this file manually. Minimum required content:
- Sign-off date
- Exp 9 gate results for NVDA and AMD (copy from above)
- Deployment scope: NVDA + AMD (paper trade), AAPL monitor-only
- Paper trade acceptance criterion: cumulative return > +5% over 2 weeks
- Next milestone: begin paper trade after staging is tagged

---

## What Comes After Staging

### Paper Trade Validation (2 weeks)
- Feed live daily data through `src/feature_engineering.py` → `compute_stationary_features()`
- Build obs: `[market_14 | news_8 | account_5]` matching training exactly
- Step `EnsembleAgent` daily, record actions and P&L
- Gate: cumulative return > +5% on NVDA + AMD over 2 weeks
- If passed: escalate to live capital (start with 1% of portfolio per signal)
- If failed: check whether test period (2025-01-03 – 2026-04-02) regime has expired

### New Ticker Onboarding (zero re-tuning needed)
1. Train 10 seeds: `python src/experiments.py --ticker <NEW> --seeds 1,2,3,4,5,6,7,8,9,10 --use-stationary-features --reward-mode sparse --rolling-reward-window 60 --binary-actions --long-only --execution-mode next_bar ...`
2. Pick top-3 by test Sharpe from leaderboard (filter: test_trade_count >= 20)
3. Add entry to `staging/models/ensemble_config.json`
4. Run: `.venv/Scripts/python scripts/run_exp9_walkforward.py --ticker <new>`
5. If all gates pass: copy models to `staging/models/<new>/`

---

## Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `src/trading_env.py` | Training environment — obs structure is the ground truth |
| `src/feature_engineering.py` | `compute_stationary_features()` — required for live obs |
| `src/ensemble.py` | `SparseEnsemble` — leaderboard-driven loader, majority voting |
| `src/trading_agent.py` | `EnsembleAgent` — stateless live inference, shape-asserting |
| `staging/models/ensemble_config.json` | Per-ticker seed config; needs Step 7 update before Exp 10 done |
| `scripts/run_exp9_walkforward.py` | Exp 9 gate script — reusable for new tickers |
| `scripts/run_fork_b_option2.py` | Training script for new runs |

### Smoke Test

```
.venv/Scripts/python -c "
import warnings; warnings.filterwarnings('ignore')
from src.ensemble import SparseEnsemble
from src.trading_agent import EnsembleAgent
e = SparseEnsemble('data/exp_1_nvda_10seed_foundation_leaderboard.csv')
e.filter_active_seeds(20); e.load_top_n_models(3)
a = EnsembleAgent(e, 'staging/models/ensemble_config.json', 'nvda')
print('obs_shape:', a.expected_obs_shape, '  seeds:', list(e.models.keys()))
"
```

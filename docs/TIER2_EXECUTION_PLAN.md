# Tier 2 Execution Plan
**Last updated:** 2026-04-30  
**Phase:** Tier 2 Active — Exp 6 complete, Exp 9 next

---

## Status Overview

| Exp | Deliverable | Status | Notes |
|-----|-------------|--------|-------|
| 4 | `src/ensemble.py` — SparseEnsemble class | COMPLETE | Loads from leaderboard CSV, top-N voting |
| 5 | `staging/models/ensemble_config.json` | COMPLETE | NVDA/AAPL/AMD top-3 seeds defined |
| **6** | `src/trading_agent.py` — EnsembleAgent | **COMPLETE** | Stateless, flat obs, shape assertion |
| **9** | Walk-forward backtest validation | **NEXT** | Unblocked by Exp 6 |
| 10 | Staging package + STAGING_READY.md | Blocked on 9 | File assembly + sign-off |

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
Note: news columns are included even for `include_news=0` runs because the stationary parquet
already contained them at training time.

### Test Split
All three tickers use an identical 70/15/15 split applied to the 2074-row stationary parquet.
- Train: rows 0–1450
- Val: rows 1451–1761
- **Test: rows 1762–2073** (312 days, 2025-01-03 to 2026-04-02)

---

## Exp 9 — Walk-Forward Validation

**Goal:** Confirm the 3-seed ensemble does not degrade vs individual seeds when running
on real market obs with evolving account state. Uses `TradingEnv` for faithful obs construction.

### Gate Criteria
| Gate | Condition |
|------|-----------|
| G1 | `ensemble_accuracy >= min(top-3 seed individual accuracies)` |
| G2 | `agreement_rate >= 60%` (fraction of steps where confidence >= 0.67) |
| G3 | `high_confidence_rate >= 30%` (fraction of steps where confidence = 1.0) |

### Step 1 — Run walk-forward for NVDA and AMD

```
.venv/Scripts/python scripts/run_exp9_walkforward.py
```

Default tickers: `nvda amd`. AAPL is excluded by default (borderline alpha).

To include AAPL:
```
.venv/Scripts/python scripts/run_exp9_walkforward.py --ticker nvda amd aapl
```

Expected output per ticker:
```
============================================================
  NVDA
============================================================
  Test rows: 312  (2025-01-03 to 2026-04-02)
  ...
  Seed   4: buys=...  accuracy=0.xxx
  Seed   6: buys=...  accuracy=0.xxx
  Seed   8: buys=...  accuracy=0.xxx

  Ensemble:   buys=...  accuracy=0.xxx  agreement=0.xx  avg_conf=0.xx

  G1 ensemble_acc >= min_seed_acc  (...): PASS / FAIL
  G2 agreement_rate >= 60%          (...): PASS / FAIL
  G3 high_conf_rate >= 30%          (...): PASS / FAIL

  EXP 9 GATE: PASS  (NVDA)
```

### Step 2 — Review results

- If all gates PASS for NVDA + AMD: proceed to Exp 10.
- If G1 fails (ensemble worse than worst seed): the voting method may be degrading signal.
  Investigate which seed is dragging accuracy down and consider removing it.
- If G2/G3 fail (low agreement): seeds are not correlated enough. Check if AMD seed 1 (low Sharpe)
  is in the loaded set — it should be filtered by `min_test_trades=20`.
- AAPL failure is acceptable — it's `production_ready: monitor`, not a deployment blocker.

---

## Exp 10 — Staging Package Assembly

**Goal:** Collect all artifacts into `staging/` and write the sign-off doc.

### Step 1 — Create staging directory structure

```
mkdir staging\models\nvda staging\models\aapl staging\models\amd staging\metrics staging\src
```

### Step 2 — Copy NVDA models (top-3 seeds)

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

### Step 5 — Copy source files to staging/src

```
copy src\ensemble.py staging\src\ensemble.py
copy src\trading_agent.py staging\src\trading_agent.py
copy src\feature_engineering.py staging\src\feature_engineering.py
copy src\trading_env.py staging\src\trading_env.py
```

### Step 6 — Copy leaderboards to staging/metrics

```
copy data\exp_1_nvda_10seed_foundation_leaderboard.csv staging\metrics\nvda_leaderboard.csv
copy data\exp_2_aapl_10seed_foundation_leaderboard.csv staging\metrics\aapl_leaderboard.csv
copy data\exp_3_amd_10seed_foundation_leaderboard.csv staging\metrics\amd_leaderboard.csv
```

### Step 7 — Update ensemble_config.json with final model paths

Edit `staging/models/ensemble_config.json` to update model paths from the original snapshot
paths to the new `staging/models/{ticker}/{ticker}_seed{n}.zip` paths, and set
`production_ready: true` for NVDA (correct the current false flag). Example final state:

```json
{
  "nvda": {
    "active_seeds": [4, 6, 8],
    "ensemble_method": "voting",
    "top_3_mean_sharpe": 0.722,
    "top_3_mean_val_test_gap": 0.177,
    "production_ready": true,
    "leaderboard_csv": "staging/metrics/nvda_leaderboard.csv",
    "notes": "9/10 active seeds. Exp 9 gate passed."
  },
  ...
}
```

### Step 8 — Verify the staging package loads end-to-end

```
.venv/Scripts/python -c "
from src.ensemble import SparseEnsemble
from src.trading_agent import EnsembleAgent

e = SparseEnsemble('staging/metrics/nvda_leaderboard.csv')
e.filter_active_seeds(min_test_trades=20)
e.load_top_n_models(n=3)
a = EnsembleAgent(e, 'staging/models/ensemble_config.json', 'nvda')
print('obs_shape:', a.expected_obs_shape)
print('Staging package: OK')
"
```

### Step 9 — Write STAGING_READY.md

Create `staging/STAGING_READY.md` with:
- Date signed off
- Exp 9 gate results for each ticker (paste from Exp 9 output)
- Model file checksums (optional)
- Next milestone: 2-week paper trade on NVDA + AMD
- Paper trade acceptance criterion: cumulative return > +5% over 2 weeks

---

## What Comes After Staging

### Paper Trade Validation (2 weeks)
- Run NVDA + AMD ensembles on live market data using real stationary features
- Target: cumulative return > +5%
- If passed: escalate to live capital (small position sizing)
- If failed: investigate whether market regime has shifted since the 2025-01-03 test period

### New Ticker Onboarding
The same pipeline works on any liquid ticker with 4+ years of daily history:
1. `python src/experiments.py --ticker <NEW> --seeds 1,2,3,4,5,6,7,8,9,10 --use-stationary-features --reward-mode sparse ...`
2. Pick top-3 seeds from leaderboard
3. Add entry to `staging/models/ensemble_config.json`
4. Run Exp 9 equivalent for the new ticker
5. Copy models to `staging/models/<new>/`

---

## Quick Reference — Key Files

| File | Purpose |
|------|---------|
| `src/trading_env.py` | Training environment — obs structure is the ground truth |
| `src/feature_engineering.py` | `compute_stationary_features()` — must be used to generate live obs |
| `src/ensemble.py` | `SparseEnsemble` — loads models, voting |
| `src/trading_agent.py` | `EnsembleAgent` — stateless live inference wrapper |
| `staging/models/ensemble_config.json` | Per-ticker seed config and metadata |
| `scripts/run_exp9_walkforward.py` | Exp 9 gate validation script |
| `scripts/run_fork_b_option2.py` | Training script for new runs |

## Quick Reference — Run Commands

```bash
# Check leaderboard for a ticker
.venv/Scripts/python -c "
import pandas as pd
df = pd.read_csv('data/exp_1_nvda_10seed_foundation_leaderboard.csv')
cols = ['seed','test_trade_count','test_sharpe_ratio','test_cumulative_return','model_path']
print(df[cols].sort_values('test_sharpe_ratio', ascending=False).to_string(index=False))
"

# Quick ensemble smoke test
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

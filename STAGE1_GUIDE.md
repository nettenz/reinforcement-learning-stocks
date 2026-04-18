# Stage 1 Implementation Guide

## Overview

Stage 1 proves whether stationary market features contain predictive signal without RL complexity. This is the critical gate before investing further in RL tuning.

**Key principle**: If supervised learning cannot extract profit from these features, RL won't either.

---

## What Has Been Built (No Breaking Changes)

### 1. **Baseline Policy Classes** (`src/baseline_agents.py`)

All implement `predict(obs) → action` interface (compatible with trading environment):

| Policy | Purpose | Use Case |
|--------|---------|----------|
| `RandomPolicy` | Sanity check (random actions) | Verify infrastructure works |
| `BuyHoldPolicy` | Market baseline (always long) | Benchmark for long bias |
| `FlatPolicy` | Null baseline (always flat) | Benchmark for no trading |
| `ThresholdPolicy` | Simple rule (if feature > threshold: long) | Verify features are directional |
| `SupervisedRegressionPolicy` | Train model to predict return, convert to weight | **PRIMARY STAGE 1** |
| `SupervisedClassificationPolicy` | Train model to classify action (long/flat/short) | Alternative to regression |

**Integration**: These policies integrate seamlessly with existing `TradingEnv` because they implement the standard interface. **Zero changes to RL pipeline required.**

---

### 2. **Supervised Baseline Training Script** (`src/supervised_baseline.py`)

Standalone Python script that:

1. **Loads data** using existing `get_tech_training_data()` pipeline
2. **Creates features** using existing stationary feature engineering
3. **Splits walk-forward** (train/val/test with temporal order preserved)
4. **Trains supervised model** (Linear, RandomForest, XGBoost, MLP)
5. **Evaluates** on validation and test sets
6. **Logs results** to JSON output

**Usage**:
```bash
python src/supervised_baseline.py \
  --ticker AAPL \
  --horizon 1 \
  --model-type rf \
  --output-dir results/stage1/
```

**Output**: JSON file with:
- Model type, hyperparameters, ticker, horizon
- Validation R², MSE, MAE
- Test R², MSE, MAE
- Feature names used
- Train/val/test split sizes

---

### 3. **Experiment Runner** (`run_stage1_baseline.ps1`)

Automated suite running all combinations:

**Experiments**:
- **Tickers**: AAPL, NVDA, AMD (tech basket)
- **Horizons**: 1, 3 days
- **Models**: linear, rf, xgb
- **Total runs**: 27 experiments (3 × 2 × 3 + variations)
- **Seed**: Fixed (42) for reproducibility

**Execution**:
```powershell
./run_stage1_baseline.ps1
```

**Output**: `data/stage1_results/` directory with results for each experiment.

---

## Stage 1 Success Criteria

### Interpretation Rules

**IF any of the following hold, signal likely exists:**

✅ **Positive predictability**:
- Test R² > 0.01 (better than random for most models)
- OR Test MAE < baseline (vs always predicting mean)

✅ **Consistency across models**:
- Linear, RF, and XGBoost all show positive R²
- Signals robustness, not model overfit

✅ **Stability across horizons**:
- 1-day and 3-day predictions both work
- Not just noise at one timescale

✅ **Statistically defensible**:
- All three tickers (AAPL, NVDA, AMD) show similar pattern
- Generalizes across tech sector

**IF these do NOT hold, signal is weak:**

❌ Only one model works (overfitting)
❌ Only one ticker works (cherry-picked)
❌ Only one horizon works (noise)
❌ R² < 0.005 (no predictive power)

---

## Current Project State Analysis

### What Works for Stage 1

✅ **Feature engineering**: 14 stationary, non-leaking features ready to use  
✅ **Data loading**: Ticker-aware pipeline with caching  
✅ **Walk-forward split**: Temporal integrity preserved  
✅ **Trading environment**: Policy-agnostic, accepts any `predict()` interface  
✅ **Evaluation**: Full metric suite (Sharpe, Sortino, alpha vs QQQ, drawdown, win rate)  

### What Does NOT Need to Change

- `src/trading_env.py` — Unchanged, works with any policy
- `src/experiments.py` — Unchanged, RL experiments untouched
- `src/market_data.py` — Unchanged, used for data loading
- `src/feature_engineering.py` — Unchanged, used for features
- Existing leaderboard tracking — Unchanged
- All existing RL experiment history — Unchanged

### Minimal Integration Points

- **No modifications to existing code** required to run Stage 1
- New files added: `baseline_agents.py`, `supervised_baseline.py`, `run_stage1_baseline.ps1`
- All Stage 1 results go to separate output directory: `data/stage1_results/`

---

## Execution Roadmap

### Phase 1: Validation (30 min)

```powershell
# Test single experiment to verify infrastructure
python src/supervised_baseline.py --ticker AAPL --model-type linear --seed 42
```

Expected output:
- JSON file with train/val/test metrics
- Should see R² values (positive or negative)
- No errors from feature engineering or environment

**Success**: Script runs without errors, produces JSON output.

### Phase 2: Full Suite (2-4 hours)

```powershell
./run_stage1_baseline.ps1
```

Expected output:
- 27 JSON files in `data/stage1_results/`
- Each with metrics across tickers, horizons, models

**Success**: All experiments complete, results collected.

### Phase 3: Analysis (1 hour)

Create analysis script to:
1. Aggregate results across all experiments
2. Compute summary statistics (mean/std R², MAE across models)
3. Check consistency (do all models agree?)
4. Generate decision: "Signal exists" vs "Signal weak"

### Phase 4: Decision Gate

**If signal exists**:
→ Proceed to **Stage 2**: Simplify RL task
- Replace continuous weights with discrete actions (flat/long/short)
- Remove reward shaping (only post-cost economic return)
- Run RL with minimal hyperparameter tuning

**If signal weak**:
→ **Investigate before proceeding**:
- Feature engineering (are stationary features rich enough?)
- Data quality (missing data? look-ahead bias?)
- Horizon mismatch (predict too far ahead?)
- Market regime (is signal regime-dependent?)

---

## Implementation Notes

### Model Choices

**Why these three models?**

1. **Linear** (Ridge regression): Fast baseline, easily interpretable, low overfit risk
2. **Random Forest**: Nonlinear relationships, feature importance, robust
3. **XGBoost**: Gradient boosting, captures interactions, best single-model performance

If all three agree on positive R², signal is real. If only XGBoost works, likely overfitting.

### Feature Engineering

**Stage 1 uses existing 14 stationary features**:
- LogReturn, VolLogDiff, RelRange, RelOpen, RelMACD, RSI_Centered, RelATR, BB_Width, BB_Upper_Dist, BB_Lower_Dist, SMA_Trend, RelVWAP, MACD_Signal_Rel, MACD_Hist_Rel

**NOT used**: News sentiment (Stage 1 focuses on pure market structure)

**Can iterate later** if weak signal: add features, try different horizons, adjust targets.

### Evaluation Metrics

**Primary (signal proof)**:
- Regression R² (does model explain variance?)
- MAE (absolute prediction error)

**Secondary (trading readiness)**:
- Will be computed when Stage 1 results feed into RL evaluation (Stage 2+)

---

## Next Steps After Stage 1

### If Signal Exists → Stage 2: RL Simplification

1. **Discrete action space**: Replace continuous weights with {flat, long, short}
2. **Minimal reward**: Only post-cost economic return (no shaping)
3. **Fast train**: 50k timesteps, single seed, no sweep
4. **Evaluate**: Does RL add value over supervised baseline?

### If Signal Weak → Debug Phase

1. **Feature analysis**: Which features have most predictive power?
2. **Regime analysis**: Does signal exist only in certain market conditions?
3. **Horizon sweep**: Is prediction easier at 5-day, 10-day horizons?
4. **Data quality**: Check for gaps, survivorship bias, forward-looking indicators

---

## Files Summary

| File | Purpose | Status |
|------|---------|--------|
| `src/baseline_agents.py` | Policy wrappers for supervised models | ✅ Created |
| `src/supervised_baseline.py` | Training and evaluation script | ✅ Created |
| `run_stage1_baseline.ps1` | Automated experiment suite runner | ✅ Created |
| Existing RL pipeline | Untouched | ✅ No changes |

---

## How to Run

### Quick Test (5 min)
```powershell
python src/supervised_baseline.py --ticker AAPL --model-type linear
```

### Full Suite (2-4 hours)
```powershell
./run_stage1_baseline.ps1
```

### Custom Experiment
```powershell
python src/supervised_baseline.py \
  --ticker NVDA \
  --horizon 3 \
  --model-type xgb \
  --output-dir data/stage1_results/ \
  --seed 42
```

---

## Key Principle

**Stage 1 answers one critical question: Does the market signal exist in these features?**

If YES → RL tuning becomes feasible (Stage 2+)  
If NO → Spend time on feature engineering, not reward tuning

This gate prevents wasting months optimizing an unsolvable problem.

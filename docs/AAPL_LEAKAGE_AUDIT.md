# AAPL Leakage Audit Checklist
**Created:** 2026-04-30  
**Trigger:** Severe val→test accuracy collapse observed in AAPL foundation sweep  
**Blocker status:** AAPL promotion blocked until this audit clears  
**Skill basis:** `backtest-auditor` + `strategy-refinement-analyst`

---

## Known Symptom
AAPL foundation sweep showed a severe val→test accuracy collapse — high val accuracy that did not survive into the test split. This pattern is the canonical signature of one of three things:
1. **Data leakage** — future information entering the training or feature pipeline
2. **Regime overfitting** — val period happened to be favorable, test was not
3. **Label contamination** — evaluation labels constructed with lookahead

Do not run a promotion sweep until at least one of these is ruled out.

---

## Pre-Audit Setup

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Pull AAPL foundation leaderboard for reference
python -c "
import pandas as pd
lb = pd.read_csv('data/exp_2_aapl_10seed_foundation_leaderboard.csv')
print(lb[['seed','val_actionable_accuracy','test_actionable_accuracy','val_alpha_vs_qqq','test_alpha_vs_qqq']].to_string())
"
```

**What to record before starting:**
- [ ] Val accuracy range across seeds: ______
- [ ] Test accuracy range across seeds: ______
- [ ] Mean val→test accuracy drop: ______
- [ ] Is the drop consistent across all seeds or only some? ______

---

## Phase 1 — Data Split Integrity

**Goal:** Confirm chronological ordering is preserved and no future bars bleed into training.

### 1.1 Verify split boundaries in `src/experiments.py`

```powershell
python -c "
import pandas as pd
from src.market_data import get_tech_training_data
df = get_tech_training_data(ticker_preset='aapl', use_stationary_features=False)
n = len(df)
train_end = int(n * 0.70)
val_end   = int(n * 0.85)
print(f'Total rows : {n}')
print(f'Train end  : {train_end} — {df.iloc[train_end][\"Date\"]}')
print(f'Val end    : {val_end}   — {df.iloc[val_end][\"Date\"]}')
print(f'Test start : {val_end}   — {df.iloc[val_end][\"Date\"]}')
print(f'Test end   : {n-1}       — {df.iloc[-1][\"Date\"]}')
"
```

- [ ] Train, val, test splits are strictly chronological (no overlap)
- [ ] Test period is recent enough to represent out-of-sample market conditions
- [ ] Val period does not bleed into test period

**Red flag:** If val period overlaps a major AAPL event (earnings, product launch) that test does not share, the collapse may be regime-driven rather than leakage.

---

### 1.2 Check AAPL-specific data cache

```powershell
# Verify the parquet cache is clean
python -c "
import pandas as pd
df = pd.read_parquet('data/tech_training_data_aapl.parquet')
print('Shape:', df.shape)
print('Date range:', df['Date'].min(), '->', df['Date'].max())
print('NaN count:', df.isnull().sum().sum())
print('Duplicate dates:', df['Date'].duplicated().sum())
"
```

- [ ] No duplicate dates in AAPL cache
- [ ] No NaN gaps in OHLCV columns
- [ ] Date range matches expected training window (2015 onward)

---

## Phase 2 — Feature Leakage Check

**Goal:** Confirm no feature is computed using data from bar T or later when predicting at bar T.

### 2.1 Inspect stationary feature construction for AAPL

```powershell
python -c "
import pandas as pd
from src.feature_engineering import compute_stationary_features
df = pd.read_parquet('data/tech_training_data_aapl.parquet')
features = compute_stationary_features(df)
# Check first few rows for NaN (correct shift behavior)
print(features.head(10).to_string())
print()
print('NaN in first 30 rows per feature:')
print(features.head(30).isnull().sum())
"
```

- [ ] Features show NaN in early rows (correct — rolling windows need warmup)
- [ ] No feature has a suspiciously low NaN count in early rows (would suggest no lookback shift)
- [ ] `LogReturn` is shifted correctly — uses only prior close, not current close

**Critical check — directional alignment term:**
The `reward_direction_scale` term in the reward function was flagged in prior sessions as a look-ahead risk. Verify it does not use bar T's close price to compute direction at bar T.

```powershell
python -c "
import inspect
from src.trading_env import TradingEnv
print(inspect.getsource(TradingEnv._compute_reward))
" 2>&1 | Select-String -Pattern "direction|close|price|next"
```

- [ ] Reward direction term uses only `next_bar` execution price, not bar T close
- [ ] No reference to `df.iloc[current_step + 1]` inside reward computation

---

### 2.2 Check news sentiment feature alignment for AAPL

```powershell
python -c "
import pandas as pd
news = pd.read_csv('data/tech_news_sentiment_aapl.csv')
print(news.head(10).to_string())
print()
print('Date column type:', news['Date'].dtype if 'Date' in news.columns else 'NO DATE COLUMN')
"
```

- [ ] News sentiment timestamps are bar-open aligned (not bar-close)
- [ ] News from day T is not being used to trade day T's open (would require same-day look-ahead)
- [ ] Sentiment feature is forward-filled correctly with no future bleed

---

## Phase 3 — Evaluation Label Integrity

**Goal:** Confirm `signal_analytics.py` evaluation labels do not use future prices.

### 3.1 Trace `enrich_with_truth_labels()` or equivalent

```powershell
python -c "
import inspect
from src.signal_analytics import SignalAnalytics
# Find the label construction method
for name, method in inspect.getmembers(SignalAnalytics, predicate=inspect.isfunction):
    if 'label' in name.lower() or 'truth' in name.lower() or 'accuracy' in name.lower():
        print(f'--- {name} ---')
        print(inspect.getsource(method))
        print()
"
```

- [ ] Accuracy labels are computed using `realized_return` from completed trades (past), not future prices
- [ ] `actionable_accuracy` is computed over closed positions only
- [ ] No `shift(-1)` or `iloc[i+1]` references in label construction

---

## Phase 4 — Val vs Test Regime Analysis

**Goal:** Determine if the collapse is regime-driven (not leakage) by comparing market conditions across splits.

```powershell
python -c "
import pandas as pd
import numpy as np
df = pd.read_parquet('data/tech_training_data_aapl.parquet')
n = len(df)
val_start = int(n * 0.70)
val_end   = int(n * 0.85)

val_df  = df.iloc[val_start:val_end]
test_df = df.iloc[val_end:]

val_return  = (val_df['Close'].iloc[-1]  / val_df['Close'].iloc[0])  - 1
test_return = (test_df['Close'].iloc[-1] / test_df['Close'].iloc[0]) - 1

val_vol  = val_df['Close'].pct_change().std() * np.sqrt(252)
test_vol = test_df['Close'].pct_change().std() * np.sqrt(252)

print(f'Val  period: {val_df[\"Date\"].iloc[0]} -> {val_df[\"Date\"].iloc[-1]}')
print(f'Test period: {test_df[\"Date\"].iloc[0]} -> {test_df[\"Date\"].iloc[-1]}')
print()
print(f'Val  cumulative return : {val_return:.2%}')
print(f'Test cumulative return : {test_return:.2%}')
print()
print(f'Val  annualized vol : {val_vol:.2%}')
print(f'Test annualized vol : {test_vol:.2%}')
"
```

- [ ] Record val period return: ______
- [ ] Record test period return: ______
- [ ] Record val volatility: ______
- [ ] Record test volatility: ______

**Interpretation:**
- If val return >> test return AND vol is similar → regime shift, not leakage → mark as **regime overfitting**
- If vol is dramatically different → agent trained on one volatility regime, tested on another → mark as **regime mismatch**
- If neither explains the full collapse → leakage is still the primary suspect

---

## Phase 5 — Cross-Ticker Comparison

**Goal:** Confirm the collapse is AAPL-specific, not a systemic pipeline bug.

```powershell
python -c "
import pandas as pd
lb = pd.read_csv('data/experiment_leaderboard.csv')

for ticker in ['NVDA', 'AAPL', 'AMD']:
    subset = lb[lb['ticker'].str.upper() == ticker]
    if len(subset) == 0:
        continue
    drift = (subset['val_actionable_accuracy'] - subset['test_actionable_accuracy']).abs()
    print(f'{ticker}: mean val_acc={subset[\"val_actionable_accuracy\"].mean():.3f}  test_acc={subset[\"test_actionable_accuracy\"].mean():.3f}  drift={drift.mean():.3f}')
"
```

- [ ] NVDA val→test drift is low (baseline: ~0.0025)
- [ ] AAPL val→test drift is significantly higher than NVDA
- [ ] AMD drift pattern is different from AAPL (confirms AAPL issue is isolated)

If NVDA and AMD show similar collapse → pipeline-level bug, not AAPL-specific.  
If only AAPL collapses → AAPL data or regime issue.

---

## Phase 6 — Audit Verdict

Fill in after completing Phases 1–5.

| Check | Result | Verdict |
|-------|--------|---------|
| Split chronology | | PASS / FAIL |
| Feature shift correctness | | PASS / FAIL |
| Direction term look-ahead | | PASS / FAIL |
| News timestamp alignment | | PASS / FAIL |
| Evaluation label integrity | | PASS / FAIL |
| Regime shift explains collapse | | YES / NO |
| Issue is AAPL-specific | | YES / NO |

**Root cause classification:**
- [ ] Data leakage (training features)
- [ ] Evaluation label contamination
- [ ] Regime overfitting (val bullish, test bearish)
- [ ] Regime mismatch (vol regime change)
- [ ] Unknown — needs deeper investigation

---

## Phase 7 — Decision Gate

| Condition | Next Action |
|-----------|-------------|
| Leakage confirmed in features | Fix `feature_engineering.py` or `market_data.py` before any sweep |
| Leakage confirmed in labels | Fix `signal_analytics.py` evaluation path before any sweep |
| Regime overfitting only | Proceed to sweep with note — no code fix required |
| Regime mismatch only | Consider expanding training window or re-splitting |
| Unknown | Do not promote — escalate to deeper audit session |

**Decision:** ______________________

---

## Post-Audit: If Cleared — First AAPL Sweep

Only run after Phase 7 decision is **Proceed**.

```powershell
.\.venv\Scripts\python.exe src\experiments.py `
    --ticker aapl `
    --reward-mode sharpe `
    --ent-coefs 0.02,0.05 `
    --timesteps 40000 `
    --seeds 3,7,13,21,42 `
    --execution-mode next_bar `
    --reward-hold-penalty-scale 0.01 `
    --reward-turnover-penalty-scale 0.10 `
    --max-weight-delta-per-step 0.10 `
    --use-stationary-features `
    --run-label "sweep_aapl_post_audit_v1" `
    --append
```

Then evaluate:

```powershell
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label sweep_aapl_post_audit_v1
```

---

## Notes
_Fill in findings as you work through each phase._

```
Phase 1 findings:


Phase 2 findings:


Phase 3 findings:


Phase 4 findings:


Phase 5 findings:


Root cause:


Decision:
```

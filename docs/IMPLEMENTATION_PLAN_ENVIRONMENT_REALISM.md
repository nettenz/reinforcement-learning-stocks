# Implementation Plan: Environment Realism Fixes
**Status**: Ready to Implement  
**Created**: 2026-04-02 | **Target Completion**: 2026-04-21  
**Owner**: Backtesting / Environment Team

---

## Overview

This plan operationalizes the findings from [docs/ENVIRONMENT_REALISM_AUDIT_2026_04_02.md](ENVIRONMENT_REALISM_AUDIT_2026_04_02.md). The goal is to reduce the gap between backtest and live trading without breaking research velocity.

**Success Criteria**:
- ✅ Next-bar execution model validated (Phase 2)
- ✅ Feature semantics clarified (Phase 1)
- ✅ Sentiment pipeline understood or disabled (Phase 1)
- ✅ Leaderboard v2 schema with execution_mode tracking (Phase 2)

---

## Phase 1: Risk Mitigation (Week 1)
**Effort**: 4 hours | **Breaking**: NO | **Leaderboard Frozen**: Yes

### 1a. Delete Corrupted Data [DONE ✅]
- [x] Delete `data/tech_training_data.csv` (2069 rows, 25 cols, _x/_y corruption)
- [x] Verify `data/tech_training_data.parquet` exists and is clean (2072 rows, 29 cols)
- [x] Confirm code defaults to parquet via [src/analytics_dashboard.py](../src/analytics_dashboard.py#L34-L36)

**Test**: `python -c "import pandas as pd; df = pd.read_parquet('data/tech_training_data.parquet'); assert df.shape == (2072, 29); assert not df.columns.str.contains('_y').any()"`

---

### 1b. Fix Feature Naming [TODO]
**File**: [src/market_data.py](../src/market_data.py#L95) and [src/trading_env.py](../src/trading_env.py#L202)  
**Change**: Rename `Close` → `DailyReturn` for semantic clarity

#### Step 1: Update market_data.py (line 95)
```python
# BEFORE:
basket = normalized.groupby("Date", as_index=False).agg(
    Open=("OpenNorm", "mean"),
    High=("HighNorm", "mean"),
    Low=("LowNorm", "mean"),
    Close=("CloseNorm", "mean"),   # ← Misleading name
    Volume=("VolumeNorm", "mean"),
    RawClose=("Close", "mean"),
)

# AFTER:
basket = normalized.groupby("Date", as_index=False).agg(
    Open=("OpenNorm", "mean"),
    High=("HighNorm", "mean"),
    Low=("LowNorm", "mean"),
    DailyReturn=("CloseNorm", "mean"),  # ← Clearer semantics
    Volume=("VolumeNorm", "mean"),
    RawClose=("Close", "mean"),
)
```

#### Step 2: Update trading_env.py (line 202)
```python
# BEFORE:
self.market_feature_columns = ["Open", "High", "Low", "Close", "Volume"]

# AFTER:
self.market_feature_columns = ["Open", "High", "Low", "DailyReturn", "Volume"]
```

#### Step 3: Update trading_env.py observation space docstring (line 190-200)
```python
"""
Observation Space: [market_features] + [news_features] + [account_state]
  market_features: [Open, High, Low, DailyReturn (mean pct_change), Volume (log diff), ...]
  news_features: [NewsCount, SentimentMean, ...]
  account_state: [balance, shares_held, current_weight (if included), unrealized_pnl, time_in_position]
"""
```

#### Step 4: Migration Script (safety check)
```bash
# Verify no hardcoded references to 'Close' remain
grep -r '"Close"' src/*.py docs/*.md  # Should only find RawClose after renaming
```

#### Step 5: Test
```python
# Quick validation: train one episode, check obs shape
from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv
df = get_tech_training_data()
assert "DailyReturn" in df.columns
env = TradingEnv(df)
obs, _ = env.reset()
assert obs.shape == (14,)  # Verify observation shape unchanged
```

**Risk**: Low (column rename; schema validates automatically)  
**Leaderboard Impact**: NONE (internal feature name, not tracked)

---

### 1c. Document NaN Fill Strategy [TODO]
**File**: [src/market_data.py](../src/market_data.py#L113-L166) `merge_news_features()` function

**Add docstring**:
```python
def merge_news_features(
    training_data: pd.DataFrame,
    news_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge news/sentiment features into training data via left-join and explicit 0-fill.
    
    Strategy: For dates with no news, NewsCount and SentimentMean are set to 0.0.
    
    WARNING: If sentiment data becomes denser in the future, this 0-fill strategy
    will introduce lookahead bias (future "no news" is filled backwards). If density
    improves significantly (e.g., >50% coverage), switch to forward-fill or dropna().
    
    Current status (as of 2026-04-02):
      - Sentiment coverage: ~1 row / 2070 (0.05%)
      - Bias risk: LOW (sentiment signal is near-zero anyway)
      - Action: Monitor; consider fixing sentiment pipeline (see NEWS_DATA_TODO)
    """
```

**Add comment in implementation**:
```python
merged = merged.fillna(fill_values)  # Explicit 0-fill (not forward-fill)
# TODO: Document decision once sentiment pipeline is fixed
# If future work improves sentiment density to >10% of data,
# reconsider fill strategy to avoid lookahead bias.
```

**Risk**: LOW (documentation only; no code change)

---

### 1d. Investigate Sentiment Data Sparse [TODO]
**Files**: [src/news_data.py](../src/news_data.py) + [data/tech_news_sentiment_data.csv](../data/tech_news_sentiment_data.csv)

**Investigation Checklist**:
- [ ] Run: `python -c "import pandas as pd; df = pd.read_csv('data/tech_news_sentiment_data.csv'); print(df.shape, df[['Date', 'NewsCount']].head(20))"`
- [ ] Check if NewsCount distribution is truly {0: 2068, 1: 1}
- [ ] Run `get_tech_news_features(refresh=True)` to re-fetch from source
- [ ] Check [src/news_data.py](../src/news_data.py#L279) `fetch_yahoo_news()` return volume
- [ ] Check if Yahoo Finance API has historical sentiment data limitation
- [ ] Document finding in [docs/SENTIMENT_INTEGRATION.md](SENTIMENT_INTEGRATION.md)

**Possible Outcomes**:

**A. API Limitation** (API only returns recent news, not historical):
```markdown
# Sentiment Data Finding (2026-04-02)

## Issue
Yahoo Finance `yfinance` library does not provide historical news sentiment data.
Current implementation returns only recent articles (~1 per date range).

## Decision
Disable news integration for now. Options:
1. Use external sentiment API (e.g., Alpaca, FinBERT, etc.)
2. Accept news=0 for historical backtesting only
3. Use differently sourced sentiment data (alternative vendor)

## Action Required
Update experiments to `include_news=False` OR fix sentiment source.
```

**B. Code Bug in fetch_yahoo_news()**:
```markdown
# Found bug: xxx in fetch_yahoo_news()
Fix: [code]
Impact: +1-3% signal if fixed
Timeline: 4 hours
```

**Action**: Choose outcome and document in [docs/SENTIMENT_INTEGRATION.md](../docs/SENTIMENT_INTEGRATION.md)

**Risk**: LOW (informational; may unblock future work)

---

### Phase 1 Sign-Off
- [ ] Corrupted CSV deleted
- [ ] Features renamed Close → DailyReturn
- [ ] NaN fill strategy documented
- [ ] Sentiment data investigation complete
- [ ] All Phase 1 tests pass
- [ ] Leaderboard frozen at row 114

**Timeline**: ~4 hours stretched over 1 week (can run in parallel)

---

## Phase 2: Next-Bar Baseline (Week 2–3)
**Effort**: 6-8 hours | **Breaking**: YES (Leaderboard v2) | **Post-Decision Point**

### 2a. Verify Next-Bar Logic [TODO]
**File**: [src/trading_env.py](../src/trading_env.py#L330-L350)

**Review Current Logic**:
```python
# Lines 345-349
if self.execution_mode == "next_bar":
    execution_target_weight = self.pending_target_weight  # From t-1
    self.pending_target_weight = desired_target_weight    # For t+1
else:
    execution_target_weight = desired_target_weight       # Execute now
```

**Verification Checklist**:
- [ ] Confirm: Decision at step t is executed at step t+1
- [ ] Verify: pending_target_weight initialized to 0.0 in reset() (line 305)
- [ ] Test: Run 5 steps manually, verify fills happen one bar late
- [ ] Edge case: Check last bar (terminated=True) behavior (should be OK due to loop structure)

**Test Case (unit test to add to tests/)**:
```python
def test_next_bar_execution_timing():
    df = get_tech_training_data().head(10)
    env = TradingEnv(df, execution_mode="next_bar")
    obs, _ = env.reset()
    
    # Step 1: Decide to go long (1.0), but execute pending (0.0)
    obs, reward, done, trunc, info = env.step(1.0)
    assert info["execution_target_weight"] == 0.0  # Pending from reset
    
    # Step 2: Execute the long from step 1; decide to go short (-1.0)
    obs, reward, done, trunc, info = env.step(-1.0)
    assert info["execution_target_weight"] == 1.0  # From step 1
    
    # Verify share count changed only in step 2, not step 1
    # (requires env to expose position history or we inspect info dict)
```

**Risk**: MED (if bugs found, next-bar may not be trustworthy; fallback to same-bar)

---

### 2b. Run Next-Bar Baseline Experiments [TODO]
**Scope**: 10 seeds, 40k timesteps each, next_bar execution mode  
**Config**:
```python
baseline_config = {
    "execution_mode": "next_bar",
    "learning_rate": 0.0003,
    "gamma": 0.99,
    "ent_coef": 0.01,
    "reward_mode": "legacy",
    "transaction_cost_rate": 0.001,
    "trade_penalty": 0.0,
    "spread_bps": 0.0,
    "slippage_bps": 0.0,
    "threshold": 0.002,
    "include_news": True,
    "use_stationary_features": False,
}

seeds = [7, 13, 21, 42, 99, 101, 102, 103, 104, 105]
# Run all 10 in experiment sweep
```

**Execution**:
```bash
cd /path/to/repo
python -m src.experiments \
    --seeds 7 13 21 42 99 101 102 103 104 105 \
    --timesteps 40000 \
    --learning_rate 0.0003 \
    --execution_mode "next_bar" \
    --output_prefix "phase2_nextbar_baseline"
```

**Expected Results**:
- Win rate: ~48-50% (same as Phase 1, or slightly lower if lookback was magical)
- Alpha vs QQQ: Same as current
- Sharpe ratio: Likely similar (fills are same, just one bar later)

**Duration**: ~2-4 hours (depends on GPU availability)

---

### 2c. Update Leaderboard Schema [TODO]
**File**: [src/experiments.py](../src/experiments.py#L32-L100) `run_experiments()` function

**Add Required Columns to Config**:
```python
# In run_experiments() default config:
DEFAULT_EXPERIMENT_CONFIG = {
    # ... existing fields ...
    "execution_mode": "next_bar",  # REQUIRED: was implicit before
    "spread_bps": 0.0,             # REQUIRED: was implicit (0.0)
    "slippage_bps": 0.0,           # REQUIRED: was implicit (0.0)
    "training_data_version": "base",  # NEW: for future multi-ticker variants
    "leaderboard_version": 2,      # NEW: mark as v2 schema (backward compat on v1)
}
```

**Add Migration Note to Leaderboard CSV**:
```csv
# Header row (row 0):
seed,timesteps,execution_mode,training_data_version,leaderboard_version,...

# First new row (row 114, Phase 2):
7,40000,next_bar,base,2,...

# Old rows (0-113) should get inline migration note:
# ADD AFTER ALL COLUMNS:
_note: "leaderboard_version=1 (legacy): same_bar execution, multi-ticker"
```

**Create Migration Document**:
```markdown
# LEADERBOARD_v2_MIGRATION.md

## Change Summary
- Old leaderboard (rows 0-113): execution_mode=same_bar (or NaN), multi-ticker basket
- New leaderboard (rows 114+): execution_mode=next_bar, multi-ticker basket (or single-ticker after Phase 3)

## Schema Changes
- Added column: execution_mode (string: "same_bar" | "next_bar")
- Added column: spread_bps (float)
- Added column: slippage_bps (float)
- Added column: training_data_version (string: "base" | "single_ticker_aapl" [future])
- Added column: leaderboard_version (int: 1 | 2)

## What Changed in Phase 2?
1. Execution model: same_bar → next_bar (more realistic fills)
2. Feature columns: Close → DailyReturn (clarity only)
3. Data pipeline: No changes to training data (still multi-ticker synthetic basket)

## Why Split Leaderboards?
Head-to-head comparison between v1 and v2 is not meaningful because:
- Execution timing shifted (same_bar vs next_bar)
- Agent has 1 extra bar of history to make decisions
- Expected performance delta: -0.5% to -1.5% (more conservative fills)

## Backward Compatibility
- Old models (trained on same_bar) can still be loaded
- Environment accepts execution_mode parameter; experiments can test mixed modes
- Dashboard filters: "Show v1 only", "Show v2 only", "Show all (not comparable)"
```

**Risk**: MED (large schema change; dashboard needs update)

---

### 2d. Dashboard & Analytics Update [TODO]
**File**: [src/analytics_dashboard.py](../src/analytics_dashboard.py#L100-L110) and comparison tables

**Update Dashboard to Handle v1/v2**:
```python
# In leaderboard loading function:
def load_leaderboard(version: str = "all"):
    lb = pd.read_csv(DEFAULT_LEADERBOARD_PATH)
    
    if version == "v1":
        return lb[lb["leaderboard_version"] == 1]
    elif version == "v2":
        return lb[lb["leaderboard_version"] == 2]
    elif version == "all":
        return lb
    else:
        raise ValueError(f"Unknown version: {version}")

# In metrics display:
st.write(f"*Execution Mode*: {row['execution_mode']}")
st.write(f"*Leaderboard Version*: {row['leaderboard_version']}")
```

**Risk**: LOW (display update; no training impact)

---

### 2e. Decision Point: Full Re-Baseline or Gradual? [TODO]
**Decision Criteria**:

```
IF next_bar_baseline_results == same_bar_results:
    → DECISION A: Phase 3 only; no full re-baseline of Phase 1
    → Rationale: If no material perf change, switch is safe; focus on market representation
    
ELIF next_bar_baseline_results < same_bar_results (worse):
    → DECISION B: Re-baseline top 50 experiments with next_bar
    → Rationale: Policy improved; justify the switch with better generalization
    
ELIF next_bar_baseline_results > same_bar_baseline_result (better):
    → DECISION C: DO NOT RE-BASELINE; investigate why lookback was bad
    → Rationale: Something is wrong with same_bar logic or this is overfitting
```

**Recommendation**: Expect DECISION A (neutral perf delta). Proceed with Phase 3.

---

### Phase 2 Sign-Off
- [ ] Next-bar logic verified (unit tests pass)
- [ ] 10-seed baseline experiments complete
- [ ] Results documented (win rate, alpha, median reward)
- [ ] Leaderboard schema updated (v2 columns added)
- [ ] Migration document created
- [ ] Dashboard filters updated
- [ ] Decision point resolved (Decision A/B/C)

**Timeline**: 6–8 hours stretched over 2 weeks (experiment runtime dominates)

---

## Phase 3: Market Representation (Week 3–4)
**Effort**: 6–10 hours | **Breaking**: YES (new training data) | **Pre-Phase 2 Decision Gate**

### 3a. Decision: Single-Ticker vs Multi-Ticker Formalization [TODO]

**Option A: Migrate to Single-Ticker (AAPL)**
- **Pros**: Cleaner semantics, realistic execution, less ambiguity
- **Cons**: 1.5-2% annual performance from reduced diversification (expected)
- **Effort**: 6 hours
- **Recommendation**: Choose this path (clearest, simplest)

**Option B: Formalize Multi-Ticker**
- **Pros**: Keep existing training data; just clarify semantics
- **Cons**: Execution still synthetic; position math needs explicit N-leg accounting
- **Effort**: 3–4 hours (change is mostly documentation + PositionManager extension)
- **Recommendation**: Choose only if time-constrained; less ideal long-term

**Go/No-Go Decision Point**: 
- Compare Phase 2 baseline performance
- If performance is acceptable, proceed to (A)
- If performance is concerning, pause and debug (B might be safer)

---

### 3b. Implement Single-Ticker (AAPL) [TODO IF OPTION A]

#### Step 1: Create New Data Function
**File**: [src/market_data.py](../src/market_data.py)

```python
def get_single_ticker_training_data(
    ticker: str = "AAPL",
    cache_path: str | Path | None = None,
    start: str = "2018-01-01",
    end: str | None = None,
    interval: str = "1d",
    include_news: bool = True,
    news_refresh: bool = False,
    refresh: bool = False,
    use_stationary_features: bool = False,
) -> pd.DataFrame:
    """
    Fetch single-ticker training data (no multi-ticker aggregation).
    
    Args:
        ticker: Stock ticker (e.g., "AAPL")
    
    Returns:
        DataFrame with single-ticker OHLCV, technical indicators, and optional news
    """
    if cache_path is None:
        cache_path = SINGLE_TICKER_CACHE_PATH.format(ticker=ticker)
    
    cache_file = Path(cache_path)
    if cache_file.exists() and not refresh:
        data = pd.read_parquet(cache_file)
        if include_news and not set(NEWS_FEATURE_COLUMNS).issubset(data.columns):
            news_features = get_tech_news_features(tickers=[ticker], refresh=news_refresh)
            data = merge_news_features(training_data=data, news_features=news_features)
            data.to_parquet(cache_file, index=False)
        return data
    
    # Fetch single ticker
    raw = fetch_yahoo_ohlcv(tickers=[ticker], start=start, end=end, interval=interval)
    normalized = parse_and_normalize_ohlcv(raw)
    
    # NO groupby aggregation; just take the single-ticker rows
    base_training = normalized[normalized["Ticker"] == ticker].drop(columns=["Ticker"]).reset_index(drop=True)
    base_training["RawClose"] = base_training["Close"]  # Keep actual prices
    base_training["Close"] = base_training["CloseNorm"]  # Rename normalized to Close (for compat)
    base_training["Open"] = base_training["OpenNorm"]
    base_training["High"] = base_training["HighNorm"]
    base_training["Low"] = base_training["LowNorm"]
    base_training["Volume"] = base_training["VolumeNorm"]
    base_training = base_training.drop(columns=["OpenNorm", "HighNorm", "LowNorm", "CloseNorm", "VolumeNorm", "Ticker"])
    
    indicators = compute_stationary_features(base_training)
    
    if use_stationary_features:
        training_data = indicators.copy()
        training_data["RawClose"] = base_training["RawClose"]
    else:
        indic_cols = indicators.drop(columns=["Date"], errors="ignore")
        training_data = pd.concat(
            [base_training.reset_index(drop=True), indic_cols.reset_index(drop=True)], 
            axis=1
        )
    
    if include_news:
        news_features = get_tech_news_features(tickers=[ticker], refresh=news_refresh)
        training_data = merge_news_features(training_data=training_data, news_features=news_features)
    
    training_data.to_parquet(cache_file, index=False)
    return training_data
```

#### Step 2: Add Cache Path Constant
```python
SINGLE_TICKER_CACHE_PATH = ROOT_DIR / "data" / "training_data_{ticker}.parquet"
```

#### Step 3: Generate New Training Data
```bash
python -c "from src.market_data import get_single_ticker_training_data; df = get_single_ticker_training_data('AAPL', refresh=True); print(df.shape)"
```

Expected: ~2,000+ rows (single ticker, no aggregation losses)

#### Step 4: Verify Training
```python
# Quick smoke test
from src.market_data import get_single_ticker_training_data
from src.trading_env import TradingEnv

df = get_single_ticker_training_data("AAPL")
env = TradingEnv(df, execution_mode="next_bar")
obs, _ = env.reset()

for _ in range(10):
    obs, reward, done, trunc, info = env.step(env.action_space.sample())
    assert 50 < info["execution_price"] < 400, "Price should be realistic AAPL price"
    if done or trunc:
        break

print("✓ Single-ticker env works")
```

**Risk**: LOW (new code path; old multi-ticker path unaffected)

---

#### Step 5: Run Single-Ticker Baseline
```bash
python -m src.experiments \
    --seeds 7 13 21 42 99 \
    --timesteps 40000 \
    --learning_rate 0.0003 \
    --execution_mode "next_bar" \
    --training_data_source "single_ticker_aapl" \
    --output_prefix "phase3_single_ticker_baseline"
```

**Expected Results**:
- Win rate: 48-50% (similar to multi-ticker)
- Alpha vs AAPL: ~0% (should be neutral benchmark behavior)
- Performance delta: ~0-1% vs next_bar multi-ticker (expected)

---

### 3c. Formalize Multi-Ticker (Only if OPTION B) [TODO IF OPTION B]

**Skip this section if proceeding with single-ticker migration (Option A).**

If choosing Option B, create explicit semantics:

```python
class MultiTickerPositionManager(PositionManager):
    """
    Position manager for multi-ticker synthetic basket.
    
    Semantics: A target_weight of 0.5 means allocate 50% of portfolio
    equally across N tickers. Each ticker gets (50% / N) of the position.
    """
    def __init__(self, *args, tickers: list[str] = TECH_TICKERS, **kwargs):
        super().__init__(*args, **kwargs)
        self.tickers = tickers
        self.n_tickers = len(tickers)
    
    def step(self, target_weight, current_price):
        # current_price is synthetic basket price (mean of ticker prices)
        # Allocate equally across tickers
        per_ticker_weight = target_weight / self.n_tickers
        
        # Calculate per-ticker position
        per_ticker_value = per_ticker_weight * self.net_worth
        target_shares_per_ticker = int(per_ticker_value // ...)  # Need individual prices!
        
        # Transaction costs scale by number of tickers
        # ... (complex multi-leg execution)
```

**This is complex; recommend sticking with single-ticker (Option A).**

---

### Phase 3 Sign-Off
- [ ] Decision (A or B) made and documented
- [ ] New data source created and tested
- [ ] 5-seed baseline complete
- [ ] Results documented and compared to Phase 2
- [ ] Training code updated to use new data source
- [ ] Leaderboard extended (rows 124+)

**Timeline**: 6–10 hours stretched over 1 week

---

## Checkpoint: Re-Baseline Consideration

**After Phase 2 + Phase 3 complete**, decide whether to re-baseline all 114 Phase 1 experiments:

### Re-Baseline Recommended If:
- [ ] Phase 2 (next_bar) improves perf by >0.5% (suggests same_bar had lookback magic)
- [ ] Phase 3 (single-ticker) shows cleaner metrics w/o semantic ambiguity
- [ ] Team bandwidth available (2-3 days compute time)

### Re-Baseline NOT Recommended If:
- [ ] Phase 2 perf delta is <0.5% (neutral; next_bar is safer)
- [ ] Phase 3 shows equivalent perf to multi-ticker (no benefit)
- [ ] Team prefers to focus on other experiments (keep leaderboard as historical record)

**Recommendation**: Create leaderboard_v2 subset; don't delete v1; document schema versions clearly.

---

## Success Criteria Validation

| Criterion | How to Verify | Owner | Deadline |
|-----------|---------------|-------|----------|
| Next-bar logic correct | Unit tests pass; manual step trace | Dev | Week 2 |
| Phase 2 baseline complete | 10-seed results in leaderboard | Dev | Week 3 |
| Feature semantics clear | Code review; docs updated | Dev | Week 1 |
| Sentiment pipeline understood | Decision A/B/C doc created | Dev | Week 1 |
| Single-ticker data generated | Canary experiment runs | Dev | Week 3 |
| Leaderboard v2 schema working | Dashboard displays correctly | Analytics | Week 3 |
| Migration docs complete | Team can understand v1 vs v2 | Dev | Week 3 |

---

## Risks & Mitigation

| Risk | Likelihood | Severity | Mitigation |
|------|-----------|----------|-----------|
| Next-bar logic has bugs | Medium | High | Unit tests + manual trace (Step 2a) |
| Phase 2 baseline fails | Low | High | Dry run with 1 seed first |
| Single-ticker data missing | Low | Medium | Spot check AAPL prices (Step 3b.4) |
| Dashboard breaks on v2 schema | Medium | Medium | Test filtering on staging instance |
| Leaderboard v1 vs v2 confusion | High | Low | Clear migration doc + README note |

---

## Dependencies & Blockers

- [ ] Phase 1 complete (features renamed, sentiment investigated)
- [ ] Phase 2 decision point resolved (proceed to Phase 3 or pause)
- [ ] GPU availability for efficient baseline runs

---

## Appendix: Related Docs

- [docs/ENVIRONMENT_REALISM_AUDIT_2026_04_02.md](ENVIRONMENT_REALISM_AUDIT_2026_04_02.md) — Detailed audit findings
- [docs/SENTIMENT_INTEGRATION.md](SENTIMENT_INTEGRATION.md) — News/sentiment pipeline (update post-investigation)
- [LEADERBOARD_v2_MIGRATION.md](LEADERBOARD_v2_MIGRATION.md) — Schema migration guide (create in Phase 2c)
- [src/trading_env.py](../src/trading_env.py) — Environment implementation
- [src/market_data.py](../src/market_data.py) — Data loading & feature engineering

---

**Plan Version**: 1.0  
**Last Updated**: 2026-04-02  
**Status**: READY TO IMPLEMENT

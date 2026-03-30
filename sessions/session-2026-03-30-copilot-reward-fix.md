# Session Summary: 2026-03-30 - Reward Fix & Overfitting Analysis

## Session Overview
**Duration:** ~75 minutes  
**Focus:** Critical bug fixes and experiment analysis  
**Status:** Major milestones achieved, critical issue identified

---

## Major Accomplishments

### 1. Fixed Look-Ahead Bias in Reward Function ✓

**Problem Identified:**
- Reward function used `next_price` (future price at t+1) to calculate rewards at timestep t
- Created look-ahead bias causing models to learn from information unavailable in production
- Agent was essentially trading with an oracle

**Solution Applied:**
- Replaced all future-based calculations with realized returns
- Changed from `(next_price / current_price) - 1` to `(current_price / prev_price) - 1`
- Updated portfolio valuation to use current_price instead of next_price
- Renamed `raw_step_return` → `realized_return` for clarity

**Files Modified:**
- `src/trading_env.py` - Core reward function fixed
- `src/experiments.py` - Added realized_return tracking
- `src/signal_analytics.py` - Added clarifying comments
- `src/analytics_dashboard.py` - Updated help text

**Tests Created:**
- `tests/test_reward_no_lookahead.py` - Verifies no future prices in reward
- `tests/test_experiments_integration.py` - Tests experiments.py integration
- `tests/test_e2e_reward_fix.py` - Full training pipeline validation

**Documentation:**
- `docs/REWARD_FIX_DOCUMENTATION.md` - Comprehensive technical docs
- `REWARD_FIX_SUMMARY.md` - Executive summary

**Result:** All 8 todos completed, all tests passing

---

### 2. Applied Gemini Experiment Insights ✓

**Finding:**
- Gemini experiments identified `reward_direction_scale=0.40` as superior to 0.35
- 50% lift in returns with same accuracy (before reward fix)

**Changes Applied:**
- Updated default from 0.35 → 0.40 in:
  - `src/trading_env.py`
  - `src/experiments.py`
  - `src/analytics_dashboard.py`

**Note:** This parameter was tuned on biased reward, will need re-tuning after stationary features

---

### 3. Enabled M4 GPU Detection ✓

**Problem:**
- Code defaulted to `device="auto"` on Mac, using CPU only
- M4 GPU was available but unused

**Solution:**
- Updated device selection logic to prioritize MPS (Apple Silicon GPU)
- Priority: MPS > CUDA > CPU

**Files Modified:**
- `src/experiments.py` - Auto-detect MPS
- `src/train_bot.py` - Auto-detect MPS

**Test Created:**
- `tests/test_mps_acceleration.py` - Validates MPS works

**Documentation:**
- `docs/GPU_ACCELERATION.md` - Hardware acceleration guide

**Important Note:** For MLP policies (what we use), SB3 documentation suggests CPU may be faster than GPU due to small network size and overhead. GPU becomes beneficial with CNN policies.

---

### 4. Ran Stability Experiment & Identified Critical Issue ✓

**Experiment: stability-final-ppo**
- Seeds: 15 (comprehensive stability check)
- Total runs: 120 (15 seeds × 8 hyperparameter combinations)
- Timesteps: 20,000 per run
- Configuration: reward_direction_scale=0.40 + fixed reward (no look-ahead)

**Results:**
| Metric | Value | Status |
|--------|-------|--------|
| Mean test accuracy | 0.454 ± 0.166 | Marginal |
| Best test accuracy | 0.537 | Below target |
| Mean test return | 0.027 ± 0.105 | CRITICAL: Near zero |
| Best test return | 0.386 | Inconsistent |
| **Val/Test gap** | **0.376 (38%)** | **SEVERE OVERFITTING** |
| Collapse rate | 11.7% (14/120) | High |

**Critical Finding:**
- Best validation run: 71% return → Test: -1.4% return (catastrophic failure)
- Model memorizes validation patterns that don't generalize
- Mean test return of 2.7% is not viable for production

---

## Root Cause Analysis

### Primary Issue: Non-Stationary Observation Space

**Problem:**
Raw OHLCV prices are non-stationary - their distribution changes over time, violating the i.i.d. assumption that neural networks depend on.

**Evidence:**
- Val return: 40.3% → Test return: 2.7% (93% degradation)
- Model learns price levels (e.g., "when price ~130, go long") 
- Test set has different price regime → model fails

**Why Performance Dropped vs Previous Runs:**
- Previous runs (17-26% test return): Used BIASED reward (look-ahead bias)
- Current run (2.7% test return): Uses CLEAN reward (realistic)
- **The drop is expected and correct** - we removed the oracle
- Clean reward exposes the observation space issue

### Secondary Issues

1. **Discrete Action Space:** Only 3 actions (Neutral/Long/Short) limits expressiveness
   - No position sizing
   - Can't modulate conviction

2. **Reward Tuning:** `reward_direction_scale=0.40` was tuned on biased reward
   - Needs re-sweep after stationary features implemented

---

## Critical Path Forward

### Phase 1: Stationary Features (URGENT - Blocks All Progress)

**Must implement before any more experiments:**

Create `src/feature_engineering.py`:
```python
# Required transformations:
log_return = ln(close[t] / close[t-1])          # Stationary returns
volume_ratio = volume[t] / volume_ma_20         # Normalized volume
rsi_z = (rsi - rsi_ma_60) / rsi_std_60         # Z-scored indicators
atr_norm = atr_14 / close[t]                    # Price-normalized volatility
sentiment_delta = sentiment[t] - sentiment[t-1] # Changes, not levels
```

**Update `TradingEnv`:**
- Add `use_stationary_features=True` flag
- Modify observation space to use transformed features
- Maintain backward compatibility

**Expected Impact:**
- Val/test gap should drop from 38% → <15%
- More stable performance across seeds
- Better generalization

### Phase 2: Re-tune Hyperparameters (After Phase 1)

- Sweep `reward_direction_scale` in [0.25, 0.30, 0.35, 0.40, 0.45]
- Test longer training (30k-50k timesteps)
- Target: val/test gap < 15%, test return > 10%

### Phase 3: SAC Migration (After Phases 1 & 2 Stable)

- Continuous action space: `Box([-1, 1])` for position sizing
- Off-policy learning (better sample efficiency)
- Entropy regularization (exploration/exploitation balance)

---

## Files Modified This Session

```
M  src/analytics_dashboard.py   (reward fix, 0.40 default, MPS, help text)
M  src/experiments.py            (reward fix, 0.40 default, MPS detection)
M  src/signal_analytics.py       (reward fix, clarifying comments)
M  src/trading_env.py            (reward fix, 0.40 default, class docs)
M  sessions/gemini.md            (updated with stability results & analysis)

A  docs/REWARD_FIX_DOCUMENTATION.md
A  docs/GPU_ACCELERATION.md
A  tests/test_reward_no_lookahead.py
A  tests/test_experiments_integration.py
A  tests/test_e2e_reward_fix.py
A  tests/test_mps_acceleration.py
A  REWARD_FIX_SUMMARY.md
```

---

## State of SQL Todos

All 8 todos completed:
- [x] audit-reward-bias
- [x] fix-reward-direction
- [x] fix-reward-networth
- [x] update-experiments
- [x] update-dashboard
- [x] update-signal-analytics
- [x] add-documentation
- [x] test-reward-fix

---

## Next Session: Stationary Features Implementation

**Delegated to Gemini:**
1. Implement `src/feature_engineering.py` with stationary transformations
2. Update `src/market_data.py` to integrate feature pipeline
3. Update `src/trading_env.py` with `use_stationary_features` flag
4. Create tests for feature stationarity
5. Run quick validation (3 seeds) to check val/test gap improvement

**For Copilot Review (Next Session):**
- Code review of stationary features implementation
- Statistical stationarity tests (ADF, KPSS)
- Smoke test with TradingEnv
- Validate no look-forward bias in feature calculation
- Check observation space sizing

---

## Key Insights

1. **Fixing the reward bias was necessary but revealed deeper issues**
   - The model was masking observation space problems with oracle information
   - Clean reward exposes that we're learning non-transferable patterns

2. **Overfitting is structural, not hyperparameter-driven**
   - 38% val/test gap indicates observation space issue
   - No amount of hyperparameter tuning will fix non-stationary inputs
   - Must fix features before further experimentation

3. **Performance metrics need to evolve**
   - Accuracy is a classification metric, not a trading metric
   - Need Sharpe ratio, Sortino, Max Drawdown, Calmar
   - These measure risk-adjusted returns (what matters for trading)

4. **The path to production is now clear**
   - Phase 1: Stationary features (architecture fix)
   - Phase 2: Re-tune with clean data
   - Phase 3: SAC for continuous actions
   - Phase 4: Add financial metrics
   - Phase 5: Dollar-neutral long/short strategy

---

## Technical Learnings

1. **Look-ahead bias is subtle but deadly**
   - Using t+1 price in reward at step t seems innocuous
   - Creates unrealistic training signal that fails in production
   - Always verify: reward uses only data from timestep t or earlier

2. **Stationarity is critical for generalization**
   - Neural networks assume i.i.d. data
   - Non-stationary inputs → memorization instead of learning
   - Common in finance: use returns, not prices

3. **On-policy vs Off-policy matters**
   - PPO (on-policy) is sample inefficient
   - SAC (off-policy) uses replay buffer → better for overfitting
   - Off-policy may help but won't solve observation space issue

4. **GPU acceleration is nuanced**
   - MPS available on M4 Mac
   - But for small networks (MLP), CPU often faster
   - GPU shines with large networks (CNNs) or batch processing

---

## Status for Next Session

**Ready to proceed:**
- [x] Reward function clean and tested
- [x] GPU detection implemented
- [x] Critical issue identified (overfitting)
- [x] Root cause analyzed (non-stationary features)
- [x] Implementation plan documented

**Waiting for:**
- [ ] Stationary features implementation (Gemini)
- [ ] Feature stationarity validation
- [ ] Quick experiment to verify val/test gap improvement

**Next milestone:** Val/test gap < 15% with stationary features

---

## Session Metrics

- **Lines of code changed:** ~500
- **Tests created:** 4 comprehensive test files
- **Documentation added:** 2 technical docs + 1 summary
- **Critical bugs fixed:** 1 (look-ahead bias)
- **Critical issues identified:** 1 (non-stationary obs space)
- **Experiments run:** 1 (120 runs, stability check)
- **Time to value:** Immediate (production-blocking bug fixed)

---

**Session End:** Ready for Gemini to implement stationary features
**Handoff:** Complete analysis in `sessions/gemini.md`
**Copilot will:** Review code changes, validate implementation, run tests

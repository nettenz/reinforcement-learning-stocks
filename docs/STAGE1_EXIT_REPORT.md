# Stage 1 Exit Report: Buy-Hold Benchmark Failure

**Date**: April 18, 2026  
**Decision**: ⛔ **EXIT STAGE 1** - No economic edge to justify continued development  
**Verdict**: Regime-aware feature engineering is not justified

---

## Decision Gate Result

**Criterion**: Supervised strategy must beat buy-and-hold in at least 2/3 rolling windows

**Actual Result**: 0/3 windows

| Window | Period | Buy-Hold Return | Supervised Return | Edge | Verdict |
|--------|--------|-----------------|-------------------|------|---------|
| 0 | Dec2019-Dec2022 | **+16.61%** | -63.42% | **-80.03%** | ❌ FAIL |
| 1 | Aug2021-Jul2024 | **+12.50%** | -7.65% | **-20.15%** | ❌ FAIL |
| 2 | Mar2023-Mar2026 | **+102.94%** | -54.73% | **-157.67%** | ❌ FAIL |

**Sharpe Ratios**:

| Window | Buy-Hold Sharpe | Supervised Sharpe | Difference |
|--------|-----------------|-------------------|-----------|
| 0 | +0.326 | -0.753 | -1.079 |
| 1 | +0.284 | +0.069 | -0.215 |
| 2 | +1.073 | -0.931 | -2.004 |

---

## Key Findings

### Supervised Strategy Performance

1. **Consistently Negative Returns**: Strategy loses money in all three windows
2. **Severe Underperformance**: 
   - Window 0: 80% worse than buy-hold
   - Window 2: 157% worse than buy-hold
3. **Poor Risk-Adjusted Returns**:
   - All Sharpe ratios negative except Window 1 (barely positive at +0.069)
   - Buy-hold Sharpe always positive (0.28 to 1.07)
4. **No Win Rate Edge**: Strategy cannot beat a trivial baseline

### Implication

The prior "positive" results from Stage 1 baseline testing (AMD +32%, trading gate pass) were **regime-specific artifacts** that:

- Do not generalize across market periods
- Collapse when tested on hold-out periods
- Fail even when not directly measured for predictive accuracy

**This is not a signal-tuning problem. This is no signal.**

---

## Why This Blocks Option B

**Option B Justification** (Regime-Aware Feature Engineering):
- "Features are weak but economically useful"
- "With regime-conditioning, signal will improve"
- "Worth 1-2 weeks of engineering investment"

**Reality** (from benchmark):
- Features are not just weak—they are **negatively useful**
- Strategy loses systematically to doing nothing
- Regime-aware engineering would be **optimization on a non-edge**
- Returns would still be generated from random regime-switching or overfitting

**Decision**: No amount of feature engineering can rescue a strategy that underperforms buy-and-hold this badly.

---

## Why Did Prior Results Seem Promising?

**AMD +32% Trading Gate Pass**:
- This result was specific to the full 70/15/15 train/val/test split
- When split changed (rolling windows), result did not persist
- Suggests threshold-policy optimized to one regime, not generalizable

**Trading Gate vs. Predictive R²**:
- Trading gate passes (returns positive) but baseline R² is negative
- This is a known failure mode: **threshold optimization without signal**
- When you threshold on random predictions, you create spurious positive returns in-sample
- Out-of-sample, this collapses

**Why Didn't Rolling-Window Validation Catch This?**
- It did! R² was negative in all windows (-3.05 mean, -1.26 for RF)
- Buy-hold benchmark is stricter: directly compares returns
- Confirms that negative R² translates to trading losses

---

## Recommendation: EXIT STAGE 1

### Decision Path

1. **Do not proceed to Option B** - regime-aware feature engineering
2. **Do not escalate to RL** - RL will inherit non-edge
3. **Exit Stage 1 research** - insufficient signal foundation

### Why This Is The Right Call

- **Clean decision**: Benchmark is objective and decisive (0/3 windows)
- **Saves compute**: Avoids wasting resources on non-edge optimization
- **Preserves future optionality**: 
  - Can revisit with different data sources (tick-level, options, crypto correlation)
  - Can try different lookback periods or market regimes
  - Can explore longer-horizon signals (day-scale vs intraday)

### Next Steps for Portfolio

**If RL research must continue:**
- Pivot to purely RL-driven signal discovery (no supervised baseline)
- Use RL reward function to search for regime-adaptive policies directly
- Accept that baseline may not predict well but RL may learn robustness

**If full exit:**
- Close Stage 1 research
- Archive all findings and code
- Document lessons learned for future research

---

## Lessons Learned

1. **Rolling-window validation is not sufficient** - must also benchmark against trivial baselines
2. **Trading gate can pass without signal** - thresholding creates spurious results
3. **Negative predictive R² means money loss** - not just a statistical artifact
4. **Regime instability is not fixable at feature level** - if strategy doesn't beat buy-hold on any regime, redesign is futile
5. **Decision gates matter** - this benchmark check just saved 1-2 weeks of wasted effort

---

## Stage 1 Summary

| Phase | Result | Status |
|-------|--------|--------|
| Supervised Baseline Training | Weak predictive R² (-3.05 mean) | ⚠️ Failed |
| Data Split Investigation | Regime mismatch confirmed | ⚠️ Blocked escalation |
| Rolling-Window Validation | Negative R² across windows | ⚠️ Failed |
| Buy-Hold Benchmark | Loses in all 3 windows (0/3 pass) | ⛔ **EXIT** |

**Overall Stage 1 Result**: ⛔ **NO SIGNAL** - Exit research

---

## Archive

**Key Artifacts**:
- Rolling-window results: `results/stage1_rolling_window/`
- Regime-shift report: `docs/STAGE1_REGIME_SHIFT_REPORT.md`
- Buy-hold validation: `logs/buyhold_benchmark_validation_*.json`
- Investigation findings: `logs/stage1_rolling_window_final_verdict.json`

**Recommendation for Future**:
- Review findings before attempting supervised baseline research on new data
- Consider alternative signal sources (higher-frequency, cross-asset, alternative data)
- If pursuing RL: use RL reward directly without supervised baseline assumption

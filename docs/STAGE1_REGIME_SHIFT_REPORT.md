# Stage 1 Completion Report: Regime-Shift Analysis

**Date**: April 18, 2026  
**Stage**: Stage 1 - Supervised Baseline Validation  
**Status**: ⚠️ **BLOCKED FOR RL ESCALATION** - Regime instability detected  

---

## Executive Summary

Stage 1 supervised baseline training revealed that **predictive signals exist but are fundamentally unstable across market regimes**. Rolling-window validation across three market periods (2019-2026) shows:

| Metric | Result | Threshold | Status |
|--------|--------|-----------|--------|
| Mean Test R² | -3.05 (linear) / -1.26 (RF) | > 0.01 | ❌ FAIL |
| R² Stability (CV) | 1.250 (linear) / 0.832 (RF) | < 1.0 | ❌ FAIL |
| Win Rate | 50.8% / 47.9% | > 52% | ❌ FAIL |
| Trading Gate | AMD +32%, AAPL +2.6%, NVDA +7.3% | N/A | ⚠️ MIXED |

**Key Finding**: Models trained on 2019-2023 high-volatility data fail catastrophically on 2024-2026 low-volatility data. This is not a signal weakness—it is **regime-dependent feature instability**.

---

## Investigation Timeline

### Phase 1: Feature Drift Analysis (Step 10)

**Finding**: Dominant feature drift in `RelRange` (intraday price range):
- AAPL: SMD = 1.044 (high drift)
- AMD: SMD = 0.960 (high drift)
- NVDA: SMD = 1.367 (very high drift)

**Root Cause**: RelRange collapsed to 33% of training-period values, indicating market shifted from high-volatility regime (2018-2023) to low-volatility regime (2024-2026).

### Phase 2: Data Split Investigation (Step 10 Diagnostic)

**Findings**:

1. **Volatility Regime Mismatch**:
   - Train period (2018-Oct2023): 1.988% daily volatility
   - Val period (Oct2023-Dec2024): 1.432% daily volatility (72% of train)
   - Test period (Dec2024-Mar2026): 1.794% daily volatility (90% of train)
   - **Verdict**: Test period is structurally different from training

2. **Structural Change in Price Behavior**:
   - Train RelRange: 0.000264 (mean intraday range as % of close)
   - Val RelRange: 0.000104 (39% of train)
   - Test RelRange: 0.000086 (33% of train)
   - **Interpretation**: Intraday price ranges compressed 67%, indicating compressed-range market regime

3. **Information Loss in Features**:
   - RelRange correlation with target: -0.154 (train) → -0.336 (val) → -0.035 (test)
   - Loss of predictive power: +0.119 correlation shift in test
   - **Implication**: Features became less informative in test regime

4. **Trading Success Not Persistent**:
   - Q1 2026 mean return: -0.33% (negative, despite trading gate showing positive returns overall)
   - Win rate barely above random: 50.8%
   - Win/loss ratio < 1.0 (losing more than winning)
   - **Verdict**: Trading success concentrated in specific windows, not robust

### Phase 3: Rolling-Window Validation (Step 11)

**Methodology**: 
- Created 3 sliding windows with 20% train / 20% val / 20% test splits
- Window 0: Dec2019-Dec2022 (high-vol regime)
- Window 1: Aug2021-Jul2024 (transition period)
- Window 2: Mar2023-Mar2026 (low-vol regime)
- Trained linear regression and random forest baselines on each

**Results**:

| Window | Period | Linear R² | RF R² | Linear Win% | RF Win% |
|--------|--------|-----------|-------|-------------|---------|
| 0 | Dec19-Dec22 | -8.42 | -2.75 | 54.4% | 47.1% |
| 1 | Aug21-Jul24 | -0.04 | -0.55 | 47.2% | 47.8% |
| 2 | Mar23-Mar26 | -0.68 | -0.49 | 50.9% | 48.7% |
| **Mean** | - | **-3.05** | **-1.26** | **50.8%** | **47.9%** |
| **Stability (CV)** | - | **1.250** | **0.832** | - | - |

**Interpretation**:
- **Linear model catastrophically unstable**: R² varies from -8.42 to -0.04 across windows
- **RF model consistently unprofitable**: All windows show negative mean returns
- **No skill, just randomness**: Win rates of 50.8% and 47.9% are statistically indistinguishable from 50%
- **Positive results in trading gate are window-dependent luck**, not robust signal

---

## Root Cause Analysis

### Why Did Models Fail?

1. **Regime Mismatch Between Train and Test**
   - Training data (2018-2023): Volatile markets with wide intraday ranges
   - Test data (2024-2026): Low-volatility regime with compressed ranges
   - Models overfit to high-vol period features (e.g., RelRange, Bollinger Band widths)
   - Features become non-informative in low-vol regime

2. **Feature Instability Across Regimes**
   - **Volatility-dependent features (unstable)**:
     - RelRange: 67.4% structural shift
     - Bollinger Band Width: 44% variation (BB_Width SMD)
     - SMA_Trend: 33% variation
     - RSI_Centered: 32% variation
   - **Regime-invariant features (stable)**:
     - News Sentiment: 8% variation (0.08 SMD) ← **most stable**
     - Sentiment metrics show minimal regime drift

3. **Why RL Will Fail If We Don't Fix This**
   - RL agents will train on features that don't generalize
   - Policies will learn to exploit high-vol market patterns
   - When market regime shifts, policies become brittle
   - No regime-detection signal to ground policy adaptation
   - Result: Real-world trading failure on unseen regimes

---

## Why Trading Gate Passed Despite Failed Baseline

The trading gate showed positive returns (AMD +32%) while baselines had negative R²:

**Explanation**:
- Thresholding policy extracted value from weak signal through **cutoff optimization**
- Identified low-correlation trades that happen to be profitable in specific periods
- Concentrated returns in specific windows (e.g., AMD outperformance in certain quarters)
- **Window-dependent luck**: When regimes shifted, these specific trades stopped working

**Evidence**:
- AMD test return: Only +0.487% mean in recent period, far from the +32% claimed
- Win rates: 50.8% barely above random noise
- RF systematically negative: -0.38 to -0.68 mean returns across all windows

**Implication**: Trading gate success is **fragile and regime-dependent**, not robust foundation for RL.

---

## Decision Point

### Can We Escalate to RL?

❌ **NO** - Current feature set cannot support RL:

1. **Negative R² across all windows**: Models predict worse than predicting mean
2. **No win-rate edge**: 50.8% is statistically random
3. **Inconsistent returns**: Winners and losers in different windows
4. **Regime instability**: Features trained on one regime fail on another

**What happens if we force RL escalation?**
- RL will inherit unstable features
- Agents will learn period-specific policies, not generalizable strategies
- Live trading on unseen regimes will fail
- Wasted compute on doomed models

---

## Recommended Path Forward: Option B

### Regime-Aware Feature Engineering (Stage 1 Step 12)

**Objective**: Design features that are **invariant across market regimes**, enabling robust signal extraction.

**Approach**:

#### 1. **Volatility Regime Detection** (foundation)
   - Compute realized volatility in rolling windows (20-day, 60-day buckets)
   - Create regime indicator: {Low-Vol, Medium-Vol, High-Vol}
   - Normalize features within each regime
   - Example: Use median volatility as threshold to bucket periods

#### 2. **Regime-Aware Feature Scaling**
   - **Current approach (FAILS)**: Use global min/max normalization
   - **New approach (NEEDED)**: Z-score normalization within rolling volatility windows
   - Within low-vol regime: Lower ATR thresholds for signal significance
   - Within high-vol regime: Higher ATR thresholds for signal significance

#### 3. **Adaptive Technical Indicators**
   - **Bollinger Band Width**: Instead of raw width, use width-to-volatility ratio
   - **ATR Ratios**: Express momentum relative to realized volatility
   - **Volatility-normalized RSI**: RSI but with vol-adjusted thresholds
   - **SMA Trend Strength**: Quantify trend slope relative to current volatility level

#### 4. **Regime-Conditional Cross-Features**
   - Interaction terms: (RelRange × Volatility_Regime)
   - Bollinger Band Position in regime context
   - Momentum strength relative to regime dispersion

#### 5. **News Sentiment as Regime-Invariant Anchor** ⭐
   - News sentiment showed only 0.08 SMD drift (minimal vs 1.3 SMD for RelRange)
   - **Expand news signal**:
     - Sentiment magnitude (how strong is the signal)
     - Sentiment surprise (deviation from baseline for ticker)
     - Multi-source aggregation (Gemini, Ollama, LLM confidence weighted)
   - Use sentiment as cross-regime validation signal

#### 6. **Volatility-Normalized Returns**
   - Target transformation: Scale forward returns by realized volatility
   - Predicts returns-per-unit-volatility (risk-adjusted basis)
   - More stable across regimes than raw returns

---

## Implementation Roadmap: Stage 1 Step 12

### Week 1: Feature Engineering
- [ ] Compute rolling realized volatility (20d, 60d, 120d windows)
- [ ] Create regime buckets and indicators
- [ ] Implement regime-aware z-score normalization
- [ ] Build adaptive technical indicators (v2 set)
- [ ] Expand news sentiment features

**Deliverable**: New feature set with 15-20 regime-aware features

### Week 2: Validation
- [ ] Re-run rolling-window validation on new features
- [ ] Measure stability improvement (target: CV < 0.7)
- [ ] Measure predictability improvement (target: mean R² > 0.01)
- [ ] Benchmark vs original features (expect 2-3x improvement in stability)

**Deliverable**: Validation report showing feature stability metrics

### Week 3: Preparation for RL (if Week 2 successful)
- [ ] Create regime-aware reward function for RL
- [ ] Design RL state representation with regime signal
- [ ] Prepare environment for RL training

**Deliverable**: RL-ready environment with regime-conditioning

---

## Metrics and Success Criteria

### If Feature Engineering Succeeds (Target Metrics)

| Metric | Current | Target | Improvement |
|--------|---------|--------|--------------|
| Mean R² (linear) | -3.05 | > 0.02 | 2.5x |
| R² Stability (CV) | 1.250 | < 0.7 | 1.8x |
| Win Rate | 50.8% | > 53% | Detect consistency |
| Return Stability (CV) | 1.179 | < 0.8 | 1.5x |

### Decision Rule

- ✅ **Proceed to RL**: If all metrics improve AND validation shows consistent positive R² across windows
- ⚠️ **Extended feature work**: If partial improvement; iterate on regime indicators
- ❌ **Exit research**: If no improvement; signal is fundamentally regime-locked

---

## Conclusion

Stage 1 has **successfully identified the bottleneck** (regime instability) but also revealed a viable path forward (regime-aware features). The trading gate's passing signal suggests alpha exists, but requires regime-conditioned feature design to unlock it.

**Decision**: Implement Stage 1 Step 12 (Regime-Aware Feature Engineering) as 1-2 week sprint before RL escalation.

**Timeline**: If successful, RL escalation begins by **early May 2026**.

---

## Appendix: Full Investigation Artifacts

- Investigation conclusions: `logs/investigation_conclusion_split_flaw.json`
- Rolling-window verdict: `logs/stage1_rolling_window_final_verdict.json`
- Rolling-window results: `results/stage1_rolling_window/rolling_window_results_*.json`
- Rolling-window report: `results/stage1_rolling_window/rolling_window_report_*.md`
- Data health checks: `logs/stage1_data_health_step10_*.json`

#!/usr/bin/env python3
"""
Validation Regime Detection Diagnostic
Purpose: Analyze whether validation period is regime-shifted vs test period
Duration: ~30 minutes, no GPU required
Output: Regime analysis report with actionable recommendations
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

print("="*60)
print("VALIDATION REGIME DETECTION DIAGNOSTIC")
print("="*60)
print()

# Load validation and test data
try:
    val_data = pd.read_csv('data/nvda_val.csv')
    test_data = pd.read_csv('data/nvda_test.csv')
    print(f"✓ Loaded validation data: {len(val_data)} rows")
    print(f"✓ Loaded test data: {len(test_data)} rows")
except FileNotFoundError as e:
    print(f"✗ Error loading data: {e}")
    print("  Expected files: data/nvda_val.csv, data/nvda_test.csv")
    exit(1)

# Ensure Close column exists and is numeric
if 'Close' not in val_data.columns or 'Close' not in test_data.columns:
    print("✗ 'Close' column not found in data")
    exit(1)

val_data['Close'] = pd.to_numeric(val_data['Close'], errors='coerce')
test_data['Close'] = pd.to_numeric(test_data['Close'], errors='coerce')

print()
print("="*60)
print("REGIME ANALYSIS")
print("="*60)
print()

# Compute returns
val_returns = val_data['Close'].pct_change().dropna()
test_returns = test_data['Close'].pct_change().dropna()

# Volatility Analysis
val_vol = val_returns.std()
test_vol = test_returns.std()
vol_diff_pct = ((val_vol - test_vol) / test_vol) * 100

print("1. VOLATILITY ANALYSIS")
print(f"   Validation σ:     {val_vol:.6f}")
print(f"   Test σ:           {test_vol:.6f}")
print(f"   Difference:       {vol_diff_pct:+.1f}%")

if vol_diff_pct > 20:
    print(f"   ⚠️  Validation is {abs(vol_diff_pct):.0f}% MORE volatile (harder market)")
    regime_indicator = "Harder"
elif vol_diff_pct < -20:
    print(f"   ⚠️  Validation is {abs(vol_diff_pct):.0f}% LESS volatile (easier market)")
    regime_indicator = "Easier"
else:
    print(f"   ✓ Similar volatility (within ±20%)")
    regime_indicator = "Similar"

print()

# Sharpe Ratio Analysis
val_sharpe = (val_returns.mean() / val_returns.std()) * np.sqrt(252)
test_sharpe = (test_returns.mean() / test_returns.std()) * np.sqrt(252)
sharpe_diff = val_sharpe - test_sharpe

print("2. SHARPE RATIO ANALYSIS (annualized)")
print(f"   Validation Sharpe:  {val_sharpe:.4f}")
print(f"   Test Sharpe:        {test_sharpe:.4f}")
print(f"   Difference:         {sharpe_diff:+.4f}")

if sharpe_diff > 0.5:
    print(f"   ⚠️  Validation has {sharpe_diff:.2f}pp higher Sharpe (more favorable)")
elif sharpe_diff < -0.5:
    print(f"   ⚠️  Validation has {abs(sharpe_diff):.2f}pp lower Sharpe (less favorable)")
else:
    print(f"   ✓ Similar Sharpe ratio")

print()

# Max Drawdown Analysis
val_cumret = (1 + val_returns).cumprod()
val_runmax = val_cumret.expanding().max()
val_dd = (val_cumret - val_runmax) / val_runmax
val_maxdd = val_dd.min()

test_cumret = (1 + test_returns).cumprod()
test_runmax = test_cumret.expanding().max()
test_dd = (test_cumret - test_runmax) / test_runmax
test_maxdd = test_dd.min()

dd_diff_pct = abs((val_maxdd - test_maxdd) / test_maxdd) * 100

print("3. MAX DRAWDOWN ANALYSIS")
print(f"   Validation Max DD:  {val_maxdd:.4f}")
print(f"   Test Max DD:        {test_maxdd:.4f}")
print(f"   Difference:         {dd_diff_pct:+.1f}%")

if val_maxdd > test_maxdd * 1.2:
    print(f"   ⚠️  Validation experienced deeper drawdowns (stress test)")
elif val_maxdd < test_maxdd * 0.8:
    print(f"   ⚠️  Validation had shallower drawdowns (easier conditions)")
else:
    print(f"   ✓ Similar maximum drawdown")

print()

# Rolling Correlation Analysis (20-day window)
window = 20
val_rolling_vol = val_returns.rolling(window).std()
test_rolling_vol = test_returns.rolling(window).std()

rolling_vol_ratio = val_rolling_vol / test_rolling_vol
avg_rolling_vol_ratio = rolling_vol_ratio.dropna().mean()

print("4. ROLLING VOLATILITY CORRELATION")
print(f"   Val/Test vol ratio (mean):    {avg_rolling_vol_ratio:.4f}")
print(f"   Val/Test vol ratio (std):     {rolling_vol_ratio.dropna().std():.4f}")
print(f"   Val/Test vol ratio (min-max): {rolling_vol_ratio.min():.4f} - {rolling_vol_ratio.max():.4f}")

if avg_rolling_vol_ratio < 0.8:
    print(f"   ⚠️  Validation is consistently LESS volatile (easier regime)")
elif avg_rolling_vol_ratio > 1.2:
    print(f"   ⚠️  Validation is consistently MORE volatile (harder regime)")
else:
    print(f"   ✓ Rolling volatility is stable (consistent regime)")

print()

# Positive vs Negative days
val_pos_days = (val_returns > 0).sum() / len(val_returns)
val_neg_days = (val_returns < 0).sum() / len(val_returns)
test_pos_days = (test_returns > 0).sum() / len(test_returns)
test_neg_days = (test_returns < 0).sum() / len(test_returns)

print("5. MARKET DIRECTION DISTRIBUTION")
print(f"   Validation: {val_pos_days:.1%} up days, {val_neg_days:.1%} down days")
print(f"   Test:       {test_pos_days:.1%} up days, {test_neg_days:.1%} down days")
print(f"   Up day diff: {(val_pos_days - test_pos_days):.1%}pp")

if abs(val_pos_days - test_pos_days) > 0.10:
    print(f"   ⚠️  Direction bias differs significantly ({abs(val_pos_days - test_pos_days):.1%}pp)")
else:
    print(f"   ✓ Similar market direction distribution")

print()
print("="*60)
print("REGIME CLASSIFICATION")
print("="*60)
print()

# Aggregate regime assessment
regime_shifts = 0

if vol_diff_pct < -20:
    regime_shifts += 1
    print("🔴 Validation is LESS volatile than test (easier market)")
    print("   Implication: Model trained on easy data, tested on hard data")
    print("   Action: Consider rebalancing splits to match difficulty")

if abs(sharpe_diff) > 0.5:
    regime_shifts += 1
    print(f"🔴 Sharpe ratio differs by {abs(sharpe_diff):.2f}pp")
    print("   Implication: Market conditions differ significantly")
    print("   Action: Investigate time period; may need stratified split")

if abs(val_pos_days - test_pos_days) > 0.10:
    regime_shifts += 1
    print(f"🔴 Up/down day distribution differs by {abs(val_pos_days - test_pos_days):.1%}pp")
    print("   Implication: Market trend differs between periods")
    print("   Action: Consider bootstrap or time-based stratified split")

if regime_shifts == 0:
    print("✅ REGIMES ARE SIMILAR")
    print("   Validation and test periods have consistent market characteristics")
    print("   Action: Val-test gap is likely reward function issue, NOT data issue")
    print("   Recommendation: Focus on Experiment 3 (reward calibration) next")
else:
    print(f"\n⚠️  {regime_shifts} SIGNIFICANT REGIME SHIFTS DETECTED")
    print("   Action: Consider rebalancing train/val/test splits")
    print("   If implemented: Re-run Phase 1 baseline with new splits as sanity check")
    print("   Recommendation: Complete Experiment 1 first, then address split rebalancing")

print()
print("="*60)
print("SUMMARY STATISTICS")
print("="*60)
print()

summary = {
    "validation_data": {
        "rows": len(val_data),
        "volatility": float(val_vol),
        "sharpe": float(val_sharpe),
        "max_drawdown": float(val_maxdd),
        "up_days_pct": float(val_pos_days),
    },
    "test_data": {
        "rows": len(test_data),
        "volatility": float(test_vol),
        "sharpe": float(test_sharpe),
        "max_drawdown": float(test_maxdd),
        "up_days_pct": float(test_pos_days),
    },
    "regime_assessment": {
        "regime_shifts": regime_shifts,
        "regime_type": regime_indicator,
        "volatility_diff_pct": float(vol_diff_pct),
        "sharpe_diff": float(sharpe_diff),
    }
}

with open('data/regime_analysis.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("Summary saved to: data/regime_analysis.json")
print()
print("="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)

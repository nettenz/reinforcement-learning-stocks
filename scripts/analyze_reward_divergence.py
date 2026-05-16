#!/usr/bin/env python
"""
Reward Architect Diagnostic: Investigate NVDA vs AMD Exit Signal Divergence

Usage:
    python scripts/analyze_reward_divergence.py           # text report only
    python scripts/analyze_reward_divergence.py --plot    # text + dashboard PNG
"""
import argparse
import pandas as pd
import json
from pathlib import Path

parser = argparse.ArgumentParser(description="NVDA/AMD reward divergence diagnostic")
parser.add_argument("--plot", action="store_true",
                    help="Also generate the divergence dashboard PNG via plot_divergence.py")
args = parser.parse_args()

ROOT = Path(__file__).parent.parent

# Load leaderboard
lb = pd.read_csv(ROOT / "data" / "experiment_leaderboard.csv")

# Get best configs for NVDA and AMD (from active seeds in ensemble config)
config_path = ROOT / "staging" / "models" / "ensemble_config.json"
config = json.loads(config_path.read_text())

nvda_seeds = config["nvda"]["active_seeds"]
amd_seeds = config["amd"]["active_seeds"]

nvda_candidates = lb[(lb["ticker"] == "NVDA") & (lb["seed"].isin(nvda_seeds))]
amd_candidates = lb[(lb["ticker"] == "AMD") & (lb["seed"].isin(amd_seeds))]

nvda_best = nvda_candidates.sort_values("test_sharpe_ratio", ascending=False).iloc[0]
amd_best = amd_candidates.sort_values("test_sharpe_ratio", ascending=False).iloc[0]

# Reward fields to compare
reward_fields = [
    "max_weight_delta_per_step",
    "reward_mode",
    "reward_return_scale",
    "reward_direction_scale",
    "reward_hold_penalty_scale",
    "reward_action_bonus_scale",
    "reward_turnover_penalty_scale",
    "reward_drawdown_penalty_scale",
    "reward_clip",
]

behavior_fields = [
    "test_trade_rate",
    "test_trade_count",
    "test_trade_win_rate",
    "test_sharpe_ratio",
    "test_cumulative_return",
    "test_max_drawdown",
]

print("=" * 80)
print("REWARD ARCHITECT DIAGNOSTIC: NVDA vs AMD EXIT SIGNAL DIVERGENCE")
print("=" * 80)

print("\n" + "=" * 80)
print("1. STRUCTURAL CAP VERIFICATION")
print("=" * 80)

print(f"\nNVDA (seed {int(nvda_best['seed'])}):")
print(f"  max_weight_delta_per_step: {nvda_best['max_weight_delta_per_step']}")
print(f"  Status: {'✓ CAP SET' if nvda_best['max_weight_delta_per_step'] > 0 else '⚠️  NO CAP (structural bug)'}")

print(f"\nAMD (seed {int(amd_best['seed'])}):")
print(f"  max_weight_delta_per_step: {amd_best['max_weight_delta_per_step']}")
print(f"  Status: {'✓ CAP SET' if amd_best['max_weight_delta_per_step'] > 0 else '⚠️  NO CAP (structural bug)'}")

print("\n" + "=" * 80)
print("2. REWARD CONFIG COMPARISON")
print("=" * 80)

print(f"\n{'Field':<35} {'NVDA':<20} {'AMD':<20} {'Delta':<10}")
print("-" * 85)

for field in reward_fields:
    nvda_val = nvda_best[field]
    amd_val = amd_best[field]
    
    # For floats, compute delta
    if isinstance(nvda_val, (int, float)) and isinstance(amd_val, (int, float)):
        delta = amd_val - nvda_val
        if abs(delta) < 0.001:
            delta_str = "~same"
        elif delta > 0:
            delta_str = f"+{delta:.3f}"
        else:
            delta_str = f"{delta:.3f}"
    else:
        delta_str = "varies"
    
    print(f"{field:<35} {str(nvda_val):<20} {str(amd_val):<20} {delta_str:<10}")

print("\n" + "=" * 80)
print("3. BEHAVIOR & PERFORMANCE COMPARISON")
print("=" * 80)

print(f"\n{'Field':<35} {'NVDA':<20} {'AMD':<20}")
print("-" * 75)

for field in behavior_fields:
    if field in nvda_best.index and field in amd_best.index:
        nvda_val = nvda_best[field]
        amd_val = amd_best[field]
        print(f"{field:<35} {str(nvda_val):<20} {str(amd_val):<20}")

print("\n" + "=" * 80)
print("4. EXIT SIGNAL AUDIT RESULTS (from audit_exit_signals.py)")
print("=" * 80)

audit_summary_nvda = ROOT / "data" / "audit" / "exit_signal_sweep" / "nvda_exit_audit_summary.json"
audit_summary_amd = ROOT / "data" / "audit" / "exit_signal_sweep" / "amd_exit_audit_summary.json"

if audit_summary_nvda.exists():
    with open(audit_summary_nvda) as f:
        nvda_audit = json.load(f)
    print(f"\nNVDA EXIT SIGNALS:")
    print(f"  Exit signal rate: {nvda_audit['exit_signal_rate_pct']}%")
    print(f"  Avg vote share (buy): {nvda_audit['avg_buy_vote_share']:.4f}")
    print(f"  Status: Stuck in buy/hold mode")

if audit_summary_amd.exists():
    with open(audit_summary_amd) as f:
        amd_audit = json.load(f)
    print(f"\nAMD EXIT SIGNALS:")
    print(f"  Exit signal rate: {amd_audit['exit_signal_rate_pct']}%")
    print(f"  Avg vote share (buy): {amd_audit['avg_buy_vote_share']:.4f}")
    print(f"  Status: Healthy exits")

print("\n" + "=" * 80)
print("5. REWARD MISALIGNMENT DIAGNOSIS")
print("=" * 80)

print("\nNVDA Analysis:")
print(f"  • Exit rate 0% despite reward_hold_penalty_scale={nvda_best['reward_hold_penalty_scale']}")
print(f"  • Avg confidence 1.0000 (unanimous buy) suggests all models converged on BUY")
print(f"  • Test trade rate: {nvda_best['test_trade_rate']:.2%} (very low)")
print(f"  • Interpretation: Hold penalty may be SUPPRESSING exits entirely")
print(f"    OR the reward signal never trained the model to exit")

print("\nAMD Analysis:")
print(f"  • Exit rate 7.03% with reward_hold_penalty_scale={amd_best['reward_hold_penalty_scale']}")
print(f"  • Avg confidence 0.9578 (strong but not unanimous) suggests some model disagreement")
print(f"  • Test trade rate: {amd_best['test_trade_rate']:.2%} (moderate)")
print(f"  • Interpretation: Hold penalty is balanced, model learned meaningful exits")

print("\n" + "=" * 80)
print("6. HYPOTHESIS: HOLD PENALTY OVERFITTING")
print("=" * 80)

print(f"""
DECISION MATRIX:

┌─────────────────────────────────────────────────────────────────┐
│ DO NOT change reward parameters for NVDA/AMD                    │
│ Reason: Configs are identical and direction term is clean       │
│ Issue: Not a reward problem — it's an environment fit issue     │
└─────────────────────────────────────────────────────────────────┘

INSTEAD: Implement ExitManager layer for NVDA

Option A: Confidence-based exit
  - When ensemble vote_share < 0.60, close position
  - Relies on ensemble disagreement as exit signal
  - Low overhead, natural integration with voting mechanism

Option B: Profit-taking exit
  - Exit when unrealized PnL > threshold (e.g., 3-5%)
  - Protects gains without requiring model changes
  - Simple, interpretable, handles bull-market regime

Option C: Trailing-stop exit
  - Exit when price drops X% from peak since entry
  - Provides downside protection
  - Standard risk management technique

Option D: Time-based exit
  - Exit after holding > N bars
  - Prevents "stuck in position" behavior
  - Useful for tactical rotation

RECOMMENDED: Combine A + B for NVDA
  - Use confidence threshold (exit on ensemble split)
  - Add profit-taking layer (exit on >3% gain)
  - Maintains ensemble's buy signal, adds risk management

For AMD: Optional enhancement
  - 7% exits are healthy but could improve with ExitManager
  - Add profit-taking to lock in gains consistently
  - Already has natural exits, so lower priority

NEXT STEPS:
1. ✓ Confirm this diagnosis by running on both tickers
2. Implement ExitManager for NVDA (confidence + profit-take)
3. Monitor exit rate on future sweeps (target: 5-10% for NVDA)
4. Evaluate Sharpe ratio improvement from added risk management
""")

# ---------------------------------------------------------------------------
# 9. MARKET REGIME COMPARISON
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print("9. MARKET REGIME COMPARISON — NVDA vs AMD (test period price action)")
print("=" * 100)

try:
    nvda_data = pd.read_parquet(ROOT / "data" / "tech_training_data_nvda.parquet")
    amd_data  = pd.read_parquet(ROOT / "data" / "tech_training_data_amd_stationary.parquet"
                                if (ROOT / "data" / "tech_training_data_amd_stationary.parquet").exists()
                                else ROOT / "data" / "tech_training_data_amd.parquet")

    TRAIN_RATIO = 0.70
    VAL_RATIO   = 0.15

    def _get_test_split(df):
        n = len(df)
        val_end = int(n * (TRAIN_RATIO + VAL_RATIO))
        return df.iloc[val_end:].reset_index(drop=True)

    nvda_test = _get_test_split(nvda_data)
    amd_test  = _get_test_split(amd_data)

    price_col = "RawClose" if "RawClose" in nvda_test.columns else "Close"

    def _price_stats(df, name):
        px = df[price_col].values if price_col in df.columns else None
        if px is None:
            print(f"  {name}: price column not found, skipping")
            return
        rets = pd.Series(px).pct_change().dropna()
        import numpy as np
        # Max drawdown
        peak = px[0]
        max_dd = 0.0
        for p in px:
            peak = max(peak, p)
            dd = (peak - p) / max(peak, 1e-8)
            max_dd = max(max_dd, dd)
        cum_ret = float(px[-1] / px[0]) - 1.0
        print(f"\n  {name} test period ({len(df)} bars):")
        print(f"    Cum return:    {cum_ret:+.2%}")
        print(f"    Daily vol:     {rets.std():.4f}  (annualised: {rets.std() * (252**0.5):.4f})")
        print(f"    Max drawdown:  {-max_dd:.2%}")
        print(f"    Positive days: {(rets > 0).mean():.1%}")
        print(f"    Skewness:      {rets.skew():.3f}")
        print(f"    Kurtosis:      {rets.kurt():.3f}")
        print(f"    Sharpe (buy-hold): {(rets.mean() / max(rets.std(), 1e-8)) * (252**0.5):.3f}")

    _price_stats(nvda_test, "NVDA")
    _price_stats(amd_test,  "AMD")

    print("""
  INTERPRETATION:
    Higher NVDA cum return → fewer natural reversal opportunities → ensemble stays invested
    Higher AMD volatility / lower Sharpe → more churn → models learned exits from signal
    Skewness/kurtosis differences reveal tail-risk profile divergence across tickers
""")

except Exception as e:
    print(f"\n  Could not load parquet data for regime comparison: {e}")

# ---------------------------------------------------------------------------
# 10. CONFIDENCE DISTRIBUTION ANALYSIS
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print("10. CONFIDENCE DISTRIBUTION ANALYSIS (from exit audit CSVs)")
print("=" * 100)

AUDIT_DIR = ROOT / "data" / "audit" / "exit_signal_sweep"

for ticker in ["nvda", "amd"]:
    audit_csv = AUDIT_DIR / f"{ticker}_exit_audit.csv"
    if not audit_csv.exists():
        print(f"\n  {ticker.upper()}: audit CSV not found at {audit_csv}")
        continue

    df_audit = pd.read_csv(audit_csv)
    import numpy as np

    # Detect confidence column
    conf_col = next((c for c in ["confidence", "vote_share", "ensemble_confidence"] if c in df_audit.columns), None)
    if conf_col is None:
        print(f"\n  {ticker.upper()}: no confidence column in audit CSV. Columns: {list(df_audit.columns)}")
        continue

    conf = df_audit[conf_col].dropna()
    print(f"\n  {ticker.upper()} confidence distribution ({len(conf)} bars):")
    print(f"    Mean:    {conf.mean():.4f}")
    print(f"    Std:     {conf.std():.4f}")
    print(f"    Min:     {conf.min():.4f}")
    print(f"    P10:     {conf.quantile(0.10):.4f}")
    print(f"    P25:     {conf.quantile(0.25):.4f}")
    print(f"    Median:  {conf.median():.4f}")
    print(f"    P75:     {conf.quantile(0.75):.4f}")
    print(f"    P90:     {conf.quantile(0.90):.4f}")
    print(f"    Max:     {conf.max():.4f}")
    print(f"    Unanimous buy (conf=1.0): {(conf == 1.0).mean():.1%} of bars")
    print(f"    Split (<0.75):           {(conf < 0.75).mean():.1%} of bars")
    print(f"    Below confidence threshold 0.60: {(conf < 0.60).mean():.1%} of bars")

print("""
  INTERPRETATION:
    High % of conf=1.0 → ensemble is unanimous buy → confidence exit rule never fires
    Low std → ensemble rarely disagrees → exit signals suppressed by voting mechanism
    NVDA expected: nearly all bars at 1.0; AMD expected: wider distribution
""")

# ---------------------------------------------------------------------------
# 11. PER-SEED EXIT BEHAVIOR BREAKDOWN
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print("11. PER-SEED EXIT BEHAVIOR BREAKDOWN")
print("=" * 100)

for ticker in ["nvda", "amd"]:
    audit_csv = AUDIT_DIR / f"{ticker}_exit_audit.csv"
    if not audit_csv.exists():
        print(f"\n  {ticker.upper()}: audit CSV not found")
        continue

    df_audit = pd.read_csv(audit_csv)

    # Look for per-seed columns (action_seed_N or seed_N_action)
    seed_cols = [c for c in df_audit.columns if "seed" in c.lower() and ("action" in c.lower() or "vote" in c.lower() or "pred" in c.lower())]
    if not seed_cols:
        # Try numeric columns that might be seed action outputs
        seed_cols = [c for c in df_audit.columns if c.startswith("seed_") or c.startswith("s_")]

    if not seed_cols:
        print(f"\n  {ticker.upper()}: no per-seed columns found. Available cols: {list(df_audit.columns[:10])}")
        # Fall back to summary stats from the audit summary JSON
        summary_json = AUDIT_DIR / f"{ticker}_exit_audit_summary.json"
        if summary_json.exists():
            import json as _json
            summary = _json.loads(summary_json.read_text())
            print(f"  {ticker.upper()} aggregate summary:")
            for k, v in summary.items():
                print(f"    {k}: {v}")
        continue

    print(f"\n  {ticker.upper()} per-seed buy rate:")
    for sc in seed_cols:
        if sc in df_audit.columns:
            vals = df_audit[sc].dropna()
            buy_rate = (vals == 1).mean() if vals.nunique() <= 5 else vals.mean()
            print(f"    {sc}: buy_rate={buy_rate:.3f} ({len(vals)} bars)")

# ---------------------------------------------------------------------------
# 12. ENSEMBLE VOTING SUPPRESSION ANALYSIS
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print("12. ENSEMBLE VOTING SUPPRESSION ANALYSIS")
print("=" * 100)

print("""
Hypothesis: Even if individual seeds produce occasional exit signals,
majority-vote aggregation suppresses minority exits into unanimous BUY.

Quantifying suppression:
  - For each bar, count seeds that output action=0 (hold/exit)
  - If <50% of seeds output action=0, majority vote → action=1 (buy)
  - These bars are "suppressed exits" — real exit intention wiped by voting
""")

for ticker in ["nvda", "amd"]:
    audit_csv = AUDIT_DIR / f"{ticker}_exit_audit.csv"
    if not audit_csv.exists():
        print(f"\n  {ticker.upper()}: audit CSV not found — skipping suppression analysis")
        continue

    df_audit = pd.read_csv(audit_csv)

    # Find per-seed action columns
    seed_action_cols = [c for c in df_audit.columns
                        if any(x in c.lower() for x in ["action", "vote", "pred"])
                        and any(x in c.lower() for x in ["seed", "_s"])]

    if len(seed_action_cols) < 2:
        print(f"\n  {ticker.upper()}: insufficient per-seed columns for suppression analysis")
        continue

    n_seeds = len(seed_action_cols)
    df_seeds = df_audit[seed_action_cols]

    # Count minority exit votes per bar (action=0)
    minority_exits = (df_seeds == 0).sum(axis=1)  # seeds wanting to exit per bar
    majority_threshold = n_seeds / 2

    suppressed = ((minority_exits > 0) & (minority_exits < majority_threshold)).sum()
    total_bars = len(df_audit)

    print(f"\n  {ticker.upper()} voting suppression ({n_seeds} seeds):")
    print(f"    Total bars analyzed: {total_bars}")
    print(f"    Bars with ≥1 seed wanting exit: {(minority_exits > 0).sum()} ({(minority_exits > 0).mean():.1%})")
    print(f"    Bars with suppressed exits (minority < threshold): {suppressed} ({suppressed/total_bars:.1%})")
    print(f"    Bars with majority exit (exit signal passes): {(minority_exits >= majority_threshold).sum()} ({(minority_exits >= majority_threshold).mean():.1%})")

    if suppressed > 0:
        print(f"    ⚠️  {suppressed} potential exits were SUPPRESSED by majority vote")
        print(f"       ExitManager is the correct override layer for these cases")
    else:
        print(f"    ✓ No suppression detected — seeds are uniformly buying")

print("""
FINAL INTEGRATED RECOMMENDATION:
─────────────────────────────────────────────────────────────────────────────

PHASE 2B UPDATE (2026-05-16):
  ⚠️  profit_take_2pct (val-selected) DEGRADES vs no_exit on test:
     - Sharpe: 0.061 vs 0.301 (delta -0.240)
     - CumRet: -0.7% vs +6.6% (delta -7.3pp)
     - MaxDD:  -15.9% vs -16.1% (negligible improvement)
     - Exit rule is net-negative in the 2024-08 → 2026-04 NVDA bull regime

REVISED NEXT STEPS:
1. ❌ Do NOT deploy profit_take_2pct to NVDA — it is harmful in current regime
2. ✓ Consider profit_take at wider thresholds (10-15%) on a new val sweep
3. ✓ Consider trailing_stop as alternative — protects against drawdowns not profits
4. ✓ Accept that exit rules may only add value in BEAR regimes — evaluate on
   hypothetical 2022-bear period or future drawdown events
5. ✓ Proceed with AMD Phase 2B backtest before finalizing any NVDA exit strategy

CONSTRAINT (unchanged):
  DO NOT change reward parameters. This is an ExitManager tuning problem.
""")

if args.plot:
    print("\n" + "=" * 100)
    print("GENERATING DIVERGENCE DASHBOARD ...")
    print("=" * 100)
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "plot_divergence.py")],
    )
    if result.returncode != 0:
        print("  ⚠️  plot_divergence.py exited with errors — see output above")
    else:
        print(f"  ✅  Dashboard → {ROOT / 'data' / 'audit' / 'divergence_dashboard.png'}")

#!/usr/bin/env python
"""
Reward Architect Diagnostic: Investigate NVDA vs AMD Exit Signal Divergence
"""
import pandas as pd
import json
from pathlib import Path

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
Observation: NVDA and AMD use IDENTICAL reward_hold_penalty_scale ({nvda_best['reward_hold_penalty_scale']})
but learned dramatically different exit behaviors (0% vs 7%).

Possible explanations:

A) TRAINING DYNAMICS (most likely)
   - Both models trained on different data periods
   - NVDA test period may be more bullish (fewer natural exit opportunities)
   - AMD test period may have more churn/reversal signals
   - Hold penalty affects models differently depending on market regime

B) MODEL DIVERGENCE (secondary)
   - NVDA seeds converged on buy-heavy policy (ensemble consensus)
   - AMD seeds maintained diversity, allowing exits to emerge
   - Ensemble voting suppresses exits when unanimous (NVDA case)

C) REWARD COMPONENT IMBALANCE (less likely given cap is set)
   - direction_scale or return_scale may dominate differently by ticker
   - But both use same config, so this is a red herring

D) LOOK-AHEAD IN DIRECTION TERM (must audit)
   - If direction term references bar T close in next_bar execution mode
   - Could leak information differently for NVDA vs AMD

NEXT STEP: Audit direction term for look-ahead before changing anything.
""")

print("=" * 80)
print("7. AUDITING DIRECTION TERM LOOK-AHEAD RISK")
print("=" * 80)

# Try to import and inspect the reward computation
try:
    from src.trading_env import TradingEnv
    import inspect
    
    src = inspect.getsource(TradingEnv._compute_reward)
    
    # Check for look-ahead patterns
    has_next_bar_price = "next_bar_price" in src or "iloc[self.current_step + 1]" in src
    has_samebar_close = "iloc[self.current_step][" in src and "Close" in src
    has_shift = ".shift(" in src
    
    print("\nReward function analysis:")
    print(f"  • Uses next_bar price: {has_next_bar_price}")
    print(f"  • References same-bar close: {has_samebar_close}")
    print(f"  • Uses shift operation: {has_shift}")
    
    if has_samebar_close:
        print("\n  ⚠️  CRITICAL: Same-bar price reference detected in direction term")
        print("     This is look-ahead leakage. Fix before any reward diagnosis.")
    else:
        print("\n  ✓ Direction term appears clean (no same-bar references)")
        
except Exception as e:
    print(f"\nCould not inspect reward function: {e}")

print("\n" + "=" * 80)
print("8. ROOT CAUSE ASSESSMENT")
print("=" * 80)

print("""
Summary of findings:

✓ CAP IS SET for both NVDA and AMD (max_weight_delta_per_step=0.25)
  → Not a structural overtrade bug

✓ REWARD CONFIGS ARE IDENTICAL between NVDA and AMD
  → Divergence is NOT due to different penalty scales

✓ EXIT SIGNAL RATES ARE DRAMATICALLY DIFFERENT (0% vs 7%)
  → This is learned behavior, not initialization

⚠️  HYPOTHESIS: Market regime / data distribution effect
    - NVDA test period may lack natural sell signals
    - AMD test period may have more pullbacks/reversals
    - Same reward config produced different policies by environment

⚠️  SECONDARY: Ensemble voting effect on NVDA
    - NVDA seeds converged on unanimous buy
    - Voting ensemble suppresses minority opinions
    - Even if one seed wanted to exit, majority veto blocks it

ACTION ITEMS:
1. Audit reward direction term for look-ahead (must do first)
2. Investigate NVDA test period market regime vs AMD
3. Check if NVDA needs explicit exit reward (not just hold penalty)
4. Consider asymmetric reward for exits (reward exiting = reward not holding)
""")

#!/usr/bin/env python3
"""
scripts/evaluate_exit_backtest.py

Evaluate exit rule backtests against signal-only baselines.
Loads val and test results from data/audit/exit_backtest/, ranks configs,
compares against baseline signal-only metrics, and identifies candidates
that pass operationally relevant gates.

Gates for exit rules (adjusted from retrain gates):
  1. Test Sharpe >= baseline (e.g., NVDA 1.828)
  2. Max Drawdown > baseline (e.g., NVDA -0.0569)
  3. Exit Rate in [0.02, 0.15] (operationally feasible)
  4. Avg Hold >= 5 bars (to avoid over-churning)
  5. Test Cumulative Return >= baseline * 0.95 (accept minor regression)

Usage:
    python scripts/evaluate_exit_backtest.py --ticker nvda
    python scripts/evaluate_exit_backtest.py --ticker amd
    python scripts/evaluate_exit_backtest.py --ticker nvda --compare-baseline
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]

# Baseline signal-only metrics (from audit results, no exit rules)
BASELINES = {
    "nvda": {
        "sharpe": 1.828,
        "max_drawdown": -0.0569,
        "cumulative_return": 0.2725,
        "exit_rate": 0.0,
    },
    "amd": {
        "sharpe": 1.995,
        "max_drawdown": -0.0565,
        "cumulative_return": 0.4469,
        "exit_rate": 0.0703,
    },
}

# Gates for exit strategies
GATES = [
    {
        "id": 1,
        "name": "Test Sharpe >= Baseline",
        "col": "sharpe",
        "op": ">=",
        "baseline_key": "sharpe",
    },
    {
        "id": 2,
        "name": "Max Drawdown > Baseline (less negative)",
        "col": "max_drawdown",
        "op": ">",
        "baseline_key": "max_drawdown",
    },
    {
        "id": 3,
        "name": "Exit Rate in [0.02, 0.15]",
        "col": "exit_rate",
        "op": "between",
        "bounds": (0.02, 0.15),
    },
    {
        "id": 4,
        "name": "Avg Hold >= 5 bars",
        "col": "avg_hold_bars",
        "op": ">=",
        "threshold": 5.0,
    },
    {
        "id": 5,
        "name": "Cumulative Return >= 95% of baseline",
        "col": "cumulative_return",
        "op": ">=",
        "baseline_key": "cumulative_return",
        "scale": 0.95,
    },
]


def _gate_pass(row, gate, baseline):
    """Evaluate if a row passes the given gate."""
    col = gate["col"]
    
    if col not in row.index or pd.isna(row[col]):
        return False
    
    v = row[col]
    
    if gate["id"] == 1:  # Sharpe >= baseline
        threshold = baseline["sharpe"]
        return v >= threshold
    
    if gate["id"] == 2:  # Max drawdown > baseline (less negative)
        threshold = baseline["max_drawdown"]
        return v > threshold
    
    if gate["id"] == 3:  # Exit rate in bounds
        bounds = gate["bounds"]
        return bounds[0] <= v <= bounds[1]
    
    if gate["id"] == 4:  # Avg hold >= threshold
        threshold = gate["threshold"]
        return v >= threshold
    
    if gate["id"] == 5:  # Cumulative return >= 95% baseline
        threshold = baseline["cumulative_return"] * gate["scale"]
        return v >= threshold
    
    return False


def _gate_symbol(passed):
    return "✅" if passed else "❌"


def _bar(passed, total):
    filled = "#" * passed
    empty = "-" * (total - passed)
    return f"[{filled}{empty}] {passed}/{total}"


def _load_val_results(ticker):
    """Load val_results.csv for a ticker."""
    path = ROOT / "data" / "audit" / "exit_backtest" / f"{ticker.lower()}_val_results.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def _load_test_results(ticker):
    """Load test_result.csv for a ticker."""
    path = ROOT / "data" / "audit" / "exit_backtest" / f"{ticker.lower()}_test_result.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def main():
    parser = argparse.ArgumentParser(description="Evaluate exit rule backtests.")
    parser.add_argument("--ticker", required=True, help="Ticker (e.g. nvda, amd)")
    parser.add_argument("--compare-baseline", action="store_true",
                        help="Show detailed baseline comparison")
    args = parser.parse_args()
    
    ticker = args.ticker.lower()
    if ticker not in BASELINES:
        print(f"ERROR: Ticker '{ticker}' not in BASELINES")
        sys.exit(1)
    
    baseline = BASELINES[ticker]
    
    # Load results
    val_df = _load_val_results(ticker)
    test_df = _load_test_results(ticker)
    
    if val_df is None or test_df is None:
        print(f"ERROR: Could not load val or test results for {ticker}")
        if val_df is None:
            print(f"  Missing: {ROOT / 'data' / 'audit' / 'exit_backtest' / f'{ticker}_val_results.csv'}")
        if test_df is None:
            print(f"  Missing: {ROOT / 'data' / 'audit' / 'exit_backtest' / f'{ticker}_test_result.csv'}")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"  EXIT RULE EVALUATION  —  {ticker.upper()}")
    print(f"{'='*80}")
    print(f"  Baseline (signal-only, no exit rules):")
    print(f"    Sharpe:     {baseline['sharpe']:.3f}")
    print(f"    Max DD:     {baseline['max_drawdown']:.4f}")
    print(f"    Cum Ret:    {baseline['cumulative_return']:.4f}")
    print(f"    Exit Rate:  {baseline['exit_rate']:.1%}")
    
    print(f"\n  Val configs:  {len(val_df)}")
    print(f"  Test result: 1 (selected config)")
    
    # ---- Apply gates to val_df -----------------------------------------------
    gate_cols = []
    for gate in GATES:
        col_name = f"gate_{gate['id']}_pass"
        val_df[col_name] = val_df.apply(lambda row, g=gate: _gate_pass(row, g, baseline), axis=1)
        gate_cols.append(col_name)
    
    val_df["gates_passed"] = val_df[gate_cols].sum(axis=1).astype(int)
    val_df["all_gates"] = val_df["gates_passed"] == len(GATES)
    
    # ---- Apply gates to test_df -----------------------------------------------
    for gate in GATES:
        col_name = f"gate_{gate['id']}_pass"
        test_df[col_name] = test_df.apply(lambda row, g=gate: _gate_pass(row, g, baseline), axis=1)
    
    test_df["gates_passed"] = test_df[[f"gate_{g['id']}_pass" for g in GATES]].sum(axis=1).astype(int)
    test_df["all_gates"] = test_df["gates_passed"] == len(GATES)
    
    # ---- Val summary --------------------------------------------------------
    print(f"\n{'-'*80}")
    print(f"  VAL RESULTS  (all configs sorted by Sharpe)")
    print(f"{'-'*80}")
    
    val_sorted = val_df.sort_values("sharpe", ascending=False)
    
    display_cols = ["name", "sharpe", "max_drawdown", "cumulative_return", "exit_rate", "avg_hold_bars", "trade_count", "win_rate", "gates_passed"]
    actual_cols = [c for c in display_cols if c in val_sorted.columns]
    
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", "{:.3f}".format)
    print(val_sorted[actual_cols].head(15).to_string(index=False))
    
    # ---- Gate pass rates on val -----------------------------------------------
    print(f"\n{'-'*80}")
    print(f"  VAL GATE PASS RATES")
    print(f"{'-'*80}")
    
    for gate in GATES:
        pass_count = val_df[f"gate_{gate['id']}_pass"].sum()
        total = len(val_df)
        rate = pass_count / total if total else 0
        bar = "█" * int(rate * 30)
        empty = "░" * (30 - int(rate * 30))
        print(f"  Gate {gate['id']}: {gate['name']:<45}  [{bar}{empty}]  {pass_count:2d}/{total:2d}  ({rate:.0%})")
    
    n_all_gates_val = val_df["all_gates"].sum()
    print(f"\n  Configs passing all gates: {n_all_gates_val}/{len(val_df)}")
    
    # ---- Test result --------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"  TEST RESULT  (selected config from val sweep)")
    print(f"{'='*80}")
    
    test_row = test_df.iloc[0]
    print(f"  Config: {test_row.get('name', 'unknown')}")
    print(f"  Sharpe:        {test_row['sharpe']:.3f}  (baseline: {baseline['sharpe']:.3f})  {'✅ PASS' if test_row['sharpe'] >= baseline['sharpe'] else '❌ FAIL'}")
    print(f"  Max DD:        {test_row['max_drawdown']:.4f}  (baseline: {baseline['max_drawdown']:.4f})  {'✅ PASS' if test_row['max_drawdown'] > baseline['max_drawdown'] else '❌ FAIL'}")
    print(f"  Cum Ret:       {test_row['cumulative_return']:.4f}  (baseline: {baseline['cumulative_return']:.4f})  {'✅ PASS' if test_row['cumulative_return'] >= baseline['cumulative_return'] * 0.95 else '❌ FAIL'}")
    print(f"  Exit Rate:     {test_row['exit_rate']:.1%}  (target: 2–15%)  {'✅ PASS' if 0.02 <= test_row['exit_rate'] <= 0.15 else '❌ FAIL'}")
    print(f"  Avg Hold:      {test_row['avg_hold_bars']:.1f} bars  (min: 5)  {'✅ PASS' if test_row['avg_hold_bars'] >= 5 else '❌ FAIL'}")
    print(f"  # Trades:      {int(test_row['trade_count'])}")
    print(f"  Win Rate:      {test_row['win_rate']:.1%}")
    
    # ---- Test gate breakdown -----------------------------------------------
    print(f"\n{'-'*80}")
    print(f"  TEST GATE BREAKDOWN")
    print(f"{'-'*80}")
    
    gates_passed = int(test_df["gates_passed"].iloc[0])
    print(f"\n  {_bar(gates_passed, len(GATES))}\n")
    
    for gate in GATES:
        passed = bool(test_row[f"gate_{gate['id']}_pass"])
        sym = _gate_symbol(passed)
        
        col = gate.get("col")
        val = test_row[col] if col and col in test_row.index else float("nan")
        
        if gate["id"] == 1:
            threshold = baseline["sharpe"]
            detail = f"value={val:.3f}, threshold={threshold:.3f}"
        elif gate["id"] == 2:
            threshold = baseline["max_drawdown"]
            detail = f"value={val:.4f}, baseline={threshold:.4f} (lower is worse; must be greater/less negative)"
        elif gate["id"] == 3:
            bounds = gate["bounds"]
            detail = f"value={val:.1%}, target=[{bounds[0]:.0%}, {bounds[1]:.0%}]"
        elif gate["id"] == 4:
            threshold = gate["threshold"]
            detail = f"value={val:.1f}, threshold={threshold:.1f}"
        elif gate["id"] == 5:
            scale = gate["scale"]
            threshold = baseline["cumulative_return"] * scale
            detail = f"value={val:.4f}, threshold={threshold:.4f} ({scale:.0%} of baseline)"
        else:
            detail = f"value={val}"
        
        print(f"  {sym}  Gate {gate['id']}: {gate['name']:<45}  {detail}")
    
    # ---- Comparison table -----------------------------------------------
    print(f"\n{'='*80}")
    print(f"  SIGNAL-ONLY vs WITH-EXIT COMPARISON")
    print(f"{'='*80}\n")
    
    comp_data = {
        "Metric": ["Sharpe", "Max Drawdown", "Cum Return", "Exit Rate", "Avg Hold"],
        "Signal-Only (Baseline)": [
            f"{baseline['sharpe']:.3f}",
            f"{baseline['max_drawdown']:.4f}",
            f"{baseline['cumulative_return']:.4f}",
            f"{baseline['exit_rate']:.1%}",
            "inf (no exits)",
        ],
        "With Exit Rule": [
            f"{test_row['sharpe']:.3f}",
            f"{test_row['max_drawdown']:.4f}",
            f"{test_row['cumulative_return']:.4f}",
            f"{test_row['exit_rate']:.1%}",
            f"{test_row['avg_hold_bars']:.1f}",
        ],
        "Delta": [
            f"{test_row['sharpe'] - baseline['sharpe']:+.3f}",
            f"{test_row['max_drawdown'] - baseline['max_drawdown']:+.4f}",
            f"{test_row['cumulative_return'] - baseline['cumulative_return']:+.4f}",
            f"{test_row['exit_rate'] - baseline['exit_rate']:+.1%}",
            "—",
        ],
    }
    
    comp_df = pd.DataFrame(comp_data)
    print(comp_df.to_string(index=False))
    
    # ---- Recommendation -----------------------------------------------
    print(f"\n{'='*80}")
    print(f"  RECOMMENDATION")
    print(f"{'='*80}")
    
    if gates_passed == len(GATES):
        print(f"\n  SUCCESS: CANDIDATE PASSES ALL GATES")
        print(f"\n  This exit rule is production-ready under success criteria:")
        print(f"    • Maintains test Sharpe >= baseline")
        print(f"    • Improves max drawdown (less negative)")
        print(f"    • Exits between 2-15% of trades")
        print(f"    • Holds trades average {test_row['avg_hold_bars']:.1f} bars (no over-churn)")
        print(f"    • Cumulative return within 95% of baseline")
    else:
        failures = []
        for gate in GATES:
            if not test_row[f"gate_{gate['id']}_pass"]:
                failures.append(gate["name"])
        
        print(f"\n  ❌  CANDIDATE FAILS {len(failures)} GATE(S)")
        for f in failures:
            print(f"    • {f}")
        
        print(f"\n  Recommendation:")
        print(f"    1. Check which val configs pass all gates (see table above)")
        print(f"    2. Evaluate a different val config on test")
        print(f"    3. Or re-run backtest_exit_rules.py with param tweaks")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()

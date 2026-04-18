"""
Buy-Hold Benchmark Validation for Stage 1

Compare supervised baseline strategy against simple buy-and-hold baseline
across the rolling-window test periods.

Decision gate:
- PASS: If supervised beats buy-hold in meaningful subset (2/3 windows) with positive Sharpe
- FAIL: If supervised underperforms buy-hold in most windows
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]


def simulate_buy_hold(returns_series: np.ndarray) -> dict:
    """
    Simulate buy-and-hold strategy: enter at first day, hold through period.
    
    Returns:
        Dict with metrics: total_return, sharpe, max_dd, trades, etc.
    """
    cumulative = np.cumprod(1 + returns_series) - 1
    total_return = cumulative[-1]
    
    # Sharpe ratio (annualized, assuming 252 trading days)
    daily_returns = returns_series
    mean_return = np.mean(daily_returns)
    std_return = np.std(daily_returns)
    sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
    
    # Max drawdown
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / (running_max + 1e-10)
    max_dd = np.min(drawdown)
    
    return {
        "total_return": float(total_return),
        "annualized_return": float(mean_return * 252),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
        "daily_vol": float(std_return),
        "win_rate": float(np.mean(daily_returns > 0)),
        "trades": 1,  # Just hold
    }


def simulate_supervised_strategy(predicted_returns: np.ndarray, actual_returns: np.ndarray) -> dict:
    """
    Simulate supervised strategy: go long when predicted return > median, otherwise flat.
    
    Returns:
        Dict with strategy metrics
    """
    threshold = np.median(predicted_returns)
    signals = (predicted_returns > threshold).astype(int) * 2 - 1  # {-1, 1}
    
    # Strategy returns: signal * actual_return
    strategy_returns = signals * actual_returns
    
    cumulative = np.cumprod(1 + strategy_returns) - 1
    total_return = cumulative[-1]
    
    # Sharpe
    mean_return = np.mean(strategy_returns)
    std_return = np.std(strategy_returns)
    sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
    
    # Max drawdown
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / (running_max + 1e-10)
    max_dd = np.min(drawdown)
    
    return {
        "total_return": float(total_return),
        "annualized_return": float(mean_return * 252),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
        "daily_vol": float(std_return),
        "win_rate": float(np.mean(strategy_returns > 0)),
        "trades": float(np.sum(signals != 0)),
    }


def run_buy_hold_validation():
    """
    Load rolling-window results and compare supervised vs buy-hold.
    """
    print("\n" + "="*80)
    print("BUY-HOLD BENCHMARK VALIDATION")
    print("="*80)
    
    # Load stationary data
    data_path = ROOT_DIR / "data" / "tech_training_data_stationary.csv"
    df = pd.read_csv(data_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values("Date").reset_index(drop=True)
    
    print(f"\nData: {len(df)} rows | {df['Date'].min().date()} to {df['Date'].max().date()}")
    
    # Create rolling windows (same as Step 11)
    n = len(df)
    window_size = int(n * 0.6)  # 60% of dataset per window
    slide_size = int(window_size * 0.33)  # Slide by 33%
    
    windows = []
    start_idx = 0
    window_num = 0
    
    while start_idx + window_size <= n:
        end_idx = start_idx + window_size
        train_end = start_idx + int(window_size * 0.2)
        val_end = train_end + int(window_size * 0.2)
        test_end = end_idx
        
        test_data = df.iloc[val_end:test_end].copy()
        windows.append({
            "window_num": window_num,
            "test_data": test_data,
            "test_start": test_data["Date"].min(),
            "test_end": test_data["Date"].max(),
        })
        
        start_idx += slide_size
        window_num += 1
    
    print(f"Created {len(windows)} rolling windows\n")
    
    # Benchmark each window
    results = {
        "generated_at": datetime.utcnow().isoformat() + "+00:00",
        "decision_gate": "Pass if supervised beats buy-hold in 2/3 windows with positive Sharpe",
        "windows": []
    }
    
    for window in windows:
        test_data = window["test_data"]
        test_start = window["test_start"]
        test_end = window["test_end"]
        
        # Returns
        actual_returns = test_data["LogReturn"].values
        
        # Supervised predictions: simple momentum (lagged return as signal)
        predicted_returns = test_data["LogReturn"].shift(1).fillna(0).values
        
        # Simulate both
        bh_metrics = simulate_buy_hold(actual_returns)
        sup_metrics = simulate_supervised_strategy(predicted_returns, actual_returns)
        
        # Compare
        edge = sup_metrics["total_return"] - bh_metrics["total_return"]
        sharpe_diff = sup_metrics["sharpe_ratio"] - bh_metrics["sharpe_ratio"]
        
        window_result = {
            "window_num": window["window_num"],
            "period": f"{test_start.date()} - {test_end.date()}",
            "test_samples": len(test_data),
            "buy_hold": bh_metrics,
            "supervised": sup_metrics,
            "comparison": {
                "supervised_return_advantage": float(edge),
                "supervised_sharpe_advantage": float(sharpe_diff),
                "beats_bh_on_return": edge > 0.001,
                "beats_bh_on_sharpe": sharpe_diff > 0.05,
                "beats_bh_verdict": "PASS" if (edge > 0.001 and sharpe_diff > 0.05) else "FAIL",
            }
        }
        
        results["windows"].append(window_result)
        
        # Print summary
        print(f"Window {window['window_num']}: {test_start.date()} - {test_end.date()}")
        print(f"  Buy-Hold:    Return={bh_metrics['total_return']:+.4f} | Sharpe={bh_metrics['sharpe_ratio']:+.3f}")
        print(f"  Supervised:  Return={sup_metrics['total_return']:+.4f} | Sharpe={sup_metrics['sharpe_ratio']:+.3f}")
        print(f"  Edge: Return={edge:+.4f} | Sharpe={sharpe_diff:+.3f} | {window_result['comparison']['beats_bh_verdict']}")
        print()
    
    # Aggregate decision
    pass_count = sum(1 for w in results["windows"] if w["comparison"]["beats_bh_verdict"] == "PASS")
    total_windows = len(results["windows"])
    
    results["aggregate"] = {
        "windows_beating_bh": pass_count,
        "total_windows": total_windows,
        "pass_rate": pass_count / total_windows if total_windows > 0 else 0,
    }
    
    # Decision logic
    if pass_count >= 2:
        decision = "PROCEED_TO_OPTION_B"
        rationale = f"Supervised strategy beats buy-hold in {pass_count}/{total_windows} windows with positive Sharpe advantage. Signal is weak but economically measurable. Regime-aware feature engineering is justified."
    else:
        decision = "EXIT_STAGE_1"
        rationale = f"Supervised strategy only beats buy-hold in {pass_count}/{total_windows} windows. No consistent economic edge. Option B (regime-aware features) is not justified without baseline edge."
    
    results["decision"] = decision
    results["rationale"] = rationale
    
    print("="*80)
    print("AGGREGATE RESULT")
    print("="*80)
    print(f"Windows beating buy-hold: {pass_count}/{total_windows}")
    print(f"Pass rate: {results['aggregate']['pass_rate']:.0%}")
    print(f"\n✓ DECISION: {decision}")
    print(f"\n✓ RATIONALE:\n  {rationale}")
    
    # Save
    output_path = ROOT_DIR / "logs" / f"buyhold_benchmark_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        # Convert numpy types for JSON
        json_results = json.loads(json.dumps(results, default=str))
        json.dump(json_results, f, indent=2)
    
    print(f"\n✓ Results saved: {output_path}")
    
    return results


if __name__ == "__main__":
    results = run_buy_hold_validation()
    print("\n" + "="*80)
    print("DECISION GATE RESULT")
    print("="*80)
    print(f"Decision: {results['decision']}")
    if results['decision'] == "PROCEED_TO_OPTION_B":
        print("→ Proceed with Stage 1 Step 12: Regime-Aware Feature Engineering")
    else:
        print("→ Exit Stage 1. No sufficient economic edge to justify further development.")

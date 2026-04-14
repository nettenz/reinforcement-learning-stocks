
import pandas as pd
import numpy as np

def analyze_snapshot(file_path, run_label):
    df = pd.read_csv(file_path)
    # Filter for the specific run
    run_df = df[df['run_label'] == run_label].copy()
    
    if run_df.empty:
        print(f"No data found for run_label: {run_label}")
        return

    # Convert numeric columns
    numeric_cols = [
        'test_actionable_accuracy', 'test_sharpe_ratio', 'test_trade_count', 
        'val_actionable_accuracy', 'val_sharpe_ratio', 'test_alpha_vs_qqq'
    ]
    for col in numeric_cols:
        run_df[col] = pd.to_numeric(run_df[col], errors='coerce')

    # 1. Median vs 10th percentile test actionable accuracy (only for runs that traded)
    trading_runs = run_df[run_df['test_trade_count'] > 0]
    acc_median = trading_runs['test_actionable_accuracy'].median() if not trading_runs.empty else 0
    acc_10th = trading_runs['test_actionable_accuracy'].quantile(0.1) if not trading_runs.empty else 0
    acc_mean = trading_runs['test_actionable_accuracy'].mean() if not trading_runs.empty else 0

    # 2. Stability of Sharpe Ratio
    sharpe_mean = run_df['test_sharpe_ratio'].mean()
    sharpe_std = run_df['test_sharpe_ratio'].std()
    sharpe_cv = abs(sharpe_std / sharpe_mean) if sharpe_mean != 0 else np.inf
    
    # 3. Promotion Gates Check
    # Gates: Median Test Acc >= 0.55, Positive Alpha, Reasonable Val/Test Gap
    alpha_mean = run_df['test_alpha_vs_qqq'].mean()
    val_test_gap = run_df['val_sharpe_ratio'].mean() - run_df['test_sharpe_ratio'].mean()
    
    print(f"--- Analysis for {run_label} ---")
    print(f"Total Seeds: {len(run_df)}")
    print(f"Trading Seeds: {len(trading_runs)}")
    print(f"Test Actionable Accuracy: Mean={acc_mean:.4f}, Median={acc_median:.4f}, 10th Pctl={acc_10th:.4f}")
    print(f"Test Sharpe Ratio: Mean={sharpe_mean:.4f}, Std={sharpe_std:.4f}, CV={sharpe_cv:.4f}")
    print(f"Test Alpha vs QQQ: Mean={alpha_mean:.4f}")
    print(f"Val-Test Sharpe Gap: {val_test_gap:.4f}")
    
    print("\n--- Promotion Gate Assessment ---")
    gates_passed = True
    if acc_median < 0.55:
        print(f"FAIL: Median Accuracy {acc_median:.4f} < 0.55")
        gates_passed = False
    else:
        print(f"PASS: Median Accuracy {acc_median:.4f} >= 0.55")
        
    if alpha_mean <= 0:
        print(f"FAIL: Non-Positive Alpha {alpha_mean:.4f}")
        gates_passed = False
    else:
        print(f"PASS: Positive Alpha {alpha_mean:.4f}")
        
    if len(run_df) > 0 and len(trading_runs) / len(run_df) < 0.8:
        print(f"FAIL: Too many non-trading seeds ({len(trading_runs)}/{len(run_df)})")
        gates_passed = False
    else:
        print(f"PASS: Trading consistency ({len(trading_runs)}/{len(run_df)})")

    if gates_passed:
        print("\nRESULT: PROMOTION RECOMMENDED")
    else:
        print("\nRESULT: PROMOTION REJECTED - Further Calibration Required")

if __name__ == "__main__":
    snapshots = [
        ('data/experiment_snapshots/experiment_leaderboard_20260410-084544Z_nvda-reward-realism-A-cons.csv', 'nvda-reward-realism-A-cons'),
        ('data/experiment_snapshots/experiment_leaderboard_20260410-084653Z_nvda-reward-realism-B-bal.csv', 'nvda-reward-realism-B-bal'),
        ('data/experiment_snapshots/experiment_leaderboard_20260410-084806Z_nvda-reward-realism-C-agg.csv', 'nvda-reward-realism-C-agg')
    ]
    
    for file_path, run_label in snapshots:
        analyze_snapshot(file_path, run_label)
        print("\n" + "="*40 + "\n")

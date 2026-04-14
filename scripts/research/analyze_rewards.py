
import pandas as pd
import numpy as np

def analyze_reward_components(file_path, run_label):
    df = pd.read_csv(file_path)
    run_df = df[df['run_label'] == run_label].copy()
    
    if run_df.empty:
        print(f"No data found for {run_label}")
        return

    # Reward component columns (Validation)
    reward_cols = [
        'val_reward_portfolio_return_mean', 
        'val_reward_direction_mean', 
        'val_reward_hold_penalty_mean', 
        'val_reward_action_bonus_mean', 
        'val_reward_turnover_penalty_mean', 
        'val_reward_drawdown_penalty_mean'
    ]
    
    # Existing PnL/Alpha metrics
    pnl_metrics = ['val_cumulative_return', 'test_cumulative_return', 'test_alpha_vs_qqq', 'test_trade_count']
    
    # Convert to numeric
    for col in reward_cols + pnl_metrics:
        run_df[col] = pd.to_numeric(run_df[col], errors='coerce')

    print(f"--- Reward Component Analysis: {run_label} ---")
    summary = run_df[reward_cols].mean()
    total_abs = summary.abs().sum()
    
    for col, val in summary.items():
        pct = (abs(val) / total_abs * 100) if total_abs != 0 else 0
        print(f"{col:35}: {val:10.6f} ({pct:5.1f}% of abs total)")

    print("\n--- Correlation: Reward Components vs Test Alpha ---")
    # Only calculate correlation if test_alpha_vs_qqq is not constant
    if run_df['test_alpha_vs_qqq'].nunique() > 1:
        corrs = run_df[reward_cols].corrwith(run_df['test_alpha_vs_qqq'])
        print(corrs.sort_values(ascending=False))
    else:
        print("Insufficient variance in Test Alpha for correlation analysis.")

    print("\n--- Cost Analysis ---")
    ignore_cost = run_df['reward_ignore_transaction_cost'].iloc[0]
    tc_rate = run_df['transaction_cost_rate'].iloc[0]
    avg_trades = run_df['test_trade_count'].mean()
    print(f"Ignore TC in Reward: {ignore_cost}")
    print(f"Transaction Cost Rate: {tc_rate}")
    print(f"Avg Test Trades: {avg_trades:.1f}")
    
    est_cost_drag = avg_trades * tc_rate
    print(f"Estimated Cost Drag (test): {est_cost_drag:.4f}")

if __name__ == "__main__":
    snapshots = [
        ('data/experiment_snapshots/experiment_leaderboard_20260410-084544Z_nvda-reward-realism-A-cons.csv', 'nvda-reward-realism-A-cons'),
        ('data/experiment_snapshots/experiment_leaderboard_20260410-084653Z_nvda-reward-realism-B-bal.csv', 'nvda-reward-realism-B-bal'),
        ('data/experiment_snapshots/experiment_leaderboard_20260410-084806Z_nvda-reward-realism-C-agg.csv', 'nvda-reward-realism-C-agg')
    ]
    
    for file_path, run_label in snapshots:
        analyze_reward_components(file_path, run_label)
        print("\n" + "="*40 + "\n")

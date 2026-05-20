import pandas as pd
from pathlib import Path

# Paths
leaderboard_path = Path("/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_leaderboard.csv")
history_path = Path("/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_leaderboard_history.csv")

print("Checking leaderboard.csv:")
if leaderboard_path.exists():
    df = pd.read_csv(leaderboard_path)
    print(f"Total rows: {len(df)}")
    cols = [c for c in df.columns if any(x in c for x in ["run_label", "label", "experiment_label"])]
    if cols:
        print("Labels in leaderboard.csv:")
        print(df[cols[0]].value_counts())
        
        low_fric = df[df[cols[0]].str.contains("low-friction", na=False)]
        print(f"\nLow friction rows in leaderboard.csv: {len(low_fric)}")
        if not low_fric.empty:
            print(low_fric[["seed", "test_sharpe_ratio", "test_trade_rate", "test_alpha_vs_qqq"]])
    else:
        print("No run label column in leaderboard.csv")

print("\nChecking experiment_leaderboard_history.csv:")
if history_path.exists():
    df_hist = pd.read_csv(history_path)
    print(f"Total rows: {len(df_hist)}")
    cols_hist = [c for c in df_hist.columns if any(x in c for x in ["run_label", "label", "experiment_label"])]
    if cols_hist:
        print("Labels in history.csv:")
        print(df_hist[cols_hist[0]].value_counts().head(10))
        
        low_fric_hist = df_hist[df_hist[cols_hist[0]].str.contains("low-friction", na=False)]
        print(f"\nLow friction rows in history.csv: {len(low_fric_hist)}")
        if not low_fric_hist.empty:
            print(low_fric_hist[["seed", "test_sharpe_ratio", "test_trade_rate", "test_alpha_vs_qqq"]])

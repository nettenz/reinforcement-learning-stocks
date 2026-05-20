import pandas as pd
from pathlib import Path

history_path = Path("/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_leaderboard_history.csv")
if history_path.exists():
    df = pd.read_csv(history_path)
    mu_rows = df[df["run_label"].str.contains("mu-masked-ppo-v1-tuned", na=False)]
    if not mu_rows.empty:
        # print non-empty columns for the first row
        first_row = mu_rows.iloc[0]
        for col in df.columns:
            val = first_row[col]
            if pd.notna(val):
                print(f"{col}: {val}")

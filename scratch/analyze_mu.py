import pandas as pd
from pathlib import Path

history_path = Path("/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_leaderboard_history.csv")
if history_path.exists():
    df = pd.read_csv(history_path)
    mu_rows = df[df["run_label"].str.contains("mu-masked-ppo-v1-tuned", na=False)]
    print(f"Total MU rows: {len(mu_rows)}")
    if not mu_rows.empty:
        cols_to_print = ["seed", "test_sharpe_ratio", "test_trade_rate", "min_hold_bars", "use_cooldown_obs"]
        cols_to_print = [c for c in cols_to_print if c in df.columns]
        print(mu_rows[cols_to_print].drop_duplicates())

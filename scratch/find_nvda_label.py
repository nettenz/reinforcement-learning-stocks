import pandas as pd
from pathlib import Path

data_dir = Path("/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data")
print("Searching for nvda-ppo-minhold1-extended across all CSVs:")
for csv_file in data_dir.glob("*.csv"):
    try:
        df = pd.read_csv(csv_file)
        cols = [c for c in df.columns if any(x in c for x in ["run_label", "label", "experiment_label"])]
        if cols:
            matches = df[df[cols[0]].str.contains("nvda-ppo-minhold1-extended", na=False)]
            if not matches.empty:
                print(f"Found {len(matches)} rows in {csv_file.name}")
    except Exception as e:
        pass

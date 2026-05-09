import json
import argparse
from pathlib import Path
import sys
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ensemble import SparseEnsemble

def main():
    parser = argparse.ArgumentParser(description="Generate or update ensemble configuration.")
    parser.add_argument("--leaderboard", type=str, help="Path to leaderboard CSV for a specific ticker.")
    parser.add_argument("--ticker", type=str, help="Ticker to update (e.g., MU). Required if --leaderboard is provided.")
    parser.add_argument("--label", type=str, help="Optional run_label filter for the leaderboard.")
    parser.add_argument("--top-n", type=int, default=3, help="Number of top seeds to include in the ensemble (default: 3).")
    args = parser.parse_args()

    data_dir = ROOT_DIR / "data"
    staging_dir = ROOT_DIR / "staging" / "models"
    staging_dir.mkdir(parents=True, exist_ok=True)
    config_out = staging_dir / "ensemble_config.json"

    # Load existing config if it exists
    config = {}
    if config_out.exists():
        with open(config_out, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Failed to decode {config_out}. Starting fresh.")

    # If --leaderboard and --ticker are provided, process just that one
    if args.leaderboard and args.ticker:
        tickers_to_process = {args.ticker.lower(): (args.leaderboard, args.label)}
    elif args.leaderboard or args.ticker:
        print("Error: Both --leaderboard and --ticker must be provided together.")
        sys.exit(1)
    else:
        # Default behavior: process the foundation tickers
        tickers_to_process = {
            "nvda": ("exp_1_nvda_10seed_foundation_leaderboard.csv", None),
            "aapl": ("exp_2_aapl_10seed_foundation_leaderboard.csv", None),
            "amd": ("exp_3_amd_10seed_foundation_leaderboard.csv", None)
        }

    for ticker, (lb_file, label_filter) in tickers_to_process.items():
        lb_file_path = Path(lb_file)
        if lb_file_path.exists():
            leaderboard_path = lb_file_path
        elif (data_dir / lb_file).exists():
            leaderboard_path = data_dir / lb_file
        else:
            print(f"Warning: {lb_file} not found locally or in {data_dir}. Skipping {ticker}.")
            continue
            
        print(f"Processing {ticker}...")
        ensemble = SparseEnsemble(str(leaderboard_path))
        
        # If we have a label filter, we should apply it before filtering active seeds 
        # to get accurate counts for that specific experiment
        if label_filter:
            initial_len = len(ensemble.active_seeds_df)
            # Find the label column
            label_col = next((c for c in ensemble.active_seeds_df.columns if c in ["run_label", "label"]), None)
            if label_col:
                ensemble.active_seeds_df = ensemble.active_seeds_df[ensemble.active_seeds_df[label_col] == label_filter]
                print(f"  Filtered by label '{label_filter}': {initial_len} -> {len(ensemble.active_seeds_df)} rows.")
            else:
                print(f"  Warning: No run_label column found. Skipping label filter.")

        dropped = ensemble.filter_active_seeds(min_test_trades=20)
        print(f"  Dropped {dropped} collapsed seeds.")
        
        active_seeds_count = len(ensemble.active_seeds_df)
        if active_seeds_count == 0:
            print(f"  Error: No active seeds found for {ticker}. Skipping.")
            continue

        # Load top N models
        top_n = min(args.top_n, active_seeds_count)
        ensemble.load_top_n_models(n=top_n, run_label_filter=label_filter)
        
        metrics = ensemble.aggregate_metrics()
        top_3_sharpe = metrics.get("ensemble_mean_test_sharpe", 0.0)
        top_3_gap = metrics.get("ensemble_mean_val_test_gap", 1.0)
        
        active_seed_list = [int(info["seed"]) for info in ensemble.top_models_info]
        
        # Production readiness rules (loosened for pilot tickers if needed, but keeping original logic)
        # Note: top_3_gap check might be tight for MU
        if active_seeds_count >= 2 and top_3_sharpe >= 0.20 and top_3_gap <= 0.05:
            ready = True
            notes = "production ready"
        elif active_seeds_count >= 2 or (0.15 <= top_3_sharpe < 0.20):
            ready = "monitor"
            notes = "borderline ensemble or marginal alpha"
        else:
            ready = False
            notes = "Sharpe below threshold or insufficient active seeds"
            
        config[ticker] = {
            "active_seeds": active_seed_list,
            "ensemble_method": "voting",
            "top_3_mean_sharpe": round(top_3_sharpe, 3),
            "top_3_mean_val_test_gap": round(top_3_gap, 3),
            "production_ready": ready,
            "notes": f"{active_seeds_count} active seeds. {notes}",
            "run_label": label_filter if label_filter else "N/A",
            "leaderboard_csv": str(leaderboard_path.relative_to(ROOT_DIR)) if leaderboard_path.is_relative_to(ROOT_DIR) else str(leaderboard_path)
        }
        
    with open(config_out, "w") as f:
        json.dump(config, f, indent=2)
        
    print(f"\nSaved master config to {config_out}")

if __name__ == "__main__":
    main()

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ensemble import SparseEnsemble

def main():
    tickers = {
        "nvda": "exp_1_nvda_10seed_foundation_leaderboard.csv",
        "aapl": "exp_2_aapl_10seed_foundation_leaderboard.csv",
        "amd": "exp_3_amd_10seed_foundation_leaderboard.csv"
    }
    
    data_dir = ROOT_DIR / "data"
    staging_dir = ROOT_DIR / "staging" / "models"
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    config = {}
    
    for ticker, filename in tickers.items():
        leaderboard_path = data_dir / filename
        if not leaderboard_path.exists():
            print(f"Warning: {leaderboard_path} not found. Skipping {ticker}.")
            continue
            
        print(f"Processing {ticker}...")
        ensemble = SparseEnsemble(str(leaderboard_path))
        dropped = ensemble.filter_active_seeds(min_test_trades=20)
        print(f"  Dropped {dropped} collapsed seeds.")
        
        active_seeds_count = len(ensemble.active_seeds_df)
        
        # Determine top 3
        top_n = min(3, active_seeds_count)
        ensemble.load_top_n_models(n=top_n)
        
        metrics = ensemble.aggregate_metrics()
        top_3_sharpe = metrics.get("ensemble_mean_test_sharpe", 0.0)
        top_3_gap = metrics.get("ensemble_mean_val_test_gap", 1.0)
        
        active_seed_list = [int(info["seed"]) for info in ensemble.top_models_info]
        
        # Production readiness rules
        if active_seeds_count >= 2 and top_3_sharpe >= 0.20 and top_3_gap <= 0.05:
            ready = True
            notes = "production ready"
        elif active_seeds_count == 2 or (0.15 <= top_3_sharpe < 0.20):
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
            "notes": f"{active_seeds_count}/10 active. {notes}"
        }
        
    config_out = staging_dir / "ensemble_config.json"
    with open(config_out, "w") as f:
        json.dump(config, f, indent=2)
        
    print(f"\nSaved master config to {config_out}")

if __name__ == "__main__":
    main()

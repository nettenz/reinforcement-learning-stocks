import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from stable_baselines3 import SAC
import time

class SparseEnsemble:
    """
    Multi-seed ensemble for Fork B Option 2 policies.
    Loads models based on a leaderboard CSV to automatically filter by trades and rank by Sharpe.
    """
    
    def __init__(self, leaderboard_csv_path: str, ranking_metric: str = "test_sharpe_ratio"):
        self.leaderboard_path = Path(leaderboard_csv_path)
        self.ranking_metric = ranking_metric
        self.leaderboard = pd.read_csv(self.leaderboard_path)
        
        # Verify required columns exist
        required_cols = ["model_path", "test_trade_count", ranking_metric]
        for col in required_cols:
            if col not in self.leaderboard.columns:
                raise ValueError(f"Leaderboard CSV missing required column: {col}")
                
        self.active_seeds_df = self.leaderboard.copy()
        self.models: Dict[str, SAC] = {}
        self.top_models_info = []

    def filter_active_seeds(self, min_test_trades: int = 20):
        """Remove collapsed seeds (test_trades < min_test_trades) from ensemble considerations."""
        initial_count = len(self.active_seeds_df)
        self.active_seeds_df = self.active_seeds_df[self.active_seeds_df["test_trade_count"] >= min_test_trades]
        return initial_count - len(self.active_seeds_df)

    def rank_by_metric(self, metric: Optional[str] = None) -> List[Tuple[int, float]]:
        """Return seeds ranked by metric in descending order."""
        rank_col = metric if metric else self.ranking_metric
        ranked = self.active_seeds_df.sort_values(rank_col, ascending=False)
        return list(zip(ranked["seed"], ranked[rank_col]))
        
    def load_top_n_models(self, n: int = 3):
        """Loads the top N models into memory based on the ranking metric."""
        ranked = self.active_seeds_df.sort_values(self.ranking_metric, ascending=False)
        top_n = ranked.head(n)
        
        self.models = {}
        self.top_models_info = []
        
        for _, row in top_n.iterrows():
            model_path = Path(row["model_path"])
            seed = int(row["seed"])
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            # Load the SAC model
            model = SAC.load(model_path)
            self.models[seed] = model
            self.top_models_info.append(row)
            
        return len(self.models)

    def ensemble_predict(self, observation: np.ndarray, method: str = "voting") -> Tuple[int, float]:
        """
        Args:
            observation: Current market state
            method: "voting" (majority) | "weighted" (by Sharpe)
        Returns:
            action: 0 (Hold), 1 (Buy)
            confidence: 0.33 to 1.0 (fraction of ensemble agreeing or weighted probability)
        """
        if not self.models:
            raise ValueError("No models loaded. Call load_top_n_models() first.")
            
        votes = []
        weights = []
        
        for info in self.top_models_info:
            seed = int(info["seed"])
            model = self.models[seed]
            
            # Predict (deterministic=True is standard for evaluation)
            action, _ = model.predict(observation, deterministic=True)
            # Ensure action is scalar int (e.g. 0 or 1)
            action_val = int(action.item() if isinstance(action, np.ndarray) else action)
            votes.append(action_val)
            
            # For weighted voting
            weights.append(float(info[self.ranking_metric]))
            
        if method == "voting":
            # Majority vote
            vote_counts = {0: 0, 1: 0}
            for v in votes:
                vote_counts[v] += 1
                
            winning_action = 1 if vote_counts[1] > vote_counts[0] else 0
            confidence = vote_counts[winning_action] / len(votes)
            return winning_action, confidence
            
        elif method == "weighted":
            # Weight votes by their Sharpe ratio (normalize weights to sum to 1)
            # Only use positive weights (shift if necessary)
            min_weight = min(weights)
            if min_weight < 0:
                shifted_weights = [w - min_weight + 0.1 for w in weights]
            else:
                shifted_weights = weights
                
            total_weight = sum(shifted_weights)
            norm_weights = [w / total_weight for w in shifted_weights]
            
            score_1 = sum(w for v, w in zip(votes, norm_weights) if v == 1)
            score_0 = sum(w for v, w in zip(votes, norm_weights) if v == 0)
            
            winning_action = 1 if score_1 > score_0 else 0
            confidence = max(score_1, score_0)
            return winning_action, confidence
            
        else:
            raise ValueError(f"Unknown ensemble method: {method}")

    def aggregate_metrics(self) -> Dict[str, float]:
        """Return ensemble-level metrics averaged over the loaded top-N seeds."""
        if not self.top_models_info:
            return {}
            
        df = pd.DataFrame(self.top_models_info)
        
        metrics = {
            "ensemble_mean_test_sharpe": float(df["test_sharpe_ratio"].mean()) if "test_sharpe_ratio" in df else 0.0,
            "ensemble_mean_test_return": float(df["test_cumulative_signal_return"].mean()) if "test_cumulative_signal_return" in df else 0.0,
            "ensemble_mean_test_accuracy": float(df["test_actionable_accuracy"].mean()) if "test_actionable_accuracy" in df else 0.0,
        }
        
        if "val_actionable_accuracy" in df and "test_actionable_accuracy" in df:
            metrics["ensemble_mean_val_test_gap"] = float((df["val_actionable_accuracy"] - df["test_actionable_accuracy"]).abs().mean())
            
        return metrics

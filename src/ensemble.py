import pandas as pd
import numpy as np
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple
from stable_baselines3 import SAC
import time

if TYPE_CHECKING:
    from src.exit_manager import ExitManager

class SparseEnsemble:
    """
    Multi-seed ensemble for Fork B Option 2 policies.
    Loads models based on a leaderboard CSV to automatically filter by trades and rank by Sharpe.
    """

    def __init__(
        self,
        leaderboard_csv_path: str,
        ranking_metric: str = "test_sharpe_ratio",
        exit_manager: Optional["ExitManager"] = None,
    ):
        self.leaderboard_path = Path(leaderboard_csv_path)
        self.ranking_metric = ranking_metric
        self.leaderboard = pd.read_csv(self.leaderboard_path)
        self.exit_manager = exit_manager

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
        
    def load_top_n_models(self, n: int = 3, seed_filter=None, run_label_filter=None):
        """Loads the top N models into memory based on the ranking metric."""
        df = self.active_seeds_df
        if seed_filter is not None:
            df = df[df['seed'].isin(seed_filter)]
        if run_label_filter is not None:
            df = df[df['run_label'] == run_label_filter]
        ranked = df.sort_values(self.ranking_metric, ascending=False)
        ranked = ranked.drop_duplicates(subset=["seed"], keep="first")
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

    def ensemble_predict(self, observation: np.ndarray, method: str = "mean") -> Tuple[int, float]:
        """
        Args:
            observation: Current market state (will be padded/trimmed per model)
            method: "mean" (continuous avg, default) | "voting" (majority) | "weighted" (by Sharpe)
        Returns:
            action: 0 (Hold), 1 (Buy)
            confidence: 0.33 to 1.0 (fraction of ensemble agreeing or weighted probability)
        
        Note: Default is "mean" to avoid tie fragility in 2-seed ensembles.
        """
        if not self.models:
            raise ValueError("No models loaded. Call load_top_n_models() first.")

        # Make inference deterministic by seeding common RNGs here. This
        # stabilizes `model.predict(..., deterministic=True)` across runs
        # and avoids ensemble tie flapping when using small ensembles.
        try:
            import random as _random
            import numpy as _np
            _random.seed(42)
            _np.random.seed(42)
            import torch as _torch
            _torch.manual_seed(42)
            if _torch.cuda.is_available():
                _torch.cuda.manual_seed_all(42)
        except Exception:
            # Best-effort; don't fail inference if seeding isn't available
            pass
            
        votes = []
        weights = []
        
        for info in self.top_models_info:
            seed = int(info["seed"])
            model = self.models[seed]
            
            # Pad or trim observation to match this model's expected shape
            model_obs_shape = model.observation_space.shape[0]
            if observation.shape[0] < model_obs_shape:
                # Pad with zeros
                padded_obs = np.concatenate([observation, np.zeros(model_obs_shape - observation.shape[0], dtype=np.float32)])
            elif observation.shape[0] > model_obs_shape:
                # Trim
                padded_obs = observation[:model_obs_shape]
            else:
                padded_obs = observation
            
            # Predict (deterministic=True is standard for evaluation)
            action, _ = model.predict(padded_obs, deterministic=True)
            # SAC outputs a continuous value in (-1, 1). 
            # Convert to binary action: 1 if positive (indicates long), 0 if negative/hold
            raw = action.item() if isinstance(action, np.ndarray) else float(action)
            action_val = 1 if raw > 0.0 else 0  # Back to 0.0, let majority vote decide
            votes.append(action_val)
            
            # For weighted voting
            weights.append(float(info[self.ranking_metric]))
            
        if method == "voting":
            # Majority vote: require 3+ out of 5 models to agree (>50%)
            vote_counts = {0: 0, 1: 0}
            for v in votes:
                vote_counts[v] += 1
            
            # Only signal if we have >50% agreement; otherwise hold (0)
            winning_action = 1 if vote_counts[1] > vote_counts[0] else 0
            confidence = vote_counts[winning_action] / len(votes)
            return winning_action, confidence
            
        elif method == "mean":
            # Average continuous model outputs and threshold the mean.
            # This avoids tie fragility in small ensembles (e.g., 2 seeds).
            mean_raw = float(np.mean(votes))  # votes here are the binary thresholded outputs
            # Instead, collect raw continuous outputs
            raws = []
            for info in self.top_models_info:
                seed = int(info["seed"])
                model = self.models[seed]
                
                model_obs_shape = model.observation_space.shape[0]
                if observation.shape[0] < model_obs_shape:
                    padded_obs = np.concatenate([observation, np.zeros(model_obs_shape - observation.shape[0], dtype=np.float32)])
                elif observation.shape[0] > model_obs_shape:
                    padded_obs = observation[:model_obs_shape]
                else:
                    padded_obs = observation
                
                action, _ = model.predict(padded_obs, deterministic=True)
                raw = action.item() if isinstance(action, np.ndarray) else float(action)
                raws.append(raw)
            
            mean_raw = float(np.mean(raws))
            winning_action = 1 if mean_raw > 0.0 else 0
            confidence = float(np.mean([1.0 if r > 0.0 else 0.0 for r in raws]))
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

    def predict_with_exit(
        self,
        obs: np.ndarray,
        position_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """
        Run ensemble prediction and apply ExitManager override if set.

        Args:
            obs: raw observation vector (padded/trimmed per model internally).
            position_state: dict with keys shares_held, entry_price, current_price,
                unrealized_pnl_pct, peak_pnl_pct, bars_held.

        Returns dict with:
            action (int): final action — 0=exit/hold, 1=buy.
            raw_action (int): action before exit override.
            confidence (float): ensemble vote_share.
            exit_fired (bool): whether ExitManager triggered.
            exit_rule (str): name of triggered rule, or ''.
        """
        raw_action, confidence = self.ensemble_predict(obs, method="mean")
        action = raw_action
        exit_fired = False
        exit_rule = ""

        shares_held = float(position_state.get("shares_held", 0.0))
        if shares_held > 0 and self.exit_manager is not None:
            fired, triggered_rule = self.exit_manager.should_exit(position_state, confidence)
            if fired:
                action = 0
                exit_fired = True
                exit_rule = triggered_rule

        return {
            "action": action,
            "raw_action": raw_action,
            "confidence": confidence,
            "exit_fired": exit_fired,
            "exit_rule": exit_rule,
        }

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

import json
import warnings
import numpy as np
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.ensemble import SparseEnsemble
from src.exit_manager import ExitManager


class EnsembleAgent:
    """
    Stateless live inference agent for stationary-feature RL environment.

    Obs vector: [market_features | news_features | account_state]
    No rolling window, no normalization — features are pre-stationary
    (LogReturn, RelVWAP, MACD_Signal_Rel, etc.).
    """

    def __init__(
        self,
        ensemble: SparseEnsemble,
        config_path: str,
        ticker: str,
        exit_manager: Optional[ExitManager] = None,
    ):
        """
        Args:
            ensemble: SparseEnsemble with models already loaded via load_top_n_models()
            config_path: path to ensemble_config.json
            ticker: ticker symbol (case-insensitive)
        """
        self.ensemble = ensemble
        self.ticker = ticker.lower()
        self.exit_manager = exit_manager

        with open(config_path) as f:
            config = json.load(f)

        if self.ticker not in config:
            raise ValueError(
                f"Ticker '{self.ticker}' not in config. Available: {list(config.keys())}"
            )

        ticker_cfg = config[self.ticker]
        production_ready = ticker_cfg.get("production_ready", False)

        if production_ready is False:
            warnings.warn(
                f"Ticker '{self.ticker}' is marked production_ready=false in ensemble_config.json. "
                "Proceeding — review config before live deployment.",
                stacklevel=2,
            )
        elif production_ready == "monitor":
            warnings.warn(
                f"Ticker '{self.ticker}' is marked production_ready='monitor'. "
                "Marginal alpha — monitor closely.",
                stacklevel=2,
            )

        self.active_seeds = ticker_cfg.get("active_seeds", [])
        self.ensemble_method = ticker_cfg.get("ensemble_method", "voting")

        if not ensemble.models:
            raise ValueError(
                "Ensemble has no loaded models. "
                "Call ensemble.load_top_n_models() before creating EnsembleAgent."
            )

        # Derive expected obs shape from training — avoids hard-coding
        first_model = next(iter(ensemble.models.values()))
        self.expected_obs_shape: Tuple[int, ...] = first_model.observation_space.shape

        self._reset_session()

    def reset(self) -> None:
        """Clear session tracking counters for a new inference session."""
        self._reset_session()
        if self.exit_manager is not None:
            self.exit_manager.reset()

    def _reset_session(self) -> None:
        self._total_steps = 0
        self._actions_taken = 0
        self._confidence_sum = 0.0
        self._majority_steps = 0   # confidence > 0.5  (>= 2/3 seeds agreeing)
        self._unanimous_steps = 0  # confidence >= 1.0 (all seeds agreeing)

    def step(
        self,
        market_features: np.ndarray,
        news_features: np.ndarray,
        account_state: np.ndarray,
    ) -> Tuple[int, float, Dict[str, Any]]:
        """
        Args:
            market_features: stationary market features for this bar
                             (LogReturn, RelVWAP, MACD_Signal_Rel, etc. — must match training)
            news_features: news sentiment features for this bar
                           (NewsCount, SentimentMean, ... — pass empty array if not used)
            account_state: portfolio state matching training obs
                           [balance, shares_held] or
                           [balance, shares_held, current_weight, unrealized_pnl, time_in_position]

        Returns:
            action: 0 (Hold) or 1 (Buy)
            confidence: fraction of seeds agreeing — 0.33 / 0.67 / 1.0 for 3-seed ensemble
            debug_info: dict with obs_shape, action, agreement, ticker, step
        """
        obs = np.concatenate([
            np.asarray(market_features, dtype=np.float32),
            np.asarray(news_features, dtype=np.float32),
            np.asarray(account_state, dtype=np.float32),
        ])

        if obs.shape != self.expected_obs_shape:
            raise AssertionError(
                f"Obs shape mismatch: got {obs.shape}, expected {self.expected_obs_shape}. "
                "Live features must be computed identically to training "
                "(market_features + news_features + account_state)."
            )

        model_action, confidence = self.ensemble.ensemble_predict(obs, method=self.ensemble_method)
        action = model_action

        state = np.asarray(account_state, dtype=np.float32).reshape(-1)
        shares_held = float(state[1]) if state.size > 1 else 0.0
        position_state = {
            "in_position": abs(shares_held) > 1e-9,
            "unrealized_pnl": float(state[3]) if state.size > 3 else 0.0,
            "time_in_position": int(max(state[4], 0.0)) if state.size > 4 else 0,
        }

        exit_fired = False
        if self.exit_manager is not None:
            should_exit = self.exit_manager.should_exit(position_state, confidence)
            if position_state["in_position"] and should_exit:
                action = 0
                exit_fired = True

        self._total_steps += 1
        if action == 1:
            self._actions_taken += 1
        self._confidence_sum += confidence
        if confidence > 0.5:
            self._majority_steps += 1
        if confidence >= 1.0 - 1e-9:
            self._unanimous_steps += 1

        debug_info: Dict[str, Any] = {
            "obs_shape": obs.shape,
            "action": action,
            "agreement": confidence,
            "ticker": self.ticker,
            "step": self._total_steps,
            "exit_fired": exit_fired,
            "exit_rule": self.exit_manager.rule if exit_fired and self.exit_manager is not None else None,
            "model_action": model_action,
        }

        return action, confidence, debug_info

    def get_session_metrics(self) -> Dict[str, Any]:
        """Return aggregate metrics over the current inference session."""
        if self._total_steps == 0:
            return {
                "total_steps": 0,
                "actions_taken": 0,
                "avg_confidence": 0.0,
                "agreement_rate": 0.0,
            }
        return {
            "total_steps":    self._total_steps,
            "actions_taken":  self._actions_taken,
            "avg_confidence": round(self._confidence_sum / self._total_steps, 4),
            "agreement_rate": round(self._majority_steps / self._total_steps, 4),
            "high_conf_rate": round(self._unanimous_steps / self._total_steps, 4),
        }

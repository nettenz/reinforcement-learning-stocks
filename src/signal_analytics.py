from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from stable_baselines3 import SAC
from stable_baselines3 import PPO

from src.trading_env import TradingEnv


ACTION_LABELS = {0: "Hold", 1: "Buy", 2: "Sell"}
MARKET_FEATURE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
STATIONARY_FEATURE_COLUMNS = [
    "LogReturn",
    "VolLogDiff",
    "RelRange",
    "RelOpen",
    "RelMACD",
    "RSI_Centered",
    "RelATR",
    "BB_Width",
    "BB_Upper_Dist",
    "BB_Lower_Dist",
    "SMA_Trend",
    "RelVWAP",
    "MACD_Signal_Rel",
    "MACD_Hist_Rel",
]
NEWS_FEATURE_COLUMNS = [
    "NewsCount",
    "SentimentMean",
    "SentimentStd",
    "SentimentMin",
    "SentimentMax",
    "SentimentConfidenceMean",
    "SentimentGeminiShare",
    "SentimentOllamaShare",
]

# Account state is always [balance, shares_held] = 2
ACCOUNT_STATE_DIM = 2
# Position memory is [current_weight, unrealized_pnl, time_in_position] = 3 (when enabled)
POSITION_MEMORY_DIM = 3


@dataclass(frozen=True)
class MetricsSummary:
    overall_accuracy: float
    actionable_accuracy: float
    actionable_support: int
    buy_precision: float
    buy_recall: float
    sell_precision: float
    sell_recall: float
    trade_count: int
    trade_rate: float
    trade_win_rate: float
    mean_trade_edge: float
    cumulative_signal_return: float


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator / denominator)


def resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if path.exists():
        return path
    zip_path = path.with_suffix(".zip")
    if zip_path.exists():
        return zip_path
    raise FileNotFoundError(f"Model not found at '{path}' or '{zip_path}'.")


def _load_model(model_path: str | Path):
    """Auto-detect and load either SAC or PPO model."""
    resolved = resolve_model_path(model_path).as_posix()
    try:
        return SAC.load(resolved), "sac"
    except Exception:
        return PPO.load(resolved), "ppo"


def _expected_observation_dim(model) -> int:
    shape = getattr(model.observation_space, "shape", None)
    if not shape or len(shape) != 1:
        raise ValueError(f"Unsupported model observation space shape: {shape}")
    return int(shape[0])


def _market_feature_candidates(df: pd.DataFrame) -> list[tuple[str, list[str]]]:
    candidates: list[tuple[str, list[str]]] = []

    if all(col in df.columns for col in MARKET_FEATURE_COLUMNS):
        candidates.append(("ohlcv", list(MARKET_FEATURE_COLUMNS)))

    stationary_available = [col for col in STATIONARY_FEATURE_COLUMNS if col in df.columns]
    if stationary_available:
        candidates.append(("stationary", stationary_available))

    return candidates


def _align_features_to_model(df: pd.DataFrame, expected_obs_dim: int) -> tuple[pd.DataFrame, bool, list[str]]:
    """
    Align the DataFrame columns to match what the model expects.
    
    Returns (aligned_df, include_position_in_observation, market_feature_columns).
    
    Observation layout:
        [market_features] + [news_features] + [balance, shares_held] + [weight, pnl, time]
         (5 OHLCV or 6 stationary)  (0-5)          (2)                    (0 or 3)
    """
    market_candidates = _market_feature_candidates(df)
    if not market_candidates:
        raise ValueError(
            "Data does not contain any supported market feature schema. "
            "Expected either OHLCV columns or stationary feature columns."
        )

    available_news = [col for col in NEWS_FEATURE_COLUMNS if col in df.columns]

    # Try each known market schema in priority order (OHLCV first for backwards compatibility).
    chosen_market: list[str] | None = None
    include_position: bool | None = None
    required_news_count: int | None = None

    for _, candidate_market in market_candidates:
        n_market = len(candidate_market)
        remaining_with_pos = expected_obs_dim - n_market - ACCOUNT_STATE_DIM - POSITION_MEMORY_DIM
        remaining_without_pos = expected_obs_dim - n_market - ACCOUNT_STATE_DIM

        if 0 <= remaining_with_pos <= len(NEWS_FEATURE_COLUMNS):
            chosen_market = candidate_market
            include_position = True
            required_news_count = remaining_with_pos
            break

        if 0 <= remaining_without_pos <= len(NEWS_FEATURE_COLUMNS):
            chosen_market = candidate_market
            include_position = False
            required_news_count = remaining_without_pos
            break

    if chosen_market is None or include_position is None or required_news_count is None:
        ranges = []
        for name, candidate_market in market_candidates:
            n_market = len(candidate_market)
            min_dim = n_market + ACCOUNT_STATE_DIM
            max_dim = n_market + len(NEWS_FEATURE_COLUMNS) + ACCOUNT_STATE_DIM + POSITION_MEMORY_DIM
            ranges.append(f"{name}: {min_dim}-{max_dim} ({n_market} market features)")

        raise ValueError(
            f"Model expects observation size {expected_obs_dim}, but TradingEnv supports "
            f"{'; '.join(ranges)}. Use a compatible model or data schema."
        )
    
    selected_news = NEWS_FEATURE_COLUMNS[:required_news_count]
    
    aligned = df.copy()
    for col in selected_news:
        if col not in aligned.columns:
            aligned[col] = 0.0
    
    extra_news = [col for col in NEWS_FEATURE_COLUMNS if col not in selected_news and col in aligned.columns]
    if extra_news:
        aligned = aligned.drop(columns=extra_news)
    
    return aligned, include_position, chosen_market


def simulate_agent_signals(
    df: pd.DataFrame,
    model_path: str | Path,
    deterministic: bool = True,
) -> pd.DataFrame:
    model, algo_type = _load_model(model_path)
    expected_obs_dim = _expected_observation_dim(model)
    aligned_df, include_position, market_feature_columns = _align_features_to_model(df, expected_obs_dim=expected_obs_dim)
    env = TradingEnv(
        aligned_df,
        include_position_in_observation=include_position,
        market_feature_columns=market_feature_columns,
    )
    actual_obs_dim = int(env.observation_space.shape[0])
    if actual_obs_dim != expected_obs_dim:
        raise ValueError(
            f"Model expects observation shape ({expected_obs_dim},), but environment provides ({actual_obs_dim},)."
        )

    obs, _ = env.reset()
    rows: list[dict[str, float | int | str | pd.Timestamp]] = []

    while True:
        step_idx = env.current_step
        action, _ = model.predict(obs, deterministic=deterministic)
        current_price = float(aligned_df.loc[step_idx, env.price_column])
        date_value = aligned_df.loc[step_idx, "Date"] if "Date" in aligned_df.columns else step_idx

        obs, reward, terminated, truncated, _ = env.step(action)
        
        # Translate the raw [-1.0, 1.0] continuous weight into discrete 0/1/2 logic
        discrete_pos = env.position
        
        current_volume = float(aligned_df.loc[step_idx, "Volume"]) if "Volume" in aligned_df.columns else 0.0
        
        rows.append(
            {
                "step": step_idx,
                "date": pd.to_datetime(date_value) if "Date" in df.columns else date_value,
                "price": current_price,
                "volume": current_volume,
                "action": discrete_pos,
                "action_label": ACTION_LABELS[discrete_pos],
                "reward": float(reward),
                "net_worth": float(env.net_worth),
            }
        )

        if terminated or truncated:
            break

    result = pd.DataFrame(rows)
    # Note: future_return is ONLY for evaluation/backtesting labeling.
    # It is NEVER used in the training reward function (which now uses realized_return).
    result["next_price"] = result["price"].shift(-1)
    result["future_return"] = (result["next_price"] / result["price"]) - 1.0
    result["future_return"] = result["future_return"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return result


def enrich_with_truth_labels(
    signal_df: pd.DataFrame,
    threshold: float = 0.002,
    horizon_steps: int = 1,
) -> pd.DataFrame:
    if horizon_steps < 1:
        raise ValueError("horizon_steps must be >= 1")
    if threshold < 0:
        raise ValueError("threshold must be >= 0")

    enriched = signal_df.copy()
    future_price = enriched["price"].shift(-horizon_steps)
    horizon_return = (future_price / enriched["price"]) - 1.0
    horizon_return = horizon_return.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    enriched["horizon_return"] = horizon_return

    true_signal = np.where(
        enriched["horizon_return"] > threshold,
        1,
        np.where(enriched["horizon_return"] < -threshold, 2, 0),
    )
    enriched["true_signal"] = true_signal.astype(int)
    enriched["true_label"] = enriched["true_signal"].map(ACTION_LABELS)
    enriched["is_correct"] = enriched["action"] == enriched["true_signal"]

    trade_mask = enriched["action"].isin([1, 2])
    enriched["trade_edge"] = np.where(
        enriched["action"] == 1,
        enriched["horizon_return"],
        np.where(enriched["action"] == 2, -enriched["horizon_return"], 0.0),
    )
    enriched["trade_win"] = np.where(trade_mask, enriched["trade_edge"] > 0, False)
    return enriched


def compute_metrics(signal_df: pd.DataFrame) -> MetricsSummary:
    overall_accuracy = _safe_div(float(signal_df["is_correct"].sum()), float(len(signal_df)))

    actionable_true = signal_df["true_signal"].isin([1, 2])
    actionable_pred = signal_df["action"].isin([1, 2])
    actionable_rows = signal_df[actionable_true & actionable_pred]
    actionable_support = int(len(actionable_rows))
    actionable_accuracy = _safe_div(
        float((actionable_rows["action"] == actionable_rows["true_signal"]).sum()),
        float(actionable_support),
    )

    predicted_buy = signal_df["action"] == 1
    predicted_sell = signal_df["action"] == 2
    true_buy = signal_df["true_signal"] == 1
    true_sell = signal_df["true_signal"] == 2

    buy_tp = float((predicted_buy & true_buy).sum())
    buy_precision = _safe_div(buy_tp, float(predicted_buy.sum()))
    buy_recall = _safe_div(buy_tp, float(true_buy.sum()))

    sell_tp = float((predicted_sell & true_sell).sum())
    sell_precision = _safe_div(sell_tp, float(predicted_sell.sum()))
    sell_recall = _safe_div(sell_tp, float(true_sell.sum()))

    trades = signal_df[signal_df["action"].isin([1, 2])]
    trade_count = int(len(trades))
    trade_rate = _safe_div(float(trade_count), float(len(signal_df)))
    trade_win_rate = _safe_div(float(trades["trade_win"].sum()), float(trade_count))
    mean_trade_edge = float(trades["trade_edge"].mean()) if trade_count else 0.0

    cumulative_signal_return = float((1.0 + signal_df["trade_edge"]).cumprod().iloc[-1] - 1.0)

    return MetricsSummary(
        overall_accuracy=overall_accuracy,
        actionable_accuracy=actionable_accuracy,
        actionable_support=actionable_support,
        buy_precision=buy_precision,
        buy_recall=buy_recall,
        sell_precision=sell_precision,
        sell_recall=sell_recall,
        trade_count=trade_count,
        trade_rate=trade_rate,
        trade_win_rate=trade_win_rate,
        mean_trade_edge=mean_trade_edge,
        cumulative_signal_return=cumulative_signal_return,
    )


def confusion_matrix(signal_df: pd.DataFrame) -> pd.DataFrame:
    matrix = pd.crosstab(
        signal_df["true_label"],
        signal_df["action_label"],
        rownames=["True"],
        colnames=["Predicted"],
        dropna=False,
    )
    order = [ACTION_LABELS[0], ACTION_LABELS[1], ACTION_LABELS[2]]
    return matrix.reindex(index=order, columns=order, fill_value=0)

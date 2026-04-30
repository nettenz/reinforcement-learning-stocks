from __future__ import annotations

import argparse
from datetime import datetime, timezone
import itertools
import json
import platform
from pathlib import Path
import re
import sys
import psutil
import time
from urllib import request

import numpy as np
import pandas as pd
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import (
    get_interval_bars_per_year,
    get_tech_training_data,
    interval_slug,
    is_intraday_interval,
    normalize_interval_key,
    TICKER_PRESETS,
)
from src.signal_analytics import compute_metrics, enrich_with_truth_labels
from src.trading_env import LEADERBOARD_VERSION, TradingEnv
from src.market_data import fetch_yahoo_ohlcv


DEFAULT_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_leaderboard.csv"
DEFAULT_REWARD_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_reward_leaderboard.csv"
DEFAULT_SUMMARY_PATH = ROOT_DIR / "data" / "experiment_summary.json"
DEFAULT_SNAPSHOT_DIR = ROOT_DIR / "data" / "experiment_snapshots"

# Prefer CUDA (NVIDIA GPU) first, then MPS (Apple Silicon), then CPU fallback
if torch.cuda.is_available():
    DEFAULT_DEVICE = "cuda"  # NVIDIA GPU (e.g. RTX 5070 Ti)
elif torch.backends.mps.is_available():
    DEFAULT_DEVICE = "mps"  # Apple Silicon GPU acceleration
else:
    DEFAULT_DEVICE = "cpu"  # CPU fallback


def _parse_float_list(value: str) -> list[float]:
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _parse_int_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def _as_naive_datetime(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series)
    if getattr(values.dt, "tz", None) is not None:
        values = values.dt.tz_localize(None)
    return values


def _model_interval_suffix(interval: str) -> str:
    interval_key = normalize_interval_key(interval)
    return f"_{interval_slug(interval_key)}" if is_intraday_interval(interval_key) else ""


def _apply_experiment_preset(args: argparse.Namespace) -> argparse.Namespace:
    preset = str(getattr(args, "experiment_preset", "daily")).strip().lower()
    if preset == "intraday_5m":
        cli_args = sys.argv[1:]
        threshold_explicit = ("--threshold" in cli_args)
        horizon_explicit = ("--horizon" in cli_args)

        args.interval = "5m"
        args.include_news = False
        args.use_stationary_features = True
        args.execution_mode = "next_bar"
        args.reward_mode = "sortino"
        # Keep explicit CLI overrides; only apply preset defaults when flag not provided.
        if not threshold_explicit:
            args.threshold = 0.001
        if not horizon_explicit:
            args.horizon = 3
        args.train_ratio = 0.60
        args.val_ratio = 0.20
    return args


def _split_walk_forward(df: pd.DataFrame, train_ratio: float, val_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(df) < 30:
        raise ValueError("Dataset is too small for walk-forward split (need at least 30 rows).")

    ordered = df.sort_values("Date").reset_index(drop=True)
    n = len(ordered)
    train_end = max(int(n * train_ratio), 10)
    val_end = max(train_end + int(n * val_ratio), train_end + 5)
    val_end = min(val_end, n - 5)

    train_df = ordered.iloc[:train_end].reset_index(drop=True)
    val_df = ordered.iloc[train_end:val_end].reset_index(drop=True)
    test_df = ordered.iloc[val_end:].reset_index(drop=True)

    if len(val_df) < 5 or len(test_df) < 5:
        raise ValueError("Split produced too few rows in validation/test. Adjust ratios or provide more data.")

    return train_df, val_df, test_df


def _simulate_with_model(model, df: pd.DataFrame, env_kwargs: dict[str, float | bool]) -> pd.DataFrame:
    eval_kwargs = env_kwargs.copy()
    eval_kwargs["max_episode_steps"] = 0
    eval_kwargs["random_start"] = False
    env = TradingEnv(df, **eval_kwargs)
    obs, _ = env.reset()
    rows: list[dict[str, float | int | pd.Timestamp]] = []

    while True:
        step_idx = env.current_step
        action, _ = model.predict(obs, deterministic=True)
        price = float(df.loc[step_idx, env.price_column])
        date_value = pd.to_datetime(df.loc[step_idx, "Date"]) if "Date" in df.columns else step_idx

        obs, reward, terminated, truncated, info = env.step(action)
        discrete_pos = env.position  # Translate continuous weight to 0/1/2
        rows.append(
            {
                "step": step_idx,
                "date": date_value,
                "price": price,
                "action": discrete_pos,
                "reward": float(reward),
                "net_worth": float(env.net_worth),
                "reward_portfolio_return": float(info.get("reward_portfolio_return", 0.0)),
                "reward_direction": float(info.get("reward_direction", 0.0)),
                "reward_pnl": float(info.get("reward_pnl", 0.0)),
                "reward_hold_penalty": float(info.get("reward_hold_penalty", 0.0)),
                "reward_action_bonus": float(info.get("reward_action_bonus", 0.0)),
                "reward_drawdown_penalty": float(info.get("reward_drawdown_penalty", 0.0)),
                "reward_drawdown": float(info.get("reward_drawdown", 0.0)),
                "realized_return": float(info.get("realized_return", 0.0)),  # No look-ahead bias
            }
        )
        if terminated or truncated:
            break

    return pd.DataFrame(rows)


def _summarize_rewards(signal_df: pd.DataFrame, prefix: str) -> dict[str, float]:
    if signal_df.empty:
        return {
            f"{prefix}_reward_total_mean": 0.0,
            f"{prefix}_reward_total_sum": 0.0,
            f"{prefix}_reward_portfolio_return_mean": 0.0,
            f"{prefix}_reward_direction_mean": 0.0,
            f"{prefix}_reward_pnl_mean": 0.0,
            f"{prefix}_reward_hold_penalty_mean": 0.0,
            f"{prefix}_reward_action_bonus_mean": 0.0,
            f"{prefix}_reward_turnover_penalty_mean": 0.0,
            f"{prefix}_reward_drawdown_penalty_mean": 0.0,
            f"{prefix}_reward_drawdown_mean": 0.0,
        }

    return {
        f"{prefix}_reward_total_mean": float(signal_df["reward"].mean()),
        f"{prefix}_reward_total_sum": float(signal_df["reward"].sum()),
        f"{prefix}_reward_portfolio_return_mean": float(signal_df["reward_portfolio_return"].mean()),
        f"{prefix}_reward_direction_mean": float(signal_df["reward_direction"].mean()),
        f"{prefix}_reward_pnl_mean": float(signal_df.get("reward_pnl", pd.Series([0.0])).mean()),
        f"{prefix}_reward_hold_penalty_mean": float(signal_df["reward_hold_penalty"].mean()),
        f"{prefix}_reward_action_bonus_mean": float(signal_df.get("reward_action_bonus", pd.Series([0.0])).mean()),
        f"{prefix}_reward_turnover_penalty_mean": float(signal_df.get("reward_turnover_penalty", pd.Series([0.0])).mean()),
        f"{prefix}_reward_drawdown_penalty_mean": float(signal_df["reward_drawdown_penalty"].mean()),
        f"{prefix}_reward_drawdown_mean": float(signal_df["reward_drawdown"].mean()),
    }


def _ranking_score(metrics_obj) -> float:
    cumulative_clipped = max(min(metrics_obj.cumulative_signal_return, 1.0), -1.0)
    return (
        0.50 * metrics_obj.actionable_accuracy
        + 0.30 * metrics_obj.trade_win_rate
        + 0.20 * cumulative_clipped
    )


def _robustness_score(
    *,
    ranking_score: float,
    test_alpha_vs_qqq: float,
    val_actionable_accuracy: float,
    test_actionable_accuracy: float,
    test_return_cv_by_config: float,
) -> float:
    test_alpha_clipped = max(min(float(test_alpha_vs_qqq), 1.0), -1.0)
    val_test_gap = abs(float(val_actionable_accuracy) - float(test_actionable_accuracy))
    cv_penalty = min(float(test_return_cv_by_config), 5.0) / 5.0
    return float(ranking_score + (0.10 * test_alpha_clipped) - (0.05 * val_test_gap) - (0.05 * cv_penalty))


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def _annualized_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    clean = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    std = float(clean.std(ddof=0))
    if std <= 1e-12:
        return 0.0
    return float(np.sqrt(max(periods_per_year, 1)) * clean.mean() / std)


def _annualized_sortino(returns: pd.Series, periods_per_year: int = 252) -> float:
    clean = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    if downside_std <= 1e-12:
        return 0.0
    return float(np.sqrt(max(periods_per_year, 1)) * clean.mean() / downside_std)


def _risk_metrics_from_equity(equity: pd.Series, prefix: str, periods_per_year: int = 252) -> dict[str, float]:
    curve = pd.Series(equity).replace([np.inf, -np.inf], np.nan).dropna()
    if curve.empty:
        return {
            f"{prefix}_cumulative_return": 0.0,
            f"{prefix}_sharpe_ratio": 0.0,
            f"{prefix}_sortino_ratio": 0.0,
            f"{prefix}_max_drawdown": 0.0,
        }

    returns = curve.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    peak = curve.cummax().replace(0.0, np.nan)
    drawdown = (curve / peak) - 1.0
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0
    cumulative_return = float((curve.iloc[-1] / max(curve.iloc[0], 1e-8)) - 1.0)

    return {
        f"{prefix}_cumulative_return": cumulative_return,
        f"{prefix}_sharpe_ratio": _annualized_sharpe(returns, periods_per_year=periods_per_year),
        f"{prefix}_sortino_ratio": _annualized_sortino(returns, periods_per_year=periods_per_year),
        f"{prefix}_max_drawdown": max_drawdown,
    }


def _attach_config_stability_metrics(leaderboard: pd.DataFrame) -> pd.DataFrame:
    if leaderboard.empty:
        return leaderboard

    leaderboard = leaderboard.copy()
    if "leaderboard_version" not in leaderboard.columns:
        leaderboard["leaderboard_version"] = 1
    else:
        leaderboard["leaderboard_version"] = leaderboard["leaderboard_version"].fillna(1).astype(int)
    if "reward_pnl_scale" not in leaderboard.columns:
        leaderboard["reward_pnl_scale"] = 0.0
    else:
        leaderboard["reward_pnl_scale"] = pd.to_numeric(leaderboard["reward_pnl_scale"], errors="coerce").fillna(0.0)

    config_keys = [
        "leaderboard_version",
        "ticker",
        "interval",
        "experiment_preset",
        "timesteps",
        "learning_rate",
        "gamma",
        "ent_coef",
        "include_news",
        "use_stationary_features",
        "threshold",
        "horizon",
        "transaction_cost_rate",
        "trade_penalty",
        "execution_mode",
        "spread_bps",
        "slippage_bps",
        "max_weight_delta_per_step",
        "reward_mode",
        "rolling_reward_window",
        "reward_epsilon",
        "reward_return_scale",
        "reward_pnl_scale",
        "reward_direction_scale",
        "reward_hold_penalty_scale",
        "reward_drawdown_penalty_scale",
        "reward_action_bonus_scale",
        "reward_clip",
        "reward_ignore_transaction_cost",
    ]

    grouped = (
        leaderboard.groupby(config_keys, dropna=False)["test_cumulative_signal_return"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(
            columns={
                "mean": "test_return_mean_by_config",
                "std": "test_return_std_by_config",
                "count": "config_seed_count",
            }
        )
    )
    grouped["test_return_std_by_config"] = grouped["test_return_std_by_config"].fillna(0.0)
    denom = grouped["test_return_mean_by_config"].abs()
    grouped["test_return_cv_by_config"] = np.where(
        denom > 1e-8,
        grouped["test_return_std_by_config"] / denom,
        np.inf,
    )
    grouped["high_return_cv_risk"] = (grouped["test_return_cv_by_config"] >= 1.0).astype(int)

    merged = leaderboard.merge(grouped, on=config_keys, how="left")
    return merged


def _passes_promotion_gates(row: pd.Series, args: argparse.Namespace) -> bool:
    test_actionable = float(row.get("test_actionable_accuracy", 0.0))
    test_win_rate = float(row.get("test_trade_win_rate", 0.0))
    test_alpha = float(row.get("test_alpha_vs_qqq", float("-inf")))
    val_actionable = float(row.get("val_actionable_accuracy", 0.0))
    test_cv = float(row.get("test_return_cv_by_config", float("inf")))
    test_trade_count = int(row.get("test_trade_count", 0))
    test_actionable_support = int(row.get("test_actionable_support", 0))

    return (
        test_actionable >= float(args.promote_min_test_actionable)
        and test_win_rate >= float(args.promote_min_test_win_rate)
        and test_alpha >= float(args.promote_min_test_alpha)
        and abs(val_actionable - test_actionable) <= float(args.promote_max_val_test_gap)
        and test_cv < float(args.promote_max_test_cv)
        and test_trade_count >= int(args.promote_min_test_trade_count)
        and test_actionable_support >= int(args.promote_min_test_actionable_support)
    )


def _fetch_qqq_prices(start_date: pd.Timestamp, end_date: pd.Timestamp, interval: str = "1d") -> pd.DataFrame:
    raw = fetch_yahoo_ohlcv(
        tickers=("QQQ",),
        start=pd.to_datetime(start_date).strftime("%Y-%m-%d"),
        end=(pd.to_datetime(end_date) + pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        interval=interval,
    )
    qqq = raw[["Date", "Close"]].copy()
    qqq["Date"] = _as_naive_datetime(qqq["Date"])
    if not is_intraday_interval(interval):
        qqq["Date"] = qqq["Date"].dt.normalize()
    qqq = qqq.sort_values("Date").drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)
    return qqq


def _benchmark_equity_curve(
    period_df: pd.DataFrame,
    qqq_prices: pd.DataFrame,
    initial_balance: float = 1000.0,
    interval: str = "1d",
) -> pd.Series:
    if "Date" not in period_df.columns:
        raise ValueError("QQQ benchmark requires a Date column in the period dataframe.")

    period_dates = _as_naive_datetime(period_df["Date"])
    if not is_intraday_interval(interval):
        period_dates = period_dates.dt.normalize()
    aligned = pd.DataFrame({"Date": period_dates}).merge(qqq_prices, on="Date", how="left")
    aligned["Close"] = aligned["Close"].ffill().bfill()

    if aligned["Close"].isna().any():
        raise ValueError("Unable to align QQQ prices to experiment dates for benchmark computation.")

    first_price = max(float(aligned["Close"].iloc[0]), 1e-8)
    return float(initial_balance) * (aligned["Close"] / first_price)


def linear_schedule(initial_value: float):
    """
    Linear learning rate schedule.
    :param initial_value: Initial learning rate.
    :return: schedule that computes current learning rate depending on remaining progress
    """
    def func(progress_remaining: float) -> float:
        """
        Progress will decrease from 1 (beginning) to 0.
        :param progress_remaining:
        :return: current learning rate
        """
        return progress_remaining * initial_value
    return func


def _safe_label(label: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_")
    return sanitized[:80] if sanitized else "run"


def make_env(df, env_kwargs):
    def _init():
        return TradingEnv(df, **env_kwargs)
    return _init


def _format_duration(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


class ProgressCallback(BaseCallback):
    """Custom callback for displaying a progress bar with a spinner effect during training."""
    def __init__(self, total_timesteps: int, verbose=0):
        super().__init__(verbose)
        self.pbar = None
        self.total_timesteps = total_timesteps

    def _on_training_start(self) -> None:
        self.pbar = tqdm(total=self.total_timesteps, desc="Training", unit="step", leave=False)

    def _on_step(self) -> bool:
        if self.pbar:
            self.pbar.update(1)
        return True

    def _on_training_end(self) -> None:
        if self.pbar:
            self.pbar.close()


def write_experiment_outputs(
    leaderboard: pd.DataFrame,
    leaderboard_path: Path,
    reward_leaderboard_path: Path,
    summary_path: Path,
    snapshot_dir: Path | None = DEFAULT_SNAPSHOT_DIR,
    run_label: str | None = None,
    append_results: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    reward_leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    new_results = leaderboard.copy()
    if "leaderboard_version" not in new_results.columns:
        new_results["leaderboard_version"] = LEADERBOARD_VERSION
    else:
        new_results["leaderboard_version"] = new_results["leaderboard_version"].fillna(LEADERBOARD_VERSION).astype(int)

    # 1. Update Historical Cumulative Data (ALWAYS)
    historical_leaderboard_path = leaderboard_path.with_name(f"{leaderboard_path.stem}_history{leaderboard_path.suffix}")
    historical_reward_leaderboard_path = reward_leaderboard_path.with_name(f"{reward_leaderboard_path.stem}_history{reward_leaderboard_path.suffix}")
    
    cumulative_history = new_results.copy()
    if historical_leaderboard_path.exists():
        try:
            existing_history = pd.read_csv(historical_leaderboard_path)
            cumulative_history = pd.concat([existing_history, new_results], ignore_index=True)
        except Exception as e:
            print(f"Warning: could not read existing history: {e}")
            
    # Save the cumulative history
    cumulative_history.sort_values(["leaderboard_version", "ranking_score"], ascending=[False, False]).to_csv(historical_leaderboard_path, index=False)
    cumulative_history.sort_values("val_reward_total_mean", ascending=False).to_csv(historical_reward_leaderboard_path, index=False)

    # 2. Update Current Leaderboard (Conditional on --append)
    if append_results and leaderboard_path.exists():
        try:
            existing = pd.read_csv(leaderboard_path)
            leaderboard = pd.concat([existing, new_results], ignore_index=True)
        except Exception as e:
            print(f"Warning: could not append to existing leaderboard: {e}")
            leaderboard = new_results.copy()
    else:
        leaderboard = new_results.copy()

    leaderboard = leaderboard.sort_values(["leaderboard_version", "ranking_score"], ascending=[False, False]).reset_index(drop=True)
    comparable_leaderboard = leaderboard[leaderboard["leaderboard_version"] == LEADERBOARD_VERSION].copy()
    if comparable_leaderboard.empty:
        comparable_leaderboard = leaderboard.copy()

    comparable_leaderboard.to_csv(leaderboard_path, index=False)
    reward_leaderboard = comparable_leaderboard.sort_values("val_reward_total_mean", ascending=False).reset_index(drop=True)
    reward_leaderboard.to_csv(reward_leaderboard_path, index=False)

    timestamp = _timestamp_slug()
    summary: dict[str, object] = {
        "rows": int(len(comparable_leaderboard)),
        "generated_at_utc": timestamp,
        "leaderboard_path": str(leaderboard_path),
        "reward_leaderboard_path": str(reward_leaderboard_path),
        "leaderboard_history_path": str(historical_leaderboard_path),
        "reward_leaderboard_history_path": str(historical_reward_leaderboard_path),
        "leaderboard_version": LEADERBOARD_VERSION,
        "top3": leaderboard.head(3).to_dict(orient="records"),
    }

    if snapshot_dir is not None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{timestamp}_{_safe_label(run_label)}" if run_label else timestamp
        snapshot_leaderboard_path = snapshot_dir / f"experiment_leaderboard_{suffix}.csv"
        snapshot_reward_leaderboard_path = snapshot_dir / f"experiment_reward_leaderboard_{suffix}.csv"
        snapshot_summary_path = snapshot_dir / f"experiment_summary_{suffix}.json"

        # Snapshots now accurately reflect the state of the leaderboard after this update
        comparable_leaderboard.to_csv(snapshot_leaderboard_path, index=False)
        reward_leaderboard.to_csv(snapshot_reward_leaderboard_path, index=False)
        
        snapshot_history_leaderboard_path = snapshot_dir / f"experiment_leaderboard_history_{suffix}.csv"
        snapshot_history_reward_path = snapshot_dir / f"experiment_reward_leaderboard_history_{suffix}.csv"
        
        # Save historical snapshots too
        cumulative_history.to_csv(snapshot_history_leaderboard_path, index=False)
        cumulative_history.sort_values("val_reward_total_mean", ascending=False).to_csv(
            snapshot_history_reward_path,
            index=False,
        )
        
        snapshot_summary = {
            **summary,
            "leaderboard_path": str(snapshot_leaderboard_path),
            "reward_leaderboard_path": str(snapshot_reward_leaderboard_path),
            "leaderboard_history_path": str(snapshot_history_leaderboard_path),
            "reward_leaderboard_history_path": str(snapshot_history_reward_path),
        }
        snapshot_summary_path.write_text(json.dumps(snapshot_summary, indent=2), encoding="utf-8")
        summary["snapshot_paths"] = {
            "leaderboard": str(snapshot_leaderboard_path),
            "reward_leaderboard": str(snapshot_reward_leaderboard_path),
            "leaderboard_history": str(snapshot_history_leaderboard_path),
            "reward_leaderboard_history": str(snapshot_history_reward_path),
            "summary": str(snapshot_summary_path),
        }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return reward_leaderboard, summary


def run_experiments(args: argparse.Namespace) -> pd.DataFrame:
    interval = str(args.interval)
    bars_per_year = get_interval_bars_per_year(interval)
    seeds = _parse_int_list(args.seeds)
    learning_rates = _parse_float_list(args.learning_rates)
    gammas = _parse_float_list(args.gammas)
    ent_coefs = _parse_float_list(args.ent_coefs)
    timesteps_list = _parse_int_list(args.timesteps)

    df = get_tech_training_data(
        ticker_preset=args.ticker,
        interval=interval,
        include_news=args.include_news,
        refresh=args.refresh_data,
        news_refresh=args.refresh_news,
        use_stationary_features=args.use_stationary_features,
    )
    train_df, val_df, test_df = _split_walk_forward(df, train_ratio=args.train_ratio, val_ratio=args.val_ratio)
    qqq_prices = _fetch_qqq_prices(
        start_date=pd.to_datetime(val_df["Date"]).min(),
        end_date=pd.to_datetime(test_df["Date"]).max(),
        interval=interval,
    )
    val_benchmark_equity = _benchmark_equity_curve(val_df, qqq_prices=qqq_prices, interval=interval)
    test_benchmark_equity = _benchmark_equity_curve(test_df, qqq_prices=qqq_prices, interval=interval)
    val_benchmark_risk = _risk_metrics_from_equity(val_benchmark_equity, prefix="val_benchmark", periods_per_year=bars_per_year)
    test_benchmark_risk = _risk_metrics_from_equity(test_benchmark_equity, prefix="test_benchmark", periods_per_year=bars_per_year)

    env_kwargs: dict[str, float | bool | str | int] = {
        "transaction_cost_rate": args.transaction_cost_rate,
        "trade_penalty": args.trade_penalty,
        "execution_mode": args.execution_mode,
        "spread_bps": args.spread_bps,
        "slippage_bps": args.slippage_bps,
        "max_weight_delta_per_step": args.max_weight_delta_per_step,
        "reward_clip": args.reward_clip,
        "reward_ignore_transaction_cost": args.reward_ignore_transaction_cost,
        "reward_mode": args.reward_mode,
        "rolling_reward_window": 100,  # Default; will be overridden per-run
        "reward_epsilon": args.reward_epsilon,
        "reward_pnl_scale": args.reward_pnl_scale,
        "long_only": args.long_only,
        "binary_actions": args.binary_actions,
        "max_episode_steps": args.max_episode_steps,
        "random_start": args.random_start,
    }

    reward_return_scales = _parse_float_list(args.reward_return_scale)
    reward_pnl_scales = _parse_float_list(args.reward_pnl_scale)
    reward_direction_scales = _parse_float_list(args.reward_direction_scale)
    reward_hold_penalty_scales = _parse_float_list(args.reward_hold_penalty_scale)
    reward_drawdown_penalty_scales = _parse_float_list(args.reward_drawdown_penalty_scale)
    reward_action_bonus_scales = _parse_float_list(args.reward_action_bonus_scale)
    reward_turnover_penalty_scales = _parse_float_list(args.reward_turnover_penalty_scale)
    rolling_reward_windows = _parse_int_list(args.rolling_reward_window)

    configs = list(itertools.product(
        seeds, timesteps_list, learning_rates, gammas, ent_coefs,
        reward_return_scales, reward_pnl_scales, reward_direction_scales, reward_hold_penalty_scales,
        reward_drawdown_penalty_scales, reward_action_bonus_scales, reward_turnover_penalty_scales,
        rolling_reward_windows
    ))
    if args.max_runs > 0:
        configs = configs[: args.max_runs]

    rows: list[dict[str, float | int | str]] = []
    canonical_ticker = TICKER_PRESETS.get(args.ticker, (args.ticker.upper(),))[0]
    print(f"Running {len(configs)} experiment runs on interval={interval} (preset={args.experiment_preset})...")

    for idx, (seed, timesteps, learning_rate, gamma, ent_coef,
              ret_scale, pnl_scale, dir_scale, hold_scale, dd_scale, bonus_scale, turnover_scale, rolling_window) in enumerate(configs, start=1):
        print(
            f"[{idx}/{len(configs)}] seed={seed} timesteps={timesteps} lr={learning_rate} "
            f"gamma={gamma} ent_coef={ent_coef} dir_scale={dir_scale} mode={args.reward_mode}"
        )
        start_time = time.time()
        lr_arg = linear_schedule(learning_rate) if args.use_lr_schedule else learning_rate
        
        env_kwargs_run = env_kwargs.copy()
        env_kwargs_run.update({
            "reward_return_scale": ret_scale,
            "reward_pnl_scale": pnl_scale,
            "reward_direction_scale": dir_scale,
            "reward_hold_penalty_scale": hold_scale,
            "reward_drawdown_penalty_scale": dd_scale,
            "reward_action_bonus_scale": bonus_scale,
            "reward_turnover_penalty_scale": turnover_scale,
            "rolling_reward_window": rolling_window,
        })

        if args.n_envs > 1:
            env_train = SubprocVecEnv([make_env(train_df, env_kwargs_run) for _ in range(args.n_envs)])
        else:
            env_train = TradingEnv(train_df, **env_kwargs_run)
            
        model_ent_coef = ent_coef if ent_coef > 0.0 else "auto"
        model = SAC(
            "MlpPolicy",
            env_train,
            verbose=0,
            seed=seed,
            learning_rate=lr_arg,
            gamma=gamma,
            ent_coef=model_ent_coef,
            batch_size=args.batch_size,
            buffer_size=max(100000, timesteps),  # Prevents 1,000,000 pre-allocation in System RAM
            device=DEFAULT_DEVICE,
        )
        
        callback = ProgressCallback(total_timesteps=timesteps)
        
        model.learn(total_timesteps=timesteps, callback=callback)
        if torch.cuda.is_available():
            print(f"GPU memory allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
            print(f"GPU memory reserved: {torch.cuda.memory_reserved() / 1e9:.2f} GB")
        # --- Intelligence Synchronization: Save Model Weights ---
        timestamp = _timestamp_slug()
        run_label_slug = _safe_label(args.run_label) if args.run_label else "run"
        model_filename = f"model_{timestamp}_{run_label_slug}_seed{seed}{_model_interval_suffix(interval)}.zip"
        model_save_path = Path(args.snapshot_dir) / model_filename
        model_save_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(model_save_path)
        # -------------------------------------------------------

        if args.n_envs > 1:
            env_train.close()

        val_signals = _simulate_with_model(model, val_df, env_kwargs=env_kwargs_run)
        test_signals = _simulate_with_model(model, test_df, env_kwargs=env_kwargs_run)

        val_enriched = enrich_with_truth_labels(val_signals, threshold=args.threshold, horizon_steps=args.horizon)
        test_enriched = enrich_with_truth_labels(test_signals, threshold=args.threshold, horizon_steps=args.horizon)
        val_metrics = compute_metrics(val_enriched)
        test_metrics = compute_metrics(test_enriched)
        val_reward = _summarize_rewards(val_signals, prefix="val")
        test_reward = _summarize_rewards(test_signals, prefix="test")
        val_strategy_risk = _risk_metrics_from_equity(val_signals["net_worth"], prefix="val")
        test_strategy_risk = _risk_metrics_from_equity(test_signals["net_worth"], prefix="test")

        row: dict[str, float | int | str] = {
            "leaderboard_version": LEADERBOARD_VERSION,
            "ticker": canonical_ticker,
            "interval": interval,
            "experiment_preset": args.experiment_preset,
            "run_label": args.run_label.strip(),
            "seed": seed,
            "timesteps": timesteps,
            "learning_rate": learning_rate,
            "gamma": gamma,
            "ent_coef": ent_coef,
            "include_news": int(args.include_news),
            "use_stationary_features": int(args.use_stationary_features),
            "threshold": args.threshold,
            "horizon": args.horizon,
            "transaction_cost_rate": args.transaction_cost_rate,
            "trade_penalty": args.trade_penalty,
            "execution_mode": args.execution_mode,
            "spread_bps": args.spread_bps,
            "slippage_bps": args.slippage_bps,
            "max_weight_delta_per_step": args.max_weight_delta_per_step,
            "reward_mode": args.reward_mode,
            "rolling_reward_window": args.rolling_reward_window,
            "reward_epsilon": args.reward_epsilon,
            "reward_pnl_scale": pnl_scale,
            "reward_return_scale": ret_scale,
            "reward_direction_scale": dir_scale,
            "reward_hold_penalty_scale": hold_scale,
            "reward_drawdown_penalty_scale": dd_scale,
            "reward_action_bonus_scale": bonus_scale,
            "reward_turnover_penalty_scale": turnover_scale,
            "reward_clip": args.reward_clip,
            "reward_ignore_transaction_cost": int(args.reward_ignore_transaction_cost),
            "bars_per_year": bars_per_year,
            "val_overall_accuracy": val_metrics.overall_accuracy,
            "val_actionable_accuracy": val_metrics.actionable_accuracy,
            "val_actionable_support": val_metrics.actionable_support,
            "val_trade_count": val_metrics.trade_count,
            "val_trade_rate": val_metrics.trade_rate,
            "val_trade_win_rate": val_metrics.trade_win_rate,
            "val_cumulative_signal_return": val_metrics.cumulative_signal_return,
            "test_overall_accuracy": test_metrics.overall_accuracy,
            "test_actionable_accuracy": test_metrics.actionable_accuracy,
            "test_actionable_support": test_metrics.actionable_support,
            "test_trade_count": test_metrics.trade_count,
            "test_trade_rate": test_metrics.trade_rate,
            "test_trade_win_rate": test_metrics.trade_win_rate,
            "test_cumulative_signal_return": test_metrics.cumulative_signal_return,
            "val_alpha_vs_qqq": float(val_strategy_risk["val_cumulative_return"] - val_benchmark_risk["val_benchmark_cumulative_return"]),
            "test_alpha_vs_qqq": float(test_strategy_risk["test_cumulative_return"] - test_benchmark_risk["test_benchmark_cumulative_return"]),
            "ranking_score": _ranking_score(val_metrics),
            "run_duration_seconds": float(time.time() - start_time),
        }
        duration_str = _format_duration(row['run_duration_seconds'])
        print(f"Run {idx} completed in {duration_str}.")
        row.update(val_reward)
        row.update(test_reward)
        row.update(val_strategy_risk)
        row.update(test_strategy_risk)
        row.update(val_benchmark_risk)
        row.update(test_benchmark_risk)
        row["model_path"] = str(model_save_path)  # Track which file belongs to this run
        rows.append(row)

    leaderboard = pd.DataFrame(rows).sort_values("ranking_score", ascending=False).reset_index(drop=True)
    leaderboard = _attach_config_stability_metrics(leaderboard)
    leaderboard["robustness_score"] = leaderboard.apply(
        lambda row: _robustness_score(
            ranking_score=float(row.get("ranking_score", 0.0)),
            test_alpha_vs_qqq=float(row.get("test_alpha_vs_qqq", 0.0)),
            val_actionable_accuracy=float(row.get("val_actionable_accuracy", 0.0)),
            test_actionable_accuracy=float(row.get("test_actionable_accuracy", 0.0)),
            test_return_cv_by_config=float(row.get("test_return_cv_by_config", float("inf"))),
        ),
        axis=1,
    )
    leaderboard = leaderboard.sort_values("ranking_score", ascending=False).reset_index(drop=True)
    return leaderboard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggressive multi-seed SAC experiment runner.")
    parser.add_argument("--experiment-preset", default="daily", choices=["daily", "intraday_5m"], help="Apply a preset for the overall experiment family.")
    parser.add_argument("--ticker", default="aapl", choices=list(TICKER_PRESETS.keys()), 
                        help=f"Stock ticker preset to train on. Options: {', '.join(TICKER_PRESETS.keys())}")
    parser.add_argument("--interval", default="1d", help="Yahoo Finance candle interval, such as 1d or 5m.")
    parser.add_argument("--include-news", action="store_true", help="Train with merged sentiment features.")
    parser.add_argument("--refresh-data", action="store_true", help="Refresh OHLCV training data cache.")
    parser.add_argument("--refresh-news", action="store_true", help="Refresh news sentiment cache.")
    parser.add_argument("--seeds", default="7,13,21", help="Comma-separated seeds.")
    parser.add_argument("--timesteps", default="20000,40000", help="Comma-separated timesteps.")
    parser.add_argument("--learning-rates", default="0.0003", help="Comma-separated learning rates.")
    parser.add_argument("--gammas", default="0.99", help="Comma-separated gammas.")
    parser.add_argument("--ent-coefs", default="0.02,0.05", help="Comma-separated entropy coefficients.")
    parser.add_argument("--batch-size", type=int, default=1024, help="Batch size for VRAM allocation.")
    parser.add_argument("--threshold", type=float, default=0.002, help="Signal threshold for evaluation.")
    parser.add_argument("--horizon", type=int, default=1, help="Forward horizon steps for evaluation.")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Walk-forward train ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Walk-forward validation ratio.")
    parser.add_argument("--transaction-cost-rate", type=float, default=0.001, help="Fee rate per executed trade.")
    parser.add_argument("--trade-penalty", type=float, default=0.05, help="Flat penalty per executed trade.")
    parser.add_argument("--execution-mode", default="same_bar", choices=["same_bar", "next_bar"], help="Execution timing model.")
    parser.add_argument("--spread-bps", type=float, default=0.0, help="Half-spread is applied around mid for buys/sells (in bps).")
    parser.add_argument("--slippage-bps", type=float, default=0.0, help="Additional one-way slippage added to execution price (in bps).")
    parser.add_argument("--max-weight-delta-per-step", type=float, default=0.0, help="Maximum absolute change in target weight allowed per step.")
    parser.add_argument("--reward-return-scale", default="1.0", help="Weight for portfolio-return reward term (list).")
    parser.add_argument("--reward-pnl-scale", default="0.0", help="Additional weight for realized portfolio P&L (list).")
    parser.add_argument("--reward-direction-scale", default="0.35", help="Weight for directional-alignment reward term (list).")
    parser.add_argument("--reward-hold-penalty-scale", default="0.10", help="Penalty scale for hold during movement (list).")
    parser.add_argument("--reward-drawdown-penalty-scale", default="0.10", help="Penalty scale for drawdown term (list).")
    parser.add_argument("--reward-action-bonus-scale", default="0.02", help="Bonus for taking Buy/Sell actions (list).")
    parser.add_argument("--reward-turnover-penalty-scale", default="0.05", help="Penalty scale for absolute weight changes (list).")

    parser.add_argument("--reward-mode", default="sharpe", choices=["legacy", "sharpe", "sortino", "sparse"], help="Reward calculation mode.")
    parser.add_argument("--rolling-reward-window", default="100", help="Window size for rolling rewards (list).")
    parser.add_argument("--reward-epsilon", type=float, default=1e-6, help="Epsilon for numerical stability in rewards.")
    parser.add_argument("--max-episode-steps", type=int, default=0, help="If > 0, truncate episodes after this many steps.")
    parser.add_argument("--random-start", action="store_true", help="If set, randomize start step (requires max-episode-steps > 0).")

    parser.add_argument("--reward-clip", type=float, default=1.0, help="Reward clip bound applied symmetrically.")
    parser.add_argument(
        "--reward-ignore-transaction-cost",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude transaction costs/penalties from reward shaping while keeping execution unchanged.",
    )
    parser.add_argument("--use-stationary-features", action="store_true", help="Use log returns and normalized technical indicators.")
    parser.add_argument("--long-only", action="store_true", help="Clip actions to [0, 1] — no short positions.")
    parser.add_argument("--binary-actions", action="store_true", help="Map actions to binary long/flat (1.0 or 0.0) — removes continuous sizing.")
    parser.add_argument("--max-runs", type=int, default=0, help="Limit number of experiment runs (0 = all).")
    parser.add_argument("--leaderboard-path", default=str(DEFAULT_LEADERBOARD_PATH), help="CSV output path.")
    parser.add_argument("--reward-leaderboard-path", default=str(DEFAULT_REWARD_LEADERBOARD_PATH), help="Reward leaderboard CSV output path.")
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH), help="JSON summary output path.")
    parser.add_argument(
        "--snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory for timestamped leaderboard/reward/summary snapshots.",
    )
    parser.add_argument("--disable-snapshots", action="store_true", help="Disable timestamped snapshot output files.")
    parser.add_argument("--append", action="store_true", help="Append results to existing leaderboard.")
    parser.add_argument("--run-label", default="", help="Optional suffix label appended to snapshot filenames.")
    parser.add_argument(
        "--compact-output",
        action="store_true",
        help="Print a compact top-run summary instead of full transposed output.",
    )
    parser.add_argument("--device", default=DEFAULT_DEVICE, help="SAC device (auto, cuda, cpu).")
    parser.add_argument("--use-lr-schedule", action="store_true", help="Use linear learning rate decay.")
    parser.add_argument("--n-envs", type=int, default=8, help="Number of parallel environments for vectorized training.")
    parser.add_argument(
        "--promote-require-gates",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only promote champion model if promotion gates are satisfied.",
    )
    parser.add_argument("--promote-min-test-actionable", type=float, default=0.53, help="Promotion gate: minimum test actionable accuracy.")
    parser.add_argument("--promote-min-test-win-rate", type=float, default=0.52, help="Promotion gate: minimum test trade win rate.")
    parser.add_argument("--promote-min-test-alpha", type=float, default=0.00, help="Promotion gate: minimum test alpha vs benchmark.")
    parser.add_argument("--promote-max-val-test-gap", type=float, default=0.05, help="Promotion gate: maximum |val actionable - test actionable|.")
    parser.add_argument("--promote-max-test-cv", type=float, default=1.0, help="Promotion gate: maximum config-level test return CV.")
    parser.add_argument("--promote-min-test-trade-count", type=int, default=0, help="Optional promotion gate: minimum number of test trades (0 disables).")
    parser.add_argument("--promote-min-test-actionable-support", type=int, default=0, help="Optional promotion gate: minimum test actionable support (0 disables).")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args = _apply_experiment_preset(args)

    # Update global device if provided
    global DEFAULT_DEVICE
    DEFAULT_DEVICE = args.device

    leaderboard = run_experiments(args)
    leaderboard_path = Path(args.leaderboard_path)
    reward_leaderboard_path = Path(args.reward_leaderboard_path)
    summary_path = Path(args.summary_path)
    snapshot_dir = None if args.disable_snapshots else Path(args.snapshot_dir)
    run_label = args.run_label.strip() or None
    canonical_ticker = TICKER_PRESETS.get(args.ticker, (args.ticker.upper(),))[0]
    interval = str(args.interval)
    model_suffix = _model_interval_suffix(interval)
    reward_leaderboard, summary = write_experiment_outputs(
        leaderboard=leaderboard,
        leaderboard_path=leaderboard_path,
        reward_leaderboard_path=reward_leaderboard_path,
        summary_path=summary_path,
        snapshot_dir=snapshot_dir,
        run_label=run_label,
        append_results=args.append,
    )
    top = leaderboard.head(3)

    # --- Champion Promotion ---
    if not leaderboard.empty:
        candidate_rows = leaderboard
        if args.promote_require_gates:
            mask = leaderboard.apply(lambda row: _passes_promotion_gates(row, args), axis=1)
            candidate_rows = leaderboard[mask].sort_values("ranking_score", ascending=False).reset_index(drop=True)
            print(
                "Promotion gates active: "
                f"min_test_actionable={args.promote_min_test_actionable:.3f}, "
                f"min_test_win_rate={args.promote_min_test_win_rate:.3f}, "
                f"min_test_alpha={args.promote_min_test_alpha:.3f}"
            )
        
        # Filter by ticker to ensure champion matches current experiment ticker
        candidate_tickers = candidate_rows.get("ticker", pd.Series(["" for _ in range(len(candidate_rows))]))
        ticker_matches = candidate_rows[candidate_tickers.astype(str).str.upper() == canonical_ticker]
        if not ticker_matches.empty:
            best_run = ticker_matches.iloc[0]
            best_ticker = str(best_run.get("ticker", "unknown"))
            best_model_path = Path(best_run["model_path"])
            if best_model_path.exists():
                import shutil

                # Store ticker-aware champion to prevent cross-ticker contamination
                default_model_path = ROOT_DIR / "models" / f"sac_trading_bot_{best_ticker}{model_suffix}.zip"
                default_model_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(best_model_path, default_model_path)
                print(
                    f"Champion promoted to: {default_model_path} "
                    f"(Ranking Score: {best_run['ranking_score']:.4f}, "
                    f"test_actionable={float(best_run.get('test_actionable_accuracy', 0.0)):.4f}, "
                    f"test_win_rate={float(best_run.get('test_trade_win_rate', 0.0)):.4f}, "
                    f"test_alpha={float(best_run.get('test_alpha_vs_qqq', 0.0)):.4f}, "
                    f"test_cv={float(best_run.get('test_return_cv_by_config', float('inf'))):.4f}, "
                    f"ticker={best_ticker})"
                )
            else:
                print(f"No champion promoted: selected model path missing: {best_model_path}")
        else:
            print(f"No champion promoted: no candidates match ticker '{canonical_ticker}'")
    # --------------------------

    print(f"Saved leaderboard: {leaderboard_path}")
    print(f"Saved reward leaderboard: {reward_leaderboard_path}")
    print(f"Saved summary: {summary_path}")
    if "snapshot_paths" in summary:
        snapshot_paths = summary["snapshot_paths"]
        if isinstance(snapshot_paths, dict):
            print(f"Saved snapshots: {snapshot_paths.get('leaderboard')}")
    if args.compact_output:
        compact_cols = [
            "run_label",
            "ticker",
            "interval",
            "seed",
            "trade_penalty",
            "reward_action_bonus_scale",
            "test_trade_count",
            "test_trade_win_rate",
            "test_actionable_accuracy",
            "ranking_score",
        ]
        available = [c for c in compact_cols if c in top.columns]
        print("Top runs (compact):")
        print(top[available].to_string(index=False))
    else:
        print("Top run (Transposed for readability):")
        print(top.head(1).T.to_string(header=False))


if __name__ == "__main__":
    main()

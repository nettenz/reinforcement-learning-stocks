from __future__ import annotations

import argparse
from datetime import datetime, timezone
import itertools
import json
import platform
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.signal_analytics import compute_metrics, enrich_with_truth_labels
from src.trading_env import TradingEnv
from src.market_data import fetch_yahoo_ohlcv


DEFAULT_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_leaderboard.csv"
DEFAULT_REWARD_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_reward_leaderboard.csv"
DEFAULT_SUMMARY_PATH = ROOT_DIR / "data" / "experiment_summary.json"
DEFAULT_SNAPSHOT_DIR = ROOT_DIR / "data" / "experiment_snapshots"

# Use M4 GPU (MPS) if available for Mac, default to CPU on Windows for stability
if torch.backends.mps.is_available():
    DEFAULT_PPO_DEVICE = "mps"  # Apple Silicon GPU acceleration
elif platform.system() == "Windows":
    DEFAULT_PPO_DEVICE = "cpu"  # Force CPU on Windows for stability
elif torch.cuda.is_available():
    DEFAULT_PPO_DEVICE = "cuda"  # NVIDIA GPU on Linux
else:
    DEFAULT_PPO_DEVICE = "cpu"  # CPU fallback


def _parse_float_list(value: str) -> list[float]:
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _parse_int_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


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


def _simulate_with_model(model: PPO, df: pd.DataFrame, env_kwargs: dict[str, float | bool]) -> pd.DataFrame:
    env = TradingEnv(df, **env_kwargs)
    obs, _ = env.reset()
    rows: list[dict[str, float | int | pd.Timestamp]] = []

    while True:
        step_idx = env.current_step
        action, _ = model.predict(obs, deterministic=True)
        price = float(df.loc[step_idx, env.price_column])
        date_value = pd.to_datetime(df.loc[step_idx, "Date"]) if "Date" in df.columns else step_idx

        obs, reward, terminated, truncated, info = env.step(int(action))
        rows.append(
            {
                "step": step_idx,
                "date": date_value,
                "price": price,
                "action": int(action),
                "reward": float(reward),
                "net_worth": float(env.net_worth),
                "reward_portfolio_return": float(info.get("reward_portfolio_return", 0.0)),
                "reward_direction": float(info.get("reward_direction", 0.0)),
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
            f"{prefix}_reward_hold_penalty_mean": 0.0,
            f"{prefix}_reward_action_bonus_mean": 0.0,
            f"{prefix}_reward_drawdown_penalty_mean": 0.0,
            f"{prefix}_reward_drawdown_mean": 0.0,
        }

    return {
        f"{prefix}_reward_total_mean": float(signal_df["reward"].mean()),
        f"{prefix}_reward_total_sum": float(signal_df["reward"].sum()),
        f"{prefix}_reward_portfolio_return_mean": float(signal_df["reward_portfolio_return"].mean()),
        f"{prefix}_reward_direction_mean": float(signal_df["reward_direction"].mean()),
        f"{prefix}_reward_hold_penalty_mean": float(signal_df["reward_hold_penalty"].mean()),
        f"{prefix}_reward_action_bonus_mean": float(signal_df.get("reward_action_bonus", pd.Series([0.0])).mean()),
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


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def _annualized_sharpe(returns: pd.Series) -> float:
    clean = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    std = float(clean.std(ddof=0))
    if std <= 1e-12:
        return 0.0
    return float(np.sqrt(252.0) * clean.mean() / std)


def _annualized_sortino(returns: pd.Series) -> float:
    clean = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    if downside_std <= 1e-12:
        return 0.0
    return float(np.sqrt(252.0) * clean.mean() / downside_std)


def _risk_metrics_from_equity(equity: pd.Series, prefix: str) -> dict[str, float]:
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
        f"{prefix}_sharpe_ratio": _annualized_sharpe(returns),
        f"{prefix}_sortino_ratio": _annualized_sortino(returns),
        f"{prefix}_max_drawdown": max_drawdown,
    }


def _fetch_qqq_prices(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    raw = fetch_yahoo_ohlcv(
        tickers=("QQQ",),
        start=pd.to_datetime(start_date).strftime("%Y-%m-%d"),
        end=(pd.to_datetime(end_date) + pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        interval="1d",
    )
    qqq = raw[["Date", "Close"]].copy()
    qqq["Date"] = pd.to_datetime(qqq["Date"]).dt.tz_localize(None).dt.normalize()
    qqq = qqq.sort_values("Date").drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)
    return qqq


def _benchmark_equity_curve(period_df: pd.DataFrame, qqq_prices: pd.DataFrame, initial_balance: float = 1000.0) -> pd.Series:
    if "Date" not in period_df.columns:
        raise ValueError("QQQ benchmark requires a Date column in the period dataframe.")

    period_dates = pd.to_datetime(period_df["Date"]).dt.tz_localize(None).dt.normalize()
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


def write_experiment_outputs(
    leaderboard: pd.DataFrame,
    leaderboard_path: Path,
    reward_leaderboard_path: Path,
    summary_path: Path,
    snapshot_dir: Path | None = DEFAULT_SNAPSHOT_DIR,
    run_label: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    reward_leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    leaderboard.to_csv(leaderboard_path, index=False)
    reward_leaderboard = leaderboard.sort_values("val_reward_total_mean", ascending=False).reset_index(drop=True)
    reward_leaderboard.to_csv(reward_leaderboard_path, index=False)

    timestamp = _timestamp_slug()
    summary: dict[str, object] = {
        "rows": int(len(leaderboard)),
        "generated_at_utc": timestamp,
        "leaderboard_path": str(leaderboard_path),
        "reward_leaderboard_path": str(reward_leaderboard_path),
        "top3": leaderboard.head(3).to_dict(orient="records"),
    }

    if snapshot_dir is not None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{timestamp}_{_safe_label(run_label)}" if run_label else timestamp
        snapshot_leaderboard_path = snapshot_dir / f"experiment_leaderboard_{suffix}.csv"
        snapshot_reward_leaderboard_path = snapshot_dir / f"experiment_reward_leaderboard_{suffix}.csv"
        snapshot_summary_path = snapshot_dir / f"experiment_summary_{suffix}.json"

        leaderboard.to_csv(snapshot_leaderboard_path, index=False)
        reward_leaderboard.to_csv(snapshot_reward_leaderboard_path, index=False)
        snapshot_summary = {
            **summary,
            "leaderboard_path": str(snapshot_leaderboard_path),
            "reward_leaderboard_path": str(snapshot_reward_leaderboard_path),
        }
        snapshot_summary_path.write_text(json.dumps(snapshot_summary, indent=2), encoding="utf-8")
        summary["snapshot_paths"] = {
            "leaderboard": str(snapshot_leaderboard_path),
            "reward_leaderboard": str(snapshot_reward_leaderboard_path),
            "summary": str(snapshot_summary_path),
        }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return reward_leaderboard, summary


def run_experiments(args: argparse.Namespace) -> pd.DataFrame:
    seeds = _parse_int_list(args.seeds)
    learning_rates = _parse_float_list(args.learning_rates)
    gammas = _parse_float_list(args.gammas)
    ent_coefs = _parse_float_list(args.ent_coefs)
    timesteps_list = _parse_int_list(args.timesteps)

    df = get_tech_training_data(
        include_news=args.include_news,
        refresh=args.refresh_data,
        news_refresh=args.refresh_news,
        use_stationary_features=args.use_stationary_features,
    )
    train_df, val_df, test_df = _split_walk_forward(df, train_ratio=args.train_ratio, val_ratio=args.val_ratio)
    qqq_prices = _fetch_qqq_prices(
        start_date=pd.to_datetime(val_df["Date"]).min(),
        end_date=pd.to_datetime(test_df["Date"]).max(),
    )
    val_benchmark_equity = _benchmark_equity_curve(val_df, qqq_prices=qqq_prices)
    test_benchmark_equity = _benchmark_equity_curve(test_df, qqq_prices=qqq_prices)
    val_benchmark_risk = _risk_metrics_from_equity(val_benchmark_equity, prefix="val_benchmark")
    test_benchmark_risk = _risk_metrics_from_equity(test_benchmark_equity, prefix="test_benchmark")

    env_kwargs: dict[str, float | bool] = {
        "transaction_cost_rate": args.transaction_cost_rate,
        "trade_penalty": args.trade_penalty,
        "reward_clip": args.reward_clip,
        "reward_ignore_transaction_cost": args.reward_ignore_transaction_cost,
    }

    reward_return_scales = _parse_float_list(args.reward_return_scale)
    reward_direction_scales = _parse_float_list(args.reward_direction_scale)
    reward_hold_penalty_scales = _parse_float_list(args.reward_hold_penalty_scale)
    reward_drawdown_penalty_scales = _parse_float_list(args.reward_drawdown_penalty_scale)
    reward_action_bonus_scales = _parse_float_list(args.reward_action_bonus_scale)

    configs = list(itertools.product(
        seeds, timesteps_list, learning_rates, gammas, ent_coefs,
        reward_return_scales, reward_direction_scales, reward_hold_penalty_scales,
        reward_drawdown_penalty_scales, reward_action_bonus_scales
    ))
    if args.max_runs > 0:
        configs = configs[: args.max_runs]

    rows: list[dict[str, float | int]] = []
    print(f"Running {len(configs)} experiment runs...")

    for idx, (seed, timesteps, learning_rate, gamma, ent_coef, 
              ret_scale, dir_scale, hold_scale, dd_scale, bonus_scale) in enumerate(configs, start=1):
        print(
            f"[{idx}/{len(configs)}] seed={seed} timesteps={timesteps} lr={learning_rate} "
            f"gamma={gamma} ent_coef={ent_coef} dir_scale={dir_scale}"
        )
        lr_arg = linear_schedule(learning_rate) if args.use_lr_schedule else learning_rate
        
        env_kwargs_run = env_kwargs.copy()
        env_kwargs_run.update({
            "reward_return_scale": ret_scale,
            "reward_direction_scale": dir_scale,
            "reward_hold_penalty_scale": hold_scale,
            "reward_drawdown_penalty_scale": dd_scale,
            "reward_action_bonus_scale": bonus_scale,
        })

        if args.n_envs > 1:
            env_train = SubprocVecEnv([make_env(train_df, env_kwargs_run) for _ in range(args.n_envs)])
        else:
            env_train = TradingEnv(train_df, **env_kwargs_run)
            
        model = PPO(
            "MlpPolicy",
            env_train,
            verbose=0,
            seed=seed,
            learning_rate=lr_arg,
            gamma=gamma,
            ent_coef=ent_coef,
            device=DEFAULT_PPO_DEVICE,
        )
        model.learn(total_timesteps=timesteps)
        
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

        row: dict[str, float | int] = {
            "seed": seed,
            "timesteps": timesteps,
            "learning_rate": learning_rate,
            "gamma": gamma,
            "ent_coef": ent_coef,
            "include_news": int(args.include_news),
            "threshold": args.threshold,
            "horizon": args.horizon,
            "transaction_cost_rate": args.transaction_cost_rate,
            "trade_penalty": args.trade_penalty,
            "reward_return_scale": ret_scale,
            "reward_direction_scale": dir_scale,
            "reward_hold_penalty_scale": hold_scale,
            "reward_drawdown_penalty_scale": dd_scale,
            "reward_action_bonus_scale": bonus_scale,
            "reward_clip": args.reward_clip,
            "reward_ignore_transaction_cost": int(args.reward_ignore_transaction_cost),
            "val_overall_accuracy": val_metrics.overall_accuracy,
            "val_actionable_accuracy": val_metrics.actionable_accuracy,
            "val_trade_win_rate": val_metrics.trade_win_rate,
            "val_cumulative_signal_return": val_metrics.cumulative_signal_return,
            "test_overall_accuracy": test_metrics.overall_accuracy,
            "test_actionable_accuracy": test_metrics.actionable_accuracy,
            "test_trade_win_rate": test_metrics.trade_win_rate,
            "test_cumulative_signal_return": test_metrics.cumulative_signal_return,
            "val_alpha_vs_qqq": float(val_strategy_risk["val_cumulative_return"] - val_benchmark_risk["val_benchmark_cumulative_return"]),
            "test_alpha_vs_qqq": float(test_strategy_risk["test_cumulative_return"] - test_benchmark_risk["test_benchmark_cumulative_return"]),
            "ranking_score": _ranking_score(val_metrics),
        }
        row.update(val_reward)
        row.update(test_reward)
        row.update(val_strategy_risk)
        row.update(test_strategy_risk)
        row.update(val_benchmark_risk)
        row.update(test_benchmark_risk)
        rows.append(row)

    leaderboard = pd.DataFrame(rows).sort_values("ranking_score", ascending=False).reset_index(drop=True)
    return leaderboard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggressive multi-seed PPO experiment runner.")
    parser.add_argument("--include-news", action="store_true", help="Train with merged sentiment features.")
    parser.add_argument("--refresh-data", action="store_true", help="Refresh OHLCV training data cache.")
    parser.add_argument("--refresh-news", action="store_true", help="Refresh news sentiment cache.")
    parser.add_argument("--seeds", default="7,13,21", help="Comma-separated seeds.")
    parser.add_argument("--timesteps", default="50000,100000", help="Comma-separated timesteps.")
    parser.add_argument("--learning-rates", default="0.0003,0.0001", help="Comma-separated learning rates.")
    parser.add_argument("--gammas", default="0.99,0.995", help="Comma-separated gammas.")
    parser.add_argument("--ent-coefs", default="0.0,0.01", help="Comma-separated entropy coefficients.")
    parser.add_argument("--threshold", type=float, default=0.002, help="Signal threshold for evaluation.")
    parser.add_argument("--horizon", type=int, default=1, help="Forward horizon steps for evaluation.")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Walk-forward train ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Walk-forward validation ratio.")
    parser.add_argument("--transaction-cost-rate", type=float, default=0.001, help="Fee rate per executed trade.")
    parser.add_argument("--trade-penalty", type=float, default=0.05, help="Flat penalty per executed trade.")
    parser.add_argument("--reward-return-scale", default="1.0", help="Weight for portfolio-return reward term (list).")
    parser.add_argument("--reward-direction-scale", default="0.35", help="Weight for directional-alignment reward term (list).")
    parser.add_argument("--reward-hold-penalty-scale", default="0.10", help="Penalty scale for hold during movement (list).")
    parser.add_argument("--reward-drawdown-penalty-scale", default="0.10", help="Penalty scale for drawdown term (list).")
    parser.add_argument("--reward-action-bonus-scale", default="0.02", help="Bonus for taking Buy/Sell actions (list).")

    parser.add_argument("--reward-clip", type=float, default=1.0, help="Reward clip bound applied symmetrically.")
    parser.add_argument(
        "--reward-ignore-transaction-cost",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude transaction costs/penalties from reward shaping while keeping execution unchanged.",
    )
    parser.add_argument("--use-stationary-features", action="store_true", help="Use log returns and normalized technical indicators.")
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
    parser.add_argument("--run-label", default="", help="Optional suffix label appended to snapshot filenames.")
    parser.add_argument("--device", default=DEFAULT_PPO_DEVICE, help="PPO device (auto, cuda, cpu).")
    parser.add_argument("--use-lr-schedule", action="store_true", help="Use linear learning rate decay.")
    parser.add_argument("--n-envs", type=int, default=1, help="Number of parallel environments for vectorized training.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Update global device if provided
    global DEFAULT_PPO_DEVICE
    DEFAULT_PPO_DEVICE = args.device

    leaderboard = run_experiments(args)
    leaderboard_path = Path(args.leaderboard_path)
    reward_leaderboard_path = Path(args.reward_leaderboard_path)
    summary_path = Path(args.summary_path)
    snapshot_dir = None if args.disable_snapshots else Path(args.snapshot_dir)
    run_label = args.run_label.strip() or None
    reward_leaderboard, summary = write_experiment_outputs(
        leaderboard=leaderboard,
        leaderboard_path=leaderboard_path,
        reward_leaderboard_path=reward_leaderboard_path,
        summary_path=summary_path,
        snapshot_dir=snapshot_dir,
        run_label=run_label,
    )
    top = leaderboard.head(3)

    print(f"Saved leaderboard: {leaderboard_path}")
    print(f"Saved reward leaderboard: {reward_leaderboard_path}")
    print(f"Saved summary: {summary_path}")
    if "snapshot_paths" in summary:
        snapshot_paths = summary["snapshot_paths"]
        if isinstance(snapshot_paths, dict):
            print(f"Saved snapshots: {snapshot_paths.get('leaderboard')}")
    print("Top run:")
    print(top.head(1).to_string(index=False))


if __name__ == "__main__":
    main()

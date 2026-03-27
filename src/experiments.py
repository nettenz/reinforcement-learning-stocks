from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.signal_analytics import compute_metrics, enrich_with_truth_labels
from src.trading_env import TradingEnv


DEFAULT_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_leaderboard.csv"
DEFAULT_SUMMARY_PATH = ROOT_DIR / "data" / "experiment_summary.json"


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


def _simulate_with_model(model: PPO, df: pd.DataFrame, env_kwargs: dict[str, float]) -> pd.DataFrame:
    env = TradingEnv(df, **env_kwargs)
    obs, _ = env.reset()
    rows: list[dict[str, float | int | pd.Timestamp]] = []

    while True:
        step_idx = env.current_step
        action, _ = model.predict(obs, deterministic=True)
        price = float(df.loc[step_idx, env.price_column])
        date_value = pd.to_datetime(df.loc[step_idx, "Date"]) if "Date" in df.columns else step_idx

        obs, reward, terminated, truncated, _ = env.step(int(action))
        rows.append(
            {
                "step": step_idx,
                "date": date_value,
                "price": price,
                "action": int(action),
                "reward": float(reward),
                "net_worth": float(env.net_worth),
            }
        )
        if terminated or truncated:
            break

    return pd.DataFrame(rows)


def _ranking_score(metrics_obj) -> float:
    cumulative_clipped = max(min(metrics_obj.cumulative_signal_return, 1.0), -1.0)
    return (
        0.50 * metrics_obj.actionable_accuracy
        + 0.30 * metrics_obj.trade_win_rate
        + 0.20 * cumulative_clipped
    )


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
    )
    train_df, val_df, test_df = _split_walk_forward(df, train_ratio=args.train_ratio, val_ratio=args.val_ratio)

    env_kwargs = {
        "transaction_cost_rate": args.transaction_cost_rate,
        "trade_penalty": args.trade_penalty,
    }

    configs = list(itertools.product(seeds, timesteps_list, learning_rates, gammas, ent_coefs))
    if args.max_runs > 0:
        configs = configs[: args.max_runs]

    rows: list[dict[str, float | int]] = []
    print(f"Running {len(configs)} experiment runs...")

    for idx, (seed, timesteps, learning_rate, gamma, ent_coef) in enumerate(configs, start=1):
        print(
            f"[{idx}/{len(configs)}] seed={seed} timesteps={timesteps} lr={learning_rate} "
            f"gamma={gamma} ent_coef={ent_coef}"
        )
        env_train = TradingEnv(train_df, **env_kwargs)
        model = PPO(
            "MlpPolicy",
            env_train,
            verbose=0,
            seed=seed,
            learning_rate=learning_rate,
            gamma=gamma,
            ent_coef=ent_coef,
        )
        model.learn(total_timesteps=timesteps)

        val_signals = _simulate_with_model(model, val_df, env_kwargs=env_kwargs)
        test_signals = _simulate_with_model(model, test_df, env_kwargs=env_kwargs)

        val_enriched = enrich_with_truth_labels(val_signals, threshold=args.threshold, horizon_steps=args.horizon)
        test_enriched = enrich_with_truth_labels(test_signals, threshold=args.threshold, horizon_steps=args.horizon)
        val_metrics = compute_metrics(val_enriched)
        test_metrics = compute_metrics(test_enriched)

        rows.append(
            {
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
                "val_overall_accuracy": val_metrics.overall_accuracy,
                "val_actionable_accuracy": val_metrics.actionable_accuracy,
                "val_trade_win_rate": val_metrics.trade_win_rate,
                "val_cumulative_signal_return": val_metrics.cumulative_signal_return,
                "test_overall_accuracy": test_metrics.overall_accuracy,
                "test_actionable_accuracy": test_metrics.actionable_accuracy,
                "test_trade_win_rate": test_metrics.trade_win_rate,
                "test_cumulative_signal_return": test_metrics.cumulative_signal_return,
                "ranking_score": _ranking_score(val_metrics),
            }
        )

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
    parser.add_argument("--max-runs", type=int, default=0, help="Limit number of experiment runs (0 = all).")
    parser.add_argument("--leaderboard-path", default=str(DEFAULT_LEADERBOARD_PATH), help="CSV output path.")
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH), help="JSON summary output path.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    leaderboard = run_experiments(args)
    leaderboard_path = Path(args.leaderboard_path)
    summary_path = Path(args.summary_path)
    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    leaderboard.to_csv(leaderboard_path, index=False)
    top = leaderboard.head(3)
    summary = {
        "rows": int(len(leaderboard)),
        "leaderboard_path": str(leaderboard_path),
        "top3": top.to_dict(orient="records"),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Saved leaderboard: {leaderboard_path}")
    print(f"Saved summary: {summary_path}")
    print("Top run:")
    print(top.head(1).to_string(index=False))


if __name__ == "__main__":
    main()


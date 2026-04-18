#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baseline_agents import BuyHoldPolicy, FlatPolicy, SupervisedRegressionPolicy
from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv


DEFAULT_TICKERS = ("AAPL", "NVDA")


@dataclass(frozen=True)
class TradingSummary:
    policy_name: str
    ticker: str
    horizon: int
    split: str
    rows: int
    trades: int
    trade_rate: float
    trade_win_rate: float
    final_net_worth: float
    cumulative_return: float
    max_drawdown: float
    mean_step_return: float
    sharpe_like: float


class MarketFeaturePolicyWrapper:
    def __init__(self, base_policy, market_feature_count: int):
        self.base_policy = base_policy
        self.market_feature_count = int(market_feature_count)

    def predict(self, obs, deterministic: bool = True):
        obs_array = np.asarray(obs)
        market_obs = obs_array[: self.market_feature_count]
        return self.base_policy.predict(market_obs, deterministic=deterministic)


class PredictionThresholdPolicyWrapper:
    def __init__(self, base_policy, long_threshold: float = 0.0005):
        self.base_policy = base_policy
        self.long_threshold = float(long_threshold)

    def predict(self, obs, deterministic: bool = True):
        prediction, _ = self.base_policy.predict(obs, deterministic=deterministic)
        pred_value = float(np.asarray(prediction).reshape(-1)[0])
        if pred_value > self.long_threshold:
            return 1.0, None
        if pred_value < -self.long_threshold:
            return -1.0, None
        return 0.0, None


class MomentumFeatureRulePolicy:
    """Trade with the sign of the first market feature (typically recent return)."""

    def __init__(self, threshold: float = 0.0005):
        self.threshold = float(threshold)

    def predict(self, obs, deterministic: bool = True):
        obs_array = np.asarray(obs).reshape(-1)
        value = float(obs_array[0]) if len(obs_array) else 0.0
        if value > self.threshold:
            return 1.0, None
        if value < -self.threshold:
            return -1.0, None
        return 0.0, None


class MeanReversionFeatureRulePolicy:
    """Trade opposite to the sign of the first market feature."""

    def __init__(self, threshold: float = 0.0005):
        self.threshold = float(threshold)

    def predict(self, obs, deterministic: bool = True):
        obs_array = np.asarray(obs).reshape(-1)
        value = float(obs_array[0]) if len(obs_array) else 0.0
        if value > self.threshold:
            return -1.0, None
        if value < -self.threshold:
            return 1.0, None
        return 0.0, None


def parse_csv_values(raw: str, cast) -> list:
    out: list = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            out.append(cast(item))
    return out


def select_feature_columns(df: pd.DataFrame, include_news: bool) -> list[str]:
    exclude = {
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "RawClose",
        "OrigOpen",
        "OrigHigh",
        "OrigLow",
        "OrigClose",
        "OrigVolume",
    }
    news_cols = {
        "NewsCount",
        "SentimentMean",
        "SentimentStd",
        "SentimentMin",
        "SentimentMax",
        "SentimentConfidenceMean",
        "SentimentGeminiShare",
        "SentimentOllamaShare",
    }
    feature_cols = [col for col in df.columns if col not in exclude]
    if not include_news:
        feature_cols = [col for col in feature_cols if col not in news_cols]
    return feature_cols


def split_walk_forward(df: pd.DataFrame, train_ratio: float = 0.70, val_ratio: float = 0.15) -> dict[str, pd.DataFrame]:
    ordered = df.sort_values("Date").reset_index(drop=True)
    n = len(ordered)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)
    return {
        "train": ordered.iloc[:train_end].copy(),
        "val": ordered.iloc[train_end:val_end].copy(),
        "test": ordered.iloc[val_end:].copy(),
    }


def prepare_dataframe(ticker: str, include_news: bool, use_stationary_features: bool = True) -> pd.DataFrame:
    frame = get_tech_training_data(
        tickers=[ticker],
        include_news=include_news,
        use_stationary_features=use_stationary_features,
    )
    if frame.empty:
        raise ValueError(f"No data returned for {ticker}")
    return frame


def price_column(frame: pd.DataFrame) -> str:
    if "RawClose" in frame.columns:
        return "RawClose"
    if "Close" in frame.columns:
        return "Close"
    raise ValueError(f"No RawClose/Close column present. Columns: {list(frame.columns)}")


def make_supervised_policy(train_frame: pd.DataFrame, feature_cols: list[str], horizon: int, model_type: str) -> SupervisedRegressionPolicy:
    price_col = price_column(train_frame)
    prices = pd.to_numeric(train_frame[price_col], errors="coerce")
    features = train_frame[feature_cols].replace([np.inf, -np.inf], np.nan)
    valid_mask = np.isfinite(features.to_numpy()).all(axis=1)

    future_prices = prices.shift(-horizon)
    targets = np.log(future_prices / prices).replace([np.inf, -np.inf], np.nan)
    valid_mask &= prices.notna().to_numpy() & future_prices.notna().to_numpy() & targets.notna().to_numpy()

    X_train = features.to_numpy()[valid_mask]
    y_train = targets.to_numpy()[valid_mask]
    if len(X_train) < 20:
        raise ValueError(f"Too few valid training rows: {len(X_train)}")

    policy = SupervisedRegressionPolicy(model_class=model_type)
    policy.train(X_train, y_train)
    return policy


def evaluate_policy(frame: pd.DataFrame, feature_cols: list[str], policy, policy_name: str, split_name: str) -> TradingSummary:
    frame = frame.reset_index(drop=True).copy()
    env = TradingEnv(
        frame,
        include_position_in_observation=True,
        market_feature_columns=feature_cols,
        transaction_cost_rate=0.001,
        trade_penalty=0.0,
        reward_ignore_transaction_cost=False,
        execution_mode="next_bar",
    )

    obs, _ = env.reset()
    net_worths = [float(env.net_worth)]
    step_returns: list[float] = []
    trade_count = 0
    trade_wins = 0

    while True:
        action, _ = policy.predict(obs, deterministic=True)
        prev_net_worth = float(env.net_worth)
        obs, reward, terminated, truncated, info = env.step(action)
        curr_net_worth = float(env.net_worth)
        step_return = (curr_net_worth / max(prev_net_worth, 1e-8)) - 1.0
        step_returns.append(step_return)
        net_worths.append(curr_net_worth)

        if info.get("execution_notional", 0.0) > 0:
            trade_count += 1
            if step_return > 0:
                trade_wins += 1

        if terminated or truncated:
            break

    equity = np.asarray(net_worths, dtype=float)
    equity_peak = np.maximum.accumulate(equity)
    drawdown = np.where(equity_peak > 0, (equity_peak - equity) / equity_peak, 0.0)
    step_returns_arr = np.asarray(step_returns, dtype=float)

    return TradingSummary(
        policy_name=policy_name,
        ticker=str(frame.get("ticker", pd.Series(["unknown"])).iloc[0]) if "ticker" in frame.columns else "unknown",
        horizon=0,
        split=split_name,
        rows=len(frame),
        trades=trade_count,
        trade_rate=float(trade_count / max(len(frame), 1)),
        trade_win_rate=float(trade_wins / max(trade_count, 1)),
        final_net_worth=float(equity[-1]),
        cumulative_return=float((equity[-1] / max(equity[0], 1e-8)) - 1.0),
        max_drawdown=float(drawdown.max(initial=0.0)),
        mean_step_return=float(step_returns_arr.mean() if len(step_returns_arr) else 0.0),
        sharpe_like=float(step_returns_arr.mean() / (step_returns_arr.std() + 1e-12) if len(step_returns_arr) > 1 else 0.0),
    )


def run_for_ticker(ticker: str, horizon: int, include_news: bool, model_type: str, threshold: float, include_simple_rules: bool) -> dict:
    frame = prepare_dataframe(ticker=ticker, include_news=include_news, use_stationary_features=True)
    feature_cols = select_feature_columns(frame, include_news=include_news)
    splits = split_walk_forward(frame)

    supervised_policy = make_supervised_policy(splits["train"], feature_cols=feature_cols, horizon=horizon, model_type=model_type)
    supervised_policy = MarketFeaturePolicyWrapper(supervised_policy, market_feature_count=len(feature_cols))
    supervised_policy = PredictionThresholdPolicyWrapper(supervised_policy, long_threshold=threshold)
    policies: list[tuple[str, object]] = [
        (f"supervised-{model_type}-thresholded", supervised_policy),
        ("flat", FlatPolicy()),
        ("buy_hold", BuyHoldPolicy()),
    ]
    if include_simple_rules:
        policies.extend(
            [
                ("momentum_rule", MomentumFeatureRulePolicy(threshold=threshold)),
                ("mean_reversion_rule", MeanReversionFeatureRulePolicy(threshold=threshold)),
            ]
        )

    report: dict = {
        "ticker": ticker,
        "horizon": horizon,
        "include_news": include_news,
        "feature_count": len(feature_cols),
        "feature_columns": feature_cols,
        "splits": {},
    }

    for split_name, split_frame in splits.items():
        split_frame = split_frame.copy()
        if split_frame.empty:
            raise ValueError(f"Empty split '{split_name}' for {ticker}")

        summaries: dict[str, dict] = {}
        for policy_name, policy in policies:
            summary = evaluate_policy(
                frame=split_frame,
                feature_cols=feature_cols,
                policy=policy,
                policy_name=policy_name,
                split_name=split_name,
            )
            summaries[policy_name] = asdict(summary)
            summaries[policy_name]["horizon"] = horizon
            summaries[policy_name]["ticker"] = ticker

        report["splits"][split_name] = summaries

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 trading-level evaluation")
    parser.add_argument("--tickers", type=str, default=",".join(DEFAULT_TICKERS), help="Comma-separated tickers")
    parser.add_argument("--horizon", type=int, default=1, help="Prediction horizon used for supervised policy training")
    parser.add_argument("--output", type=str, default=str(ROOT / "logs" / "stage1_trading_eval.json"), help="Output JSON path")
    parser.add_argument("--include-news", action="store_true", help="Include news features")
    parser.add_argument("--include-simple-rules", action="store_true", help="Add momentum and mean-reversion rule baselines")
    parser.add_argument("--model-type", type=str, default="linear", choices=["linear", "rf", "xgb", "mlp"], help="Supervised model type")
    parser.add_argument("--threshold", type=float, default=0.0005, help="Prediction threshold for long/flat/short trading rule")
    args = parser.parse_args()

    tickers = parse_csv_values(args.tickers, str.upper)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "tickers": tickers,
        "horizon": args.horizon,
        "include_news": bool(args.include_news),
        "model_type": args.model_type,
        "reports": [],
    }

    for ticker in tickers:
        print(f"\n=== {ticker} | horizon={args.horizon} | model={args.model_type} ===")
        report = run_for_ticker(
            ticker=ticker,
            horizon=args.horizon,
            include_news=args.include_news,
            model_type=args.model_type,
            threshold=args.threshold,
            include_simple_rules=bool(args.include_simple_rules),
        )
        payload["reports"].append(report)

        for split_name, policy_map in report["splits"].items():
            print(f"  Split: {split_name}")
            for policy_name, summary in policy_map.items():
                print(
                    f"    {policy_name}: return={summary['cumulative_return']:.4f}, dd={summary['max_drawdown']:.4f}, "
                    f"trades={summary['trades']}, win_rate={summary['trade_win_rate']:.3f}"
                )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote trading-level evaluation to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
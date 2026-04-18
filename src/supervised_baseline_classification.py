"""
Stage 1 supervised classification baseline.

This companion baseline keeps the Stage 1 gate-compatible metrics (`val_r2`, `test_r2`)
by projecting class probabilities into an expected signed-return proxy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.baseline_agents import SupervisedClassificationPolicy
from src.market_data import get_tech_training_data


def _select_feature_columns(df: pd.DataFrame, use_news: bool) -> list[str]:
    exclude_cols = {
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
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    if not use_news:
        feature_cols = [c for c in feature_cols if c not in news_cols]
    return feature_cols


def _price_series(df: pd.DataFrame) -> pd.Series:
    if "RawClose" in df.columns:
        return pd.to_numeric(df["RawClose"], errors="coerce")
    if "Close" in df.columns:
        return pd.to_numeric(df["Close"], errors="coerce")
    raise ValueError(f"No RawClose/Close column available. Columns={list(df.columns)}")


def _split_indices(n: int, train_ratio: float = 0.70, val_ratio: float = 0.15) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)
    idx = np.arange(n)
    return idx < train_end, (idx >= train_end) & (idx < val_end), idx >= val_end


def _classify_targets(returns: np.ndarray, class_threshold: float) -> np.ndarray:
    labels = np.zeros_like(returns, dtype=int)
    labels[returns > class_threshold] = 1
    labels[returns < -class_threshold] = -1
    return labels


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if denom <= 1e-12:
        return 0.0
    return float(1.0 - np.sum((y_true - y_pred) ** 2) / denom)


def run_baseline(
    ticker: str,
    horizon: int,
    model_type: str,
    class_threshold: float,
    use_news: bool,
    output_dir: str,
    seed: int,
) -> dict:
    np.random.seed(seed)

    df = get_tech_training_data(
        tickers=[ticker],
        include_news=use_news,
        use_stationary_features=True,
    )
    if df.empty:
        raise ValueError(f"No data loaded for ticker={ticker}")

    features = _select_feature_columns(df, use_news=use_news)
    X = df[features].replace([np.inf, -np.inf], np.nan).to_numpy()
    prices = _price_series(df)
    future = prices.shift(-horizon)
    y = np.log(future / prices).replace([np.inf, -np.inf], np.nan).to_numpy()

    valid = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X = X[valid]
    y = y[valid]

    train_mask, val_mask, test_mask = _split_indices(len(X))
    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    if len(X_train) < 20 or len(X_val) < 10 or len(X_test) < 10:
        raise ValueError(
            f"Insufficient split sizes: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}"
        )

    y_train_cls = _classify_targets(y_train, class_threshold=class_threshold)
    y_val_cls = _classify_targets(y_val, class_threshold=class_threshold)
    y_test_cls = _classify_targets(y_test, class_threshold=class_threshold)

    policy = SupervisedClassificationPolicy(model_class=model_type, random_state=seed)
    policy.train(X_train, y_train_cls)

    # Probabilistic class expectation mapped to signed-return proxy for gate-compatible R2.
    # sklearn class order after mapping is 0->short, 1->flat, 2->long.
    class_values = np.array([-1.0, 0.0, 1.0], dtype=float)
    return_scale = float(max(np.mean(np.abs(y_train)), 1e-6))

    if hasattr(policy.model, "predict_proba"):
        val_probs = policy.model.predict_proba(X_val)
        test_probs = policy.model.predict_proba(X_test)
        val_expected_sign = val_probs @ class_values
        test_expected_sign = test_probs @ class_values
    else:
        # Fallback for classifiers without probability support.
        val_pred = policy.model.predict(X_val)
        test_pred = policy.model.predict(X_test)
        reverse_map = {0: -1.0, 1: 0.0, 2: 1.0}
        val_expected_sign = np.array([reverse_map[int(x)] for x in val_pred], dtype=float)
        test_expected_sign = np.array([reverse_map[int(x)] for x in test_pred], dtype=float)

    y_val_proxy = val_expected_sign * return_scale
    y_test_proxy = test_expected_sign * return_scale

    val_mse = float(np.mean((y_val - y_val_proxy) ** 2))
    val_mae = float(np.mean(np.abs(y_val - y_val_proxy)))
    val_r2 = _r2(y_val, y_val_proxy)

    test_mse = float(np.mean((y_test - y_test_proxy) ** 2))
    test_mae = float(np.mean(np.abs(y_test - y_test_proxy)))
    test_r2 = _r2(y_test, y_test_proxy)

    val_pred_cls = _classify_targets(y_val_proxy, class_threshold=class_threshold)
    test_pred_cls = _classify_targets(y_test_proxy, class_threshold=class_threshold)

    results = {
        "ticker": ticker,
        "horizon": horizon,
        "model_type": model_type,
        "target_type": "classification",
        "class_threshold": class_threshold,
        "return_proxy_scale": return_scale,
        "use_stationary": True,
        "use_news": use_news,
        "n_features": int(X.shape[1]),
        "feature_names": features,
        "train_samples": int(len(X_train)),
        "val_samples": int(len(X_val)),
        "test_samples": int(len(X_test)),
        "seed": seed,
        "timestamp": datetime.now().isoformat(),
        "val_mse": val_mse,
        "val_mae": val_mae,
        "val_r2": val_r2,
        "test_mse": test_mse,
        "test_mae": test_mae,
        "test_r2": test_r2,
        "val_class_accuracy": float(np.mean(y_val_cls == val_pred_cls)),
        "test_class_accuracy": float(np.mean(y_test_cls == test_pred_cls)),
    }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"stage1_baseline_{ticker}_{model_type}_clf_{horizon}h.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(
        f"[{ticker} | {model_type} | clf] val_r2={val_r2:.6f}, test_r2={test_r2:.6f}, "
        f"val_acc={results['val_class_accuracy']:.4f}, test_acc={results['test_class_accuracy']:.4f}"
    )
    print(f"Wrote {output_path}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 supervised classification baseline")
    parser.add_argument("--ticker", type=str, default="AAPL")
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--model-type", type=str, default="rf", choices=["rf", "xgb", "svm", "mlp"])
    parser.add_argument("--class-threshold", type=float, default=0.0005, help="Return dead-zone threshold for class labels")
    parser.add_argument("--use-news", action="store_true")
    parser.add_argument("--output-dir", type=str, default="results/stage1/")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    run_baseline(
        ticker=str(args.ticker).upper(),
        horizon=int(args.horizon),
        model_type=str(args.model_type).lower(),
        class_threshold=float(args.class_threshold),
        use_news=bool(args.use_news),
        output_dir=str(args.output_dir),
        seed=int(args.seed),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

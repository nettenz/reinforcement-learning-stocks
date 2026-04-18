#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from src.market_data import get_tech_training_data


EXCLUDE_COLS = {
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Stage 1 data health by ticker")
    parser.add_argument("--ticker", type=str, required=True, help="Ticker symbol, e.g. NVDA")
    parser.add_argument("--horizon", type=int, default=1, help="Forward return horizon in bars")
    parser.add_argument("--include-news", action="store_true", help="Include news features")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument(
        "--output-json",
        type=str,
        default="",
        help="Optional output JSON path (relative to repo root if not absolute)",
    )
    return parser.parse_args()


def to_numeric_series(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce")


def summarize_series(series: pd.Series) -> dict[str, float | int]:
    s = series.dropna()
    if s.empty:
        return {"n": 0, "mean": float("nan"), "std": float("nan"), "q05": float("nan"), "q95": float("nan")}
    return {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "std": float(s.std()),
        "q05": float(s.quantile(0.05)),
        "q95": float(s.quantile(0.95)),
    }


def standardized_mean_diff(a: pd.Series, b: pd.Series) -> float:
    a = a.dropna()
    b = b.dropna()
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    pooled = np.sqrt((a.var() + b.var()) / 2)
    if pooled == 0 or np.isnan(pooled):
        return 0.0
    return float(abs((a.mean() - b.mean()) / pooled))


def main() -> int:
    args = parse_args()

    ticker = args.ticker.upper().strip()
    frame = get_tech_training_data(
        tickers=[ticker],
        include_news=bool(args.include_news),
        use_stationary_features=True,
    ).sort_values("Date").reset_index(drop=True)

    if frame.empty:
        raise SystemExit(f"No data returned for ticker={ticker}")

    if "RawClose" in frame.columns:
        price_col = "RawClose"
    elif "Close" in frame.columns:
        price_col = "Close"
    else:
        raise SystemExit("No RawClose/Close column found")

    prices = to_numeric_series(frame, price_col)
    future_prices = prices.shift(-args.horizon)
    targets = np.log(future_prices / prices).replace([np.inf, -np.inf], np.nan)

    feature_cols = [c for c in frame.columns if c not in EXCLUDE_COLS]
    feature_matrix = frame[feature_cols].replace([np.inf, -np.inf], np.nan)
    feature_valid = np.all(np.isfinite(feature_matrix.to_numpy()), axis=1)
    target_valid = targets.notna().to_numpy()
    combined_valid = feature_valid & target_valid

    n = len(frame)
    train_end = int(n * args.train_ratio)
    val_end = train_end + int(n * args.val_ratio)

    idx = np.arange(n)
    split_masks = {
        "train": idx < train_end,
        "val": (idx >= train_end) & (idx < val_end),
        "test": idx >= val_end,
    }

    split_target_stats: dict[str, dict] = {}
    for split, mask in split_masks.items():
        split_series = pd.Series(targets[mask])
        split_target_stats[split] = {
            **summarize_series(split_series),
            "rows": int(mask.sum()),
            "valid_rows": int((mask & combined_valid).sum()),
            "valid_rate": float((mask & combined_valid).sum() / max(mask.sum(), 1)),
        }

    train_features = frame.iloc[:train_end][feature_cols]
    test_features = frame.iloc[val_end:][feature_cols]
    drift = []
    for col in feature_cols:
        smd = standardized_mean_diff(to_numeric_series(train_features, col), to_numeric_series(test_features, col))
        drift.append({"feature": col, "smd_abs": smd})
    drift = sorted(drift, key=lambda x: (np.nan_to_num(x["smd_abs"], nan=-1.0)), reverse=True)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "ticker": ticker,
        "horizon": int(args.horizon),
        "include_news": bool(args.include_news),
        "rows": int(n),
        "price_column": price_col,
        "price_valid_rows": int((prices.notna() & (prices > 0)).sum()),
        "feature_count": int(len(feature_cols)),
        "feature_valid_rows": int(feature_valid.sum()),
        "target_valid_rows": int(target_valid.sum()),
        "combined_valid_rows": int(combined_valid.sum()),
        "split_target_stats": split_target_stats,
        "top_feature_drift_train_vs_test": drift[:10],
    }

    print(f"Ticker: {ticker}")
    print(f"Rows: {report['rows']} | Price valid: {report['price_valid_rows']} | Combined valid: {report['combined_valid_rows']}")
    print("Split target stats:")
    for split, payload in split_target_stats.items():
        print(
            f"  {split}: n={payload['n']} mean={payload['mean']:.6f} std={payload['std']:.6f} "
            f"valid_rate={payload['valid_rate']:.3f}"
        )
    print("Top feature drift (train vs test, abs SMD):")
    for row in report["top_feature_drift_train_vs_test"][:5]:
        print(f"  {row['feature']}: {row['smd_abs']:.3f}")

    if args.output_json:
        out = Path(args.output_json)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

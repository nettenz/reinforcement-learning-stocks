#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"

import sys
sys.path.insert(0, str(ROOT))

from src.market_data import get_tech_training_data


DEFAULT_TICKERS = ("AAPL", "NVDA", "AMD")
DEFAULT_HORIZONS = (1, 3)
NEWS_COLUMNS = {
    "NewsCount",
    "SentimentMean",
    "SentimentStd",
    "SentimentMin",
    "SentimentMax",
    "SentimentConfidenceMean",
    "SentimentGeminiShare",
    "SentimentOllamaShare",
}


def parse_csv_values(raw: str, cast) -> list:
    values: list = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            values.append(cast(item))
    return values


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
    feature_cols = [col for col in df.columns if col not in exclude]
    if not include_news:
        feature_cols = [col for col in feature_cols if col not in NEWS_COLUMNS]
    return feature_cols


def compute_forward_log_return_targets(price_series: pd.Series, horizon: int) -> pd.Series:
    future_prices = price_series.shift(-horizon)
    targets = np.log(future_prices / price_series)
    targets = targets.replace([np.inf, -np.inf], np.nan)
    return targets


def leading_zero_run(matrix: np.ndarray) -> int:
    if matrix.size == 0:
        return 0
    zero_rows = np.all(np.isclose(matrix, 0.0), axis=1)
    run = 0
    for is_zero in zero_rows:
        if is_zero:
            run += 1
        else:
            break
    return run


def audit_ticker(ticker: str, horizons: Iterable[int], include_news: bool) -> dict:
    frame = get_tech_training_data(
        tickers=[ticker],
        include_news=include_news,
        use_stationary_features=True,
    )

    if frame.empty:
        raise ValueError(f"No data returned for {ticker}")

    if "RawClose" in frame.columns:
        price_col = "RawClose"
    elif "Close" in frame.columns:
        price_col = "Close"
    else:
        raise ValueError(f"No raw price column available for {ticker}")

    prices = pd.to_numeric(frame[price_col], errors="coerce")
    feature_cols = select_feature_columns(frame, include_news=include_news)
    feature_matrix = frame[feature_cols].replace([np.inf, -np.inf], np.nan).to_numpy()
    feature_valid = np.all(np.isfinite(feature_matrix), axis=1)
    zero_run = leading_zero_run(np.nan_to_num(feature_matrix, nan=0.0))

    report: dict = {
        "ticker": ticker,
        "rows": int(len(frame)),
        "price_column": price_col,
        "price_valid_rows": int((prices.notna() & (prices > 0)).sum()),
        "feature_count": int(len(feature_cols)),
        "feature_valid_rows": int(feature_valid.sum()),
        "leading_all_zero_feature_rows": int(zero_run),
        "horizons": {},
    }

    for horizon in horizons:
        targets = compute_forward_log_return_targets(prices, horizon=horizon)
        target_valid = targets.notna().to_numpy()
        combined_valid = feature_valid & target_valid

        n = len(frame)
        train_end = int(n * 0.70)
        val_end = train_end + int(n * 0.15)

        split_masks = {
            "train": np.arange(n) < train_end,
            "val": (np.arange(n) >= train_end) & (np.arange(n) < val_end),
            "test": np.arange(n) >= val_end,
        }

        split_counts = {}
        for split_name, mask in split_masks.items():
            split_counts[split_name] = {
                "rows": int(mask.sum()),
                "valid_rows": int((mask & combined_valid).sum()),
                "valid_rate": float((mask & combined_valid).sum() / max(mask.sum(), 1)),
            }

        report["horizons"][str(horizon)] = {
            "valid_target_rows": int(target_valid.sum()),
            "combined_valid_rows": int(combined_valid.sum()),
            "target_mean": float(targets.mean(skipna=True)),
            "target_std": float(targets.std(skipna=True)),
            "split_counts": split_counts,
        }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 completeness audit")
    parser.add_argument("--tickers", type=str, default=",".join(DEFAULT_TICKERS), help="Comma-separated ticker list")
    parser.add_argument("--horizons", type=str, default=",".join(str(h) for h in DEFAULT_HORIZONS), help="Comma-separated horizons")
    parser.add_argument("--include-news", action="store_true", help="Include news features in feature audit")
    parser.add_argument("--output", type=str, default=str(LOGS_DIR / "stage1_completeness_audit.json"), help="Output JSON path")
    args = parser.parse_args()

    tickers = parse_csv_values(args.tickers, str.upper)
    horizons = parse_csv_values(args.horizons, int)

    summaries = []
    for ticker in tickers:
        print(f"\n=== {ticker} ===")
        summary = audit_ticker(ticker, horizons=horizons, include_news=args.include_news)
        summaries.append(summary)

        print(f"Rows: {summary['rows']}")
        print(f"Price column: {summary['price_column']} ({summary['price_valid_rows']} valid)")
        print(f"Features: {summary['feature_count']} valid rows: {summary['feature_valid_rows']}")
        print(f"Leading all-zero feature rows: {summary['leading_all_zero_feature_rows']}")
        for horizon, payload in summary["horizons"].items():
            print(f"  Horizon {horizon}:")
            print(f"    Valid target rows: {payload['valid_target_rows']}")
            print(f"    Combined valid rows: {payload['combined_valid_rows']}")
            print(f"    Target mean/std: {payload['target_mean']:.8f} / {payload['target_std']:.8f}")
            for split_name, split_payload in payload["split_counts"].items():
                print(
                    f"    {split_name}: rows={split_payload['rows']}, valid={split_payload['valid_rows']}, rate={split_payload['valid_rate']:.3f}"
                )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "include_news": bool(args.include_news),
        "tickers": tickers,
        "horizons": horizons,
        "summaries": summaries,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nAudit written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

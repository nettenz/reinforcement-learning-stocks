from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf


TECH_TICKERS = ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA")


def fetch_yahoo_ohlcv(
    tickers: Iterable[str],
    start: str = "2018-01-01",
    end: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for ticker in tickers:
        try:
            history = yf.Ticker(ticker).history(
                start=start,
                end=end,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            continue

        if history.empty:
            continue

        frame = history.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
        frame["Ticker"] = ticker
        frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
        frames.append(frame)

    if not frames:
        detail = "; ".join(errors) if errors else "No rows returned for requested tickers."
        raise RuntimeError(f"Unable to fetch Yahoo Finance tech stock data. {detail}")

    return pd.concat(frames, ignore_index=True).sort_values(["Ticker", "Date"]).reset_index(drop=True)


def parse_and_normalize_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Missing required OHLCV fields: {sorted(missing)}")

    cleaned = data.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]).copy()
    cleaned["Volume"] = cleaned["Volume"].clip(lower=0)
    cleaned = cleaned.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    grouped = cleaned.groupby("Ticker", group_keys=False)
    previous_close = grouped["Close"].shift(1)

    cleaned["OpenNorm"] = (cleaned["Open"] / previous_close) - 1.0
    cleaned["HighNorm"] = (cleaned["High"] / cleaned["Close"]) - 1.0
    cleaned["LowNorm"] = (cleaned["Low"] / cleaned["Close"]) - 1.0
    cleaned["CloseNorm"] = grouped["Close"].pct_change()
    cleaned["VolumeNorm"] = grouped["Volume"].transform(lambda s: np.log1p(s).diff())

    norm_cols = ["OpenNorm", "HighNorm", "LowNorm", "CloseNorm", "VolumeNorm"]
    cleaned[norm_cols] = cleaned[norm_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return cleaned


def build_training_frame(normalized: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "OpenNorm", "HighNorm", "LowNorm", "CloseNorm", "VolumeNorm", "Close"}
    missing = required - set(normalized.columns)
    if missing:
        raise ValueError(f"Missing normalized fields: {sorted(missing)}")

    basket = (
        normalized.groupby("Date", as_index=False)
        .agg(
            Open=("OpenNorm", "mean"),
            High=("HighNorm", "mean"),
            Low=("LowNorm", "mean"),
            Close=("CloseNorm", "mean"),
            Volume=("VolumeNorm", "mean"),
            RawClose=("Close", "mean"),
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )

    return basket


def get_tech_training_data(
    cache_path: str | Path = "tech_training_data.csv",
    tickers: Iterable[str] = TECH_TICKERS,
    start: str = "2018-01-01",
    end: str | None = None,
    interval: str = "1d",
    refresh: bool = False,
) -> pd.DataFrame:
    cache_file = Path(cache_path)
    if cache_file.exists() and not refresh:
        data = pd.read_csv(cache_file, parse_dates=["Date"])
        return data

    raw = fetch_yahoo_ohlcv(tickers=tickers, start=start, end=end, interval=interval)
    normalized = parse_and_normalize_ohlcv(raw)
    training_data = build_training_frame(normalized)
    training_data.to_csv(cache_file, index=False)
    return training_data

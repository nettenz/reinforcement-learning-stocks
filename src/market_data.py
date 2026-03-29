from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf
from src.news_data import get_tech_news_features


TECH_TICKERS = ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA")
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
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


def merge_news_features(
    training_data: pd.DataFrame,
    news_features: pd.DataFrame,
) -> pd.DataFrame:
    required_training = {"Date"}
    missing_training = required_training - set(training_data.columns)
    if missing_training:
        raise ValueError(f"Training frame missing fields: {sorted(missing_training)}")

    required_news = {
        "Date",
        "NewsCount",
        "SentimentMean",
        "SentimentStd",
        "SentimentMin",
        "SentimentMax",
        "SentimentConfidenceMean",
        "SentimentGeminiShare",
        "SentimentOllamaShare",
    }
    missing_news = required_news - set(news_features.columns)
    if missing_news:
        raise ValueError(f"News frame missing fields: {sorted(missing_news)}")

    base_training = training_data.drop(columns=[c for c in NEWS_FEATURE_COLUMNS if c in training_data.columns]).copy()
    weighted = news_features.copy()
    weighted["WeightedSentiment"] = weighted["SentimentMean"] * weighted["NewsCount"]

    daily_news = (
        weighted.groupby("Date", as_index=False)
        .agg(
            NewsCount=("NewsCount", "sum"),
            WeightedSentiment=("WeightedSentiment", "sum"),
            SentimentStd=("SentimentStd", "mean"),
            SentimentMin=("SentimentMin", "min"),
            SentimentMax=("SentimentMax", "max"),
            SentimentConfidenceMean=("SentimentConfidenceMean", "mean"),
            SentimentGeminiShare=("SentimentGeminiShare", "mean"),
            SentimentOllamaShare=("SentimentOllamaShare", "mean"),
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )
    daily_news["SentimentMean"] = np.where(
        daily_news["NewsCount"] > 0,
        daily_news["WeightedSentiment"] / daily_news["NewsCount"],
        0.0,
    )
    daily_news = daily_news.drop(columns=["WeightedSentiment"])

    merged = base_training.merge(daily_news, on="Date", how="left")
    fill_values = {col: 0.0 for col in NEWS_FEATURE_COLUMNS}
    merged = merged.fillna(fill_values)
    return merged


def get_tech_training_data(
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    tickers: Iterable[str] = TECH_TICKERS,
    start: str = "2018-01-01",
    end: str | None = None,
    interval: str = "1d",
    include_news: bool = True,
    news_refresh: bool = False,
    refresh: bool = False,
) -> pd.DataFrame:
    cache_file = Path(cache_path)
    if cache_file.exists() and not refresh:
        data = pd.read_csv(cache_file, parse_dates=["Date"])
        if include_news and not set(NEWS_FEATURE_COLUMNS).issubset(data.columns):
            news_features = get_tech_news_features(tickers=tickers, refresh=news_refresh)
            data = merge_news_features(training_data=data, news_features=news_features)
            data.to_csv(cache_file, index=False)
        return data

    raw = fetch_yahoo_ohlcv(tickers=tickers, start=start, end=end, interval=interval)
    normalized = parse_and_normalize_ohlcv(raw)
    training_data = build_training_frame(normalized)
    if include_news:
        news_features = get_tech_news_features(tickers=tickers, refresh=news_refresh)
        training_data = merge_news_features(training_data=training_data, news_features=news_features)
    training_data.to_csv(cache_file, index=False)
    return training_data

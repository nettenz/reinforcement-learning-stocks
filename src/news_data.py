from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf


TECH_TICKERS = ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA")
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_NEWS_CACHE_PATH = ROOT_DIR / "data" / "tech_news_sentiment_data.csv"

POSITIVE_TERMS = {
    "beat",
    "beats",
    "surge",
    "surges",
    "growth",
    "upgrade",
    "upgraded",
    "bullish",
    "strong",
    "record",
    "profit",
    "profits",
    "outperform",
    "outperformed",
    "rally",
    "rallies",
}

NEGATIVE_TERMS = {
    "miss",
    "misses",
    "drop",
    "drops",
    "downgrade",
    "downgraded",
    "bearish",
    "weak",
    "loss",
    "losses",
    "lawsuit",
    "risk",
    "risks",
    "plunge",
    "plunges",
    "decline",
    "declines",
}


def _to_datetime_utc(value: object) -> pd.Timestamp | pd.NaT:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts


def _score_text_sentiment(text: str) -> float:
    tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in text.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0.0

    pos_hits = sum(1 for t in tokens if t in POSITIVE_TERMS)
    neg_hits = sum(1 for t in tokens if t in NEGATIVE_TERMS)
    raw = (pos_hits - neg_hits) / max(len(tokens), 1)

    if raw > 1.0:
        return 1.0
    if raw < -1.0:
        return -1.0
    return float(raw)


def fetch_yahoo_news(
    tickers: Iterable[str] = TECH_TICKERS,
    max_articles_per_ticker: int = 50,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    errors: list[str] = []

    for ticker in tickers:
        try:
            raw_news = yf.Ticker(ticker).news
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            continue

        if not raw_news:
            continue

        for item in raw_news[:max_articles_per_ticker]:
            content = item.get("content") if isinstance(item, dict) else {}
            title = ""
            summary = ""
            published_at: object = None
            source = None
            link = None

            if isinstance(content, dict):
                title = str(content.get("title") or "")
                summary = str(content.get("summary") or "")
                published_at = content.get("pubDate") or content.get("displayTime")
                source = content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else None
                link = content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else None
            else:
                title = str(item.get("title") or "")
                summary = str(item.get("summary") or "")
                published_at = item.get("providerPublishTime")
                source = item.get("publisher")
                link = item.get("link")

            text = f"{title} {summary}".strip()
            rows.append(
                {
                    "Ticker": ticker,
                    "PublishedAt": _to_datetime_utc(published_at),
                    "Title": title,
                    "Summary": summary,
                    "Source": source,
                    "Link": link,
                    "SentimentScore": _score_text_sentiment(text),
                }
            )

    if not rows:
        detail = "; ".join(errors) if errors else "No news entries returned by Yahoo Finance."
        raise RuntimeError(f"Unable to fetch ticker news. {detail}")

    frame = pd.DataFrame(rows)
    frame = frame.dropna(subset=["PublishedAt"]).copy()
    frame["Date"] = frame["PublishedAt"].dt.tz_convert(None).dt.normalize()
    return frame.sort_values(["Ticker", "PublishedAt"]).reset_index(drop=True)


def aggregate_daily_news_features(news_df: pd.DataFrame) -> pd.DataFrame:
    required = {"Ticker", "Date", "SentimentScore"}
    missing = required - set(news_df.columns)
    if missing:
        raise ValueError(f"Missing required news fields: {sorted(missing)}")

    features = (
        news_df.groupby(["Ticker", "Date"], as_index=False)
        .agg(
            NewsCount=("SentimentScore", "count"),
            SentimentMean=("SentimentScore", "mean"),
            SentimentStd=("SentimentScore", "std"),
            SentimentMin=("SentimentScore", "min"),
            SentimentMax=("SentimentScore", "max"),
        )
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )
    features["SentimentStd"] = features["SentimentStd"].fillna(0.0)
    return features


def get_tech_news_features(
    cache_path: str | Path = DEFAULT_NEWS_CACHE_PATH,
    tickers: Iterable[str] = TECH_TICKERS,
    max_articles_per_ticker: int = 50,
    refresh: bool = False,
) -> pd.DataFrame:
    cache_file = Path(cache_path)
    if cache_file.exists() and not refresh:
        return pd.read_csv(cache_file, parse_dates=["Date"])

    news = fetch_yahoo_news(tickers=tickers, max_articles_per_ticker=max_articles_per_ticker)
    features = aggregate_daily_news_features(news)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(cache_file, index=False)
    return features


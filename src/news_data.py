from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable
from urllib import error, request

import pandas as pd
import yfinance as yf


TECH_TICKERS = ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA")
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_NEWS_CACHE_PATH = ROOT_DIR / "data" / "tech_news_sentiment_data.csv"
DEFAULT_SENTIMENT_CACHE_PATH = ROOT_DIR / "data" / "news_sentiment_llm_cache.csv"
DEFAULT_SENTIMENT_PROVIDER = "hybrid"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

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


@dataclass(frozen=True)
class SentimentResult:
    score: float
    confidence: float
    provider: str
    model: str


def _to_datetime_utc(value: object) -> pd.Timestamp | pd.NaT:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts


def _clamp(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


def _article_key(ticker: str, title: str, summary: str, source: str | None, link: str | None, published_at: object) -> str:
    raw = "|".join(
        [
            ticker.strip().upper(),
            str(title or "").strip().lower(),
            str(summary or "").strip().lower(),
            str(source or "").strip().lower(),
            str(link or "").strip().lower(),
            str(published_at or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_sentiment_cache(path: Path) -> dict[str, SentimentResult]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    required = {"ArticleKey", "SentimentScore", "SentimentConfidence", "SentimentProvider", "SentimentModel"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Sentiment cache is missing columns: {sorted(missing)}")
    cache: dict[str, SentimentResult] = {}
    for row in frame.itertuples(index=False):
        cache[str(row.ArticleKey)] = SentimentResult(
            score=_clamp(float(row.SentimentScore), -1.0, 1.0),
            confidence=_clamp(float(row.SentimentConfidence), 0.0, 1.0),
            provider=str(row.SentimentProvider),
            model=str(row.SentimentModel),
        )
    return cache


def _append_sentiment_cache(path: Path, article_key: str, result: SentimentResult) -> None:
    row = pd.DataFrame(
        [
            {
                "ArticleKey": article_key,
                "SentimentScore": result.score,
                "SentimentConfidence": result.confidence,
                "SentimentProvider": result.provider,
                "SentimentModel": result.model,
                "CachedAtUTC": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    row.to_csv(path, mode="a", header=not exists, index=False)


def _score_text_sentiment(text: str) -> SentimentResult:
    tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in text.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return SentimentResult(score=0.0, confidence=0.0, provider="heuristic", model="lexicon-v1")

    pos_hits = sum(1 for t in tokens if t in POSITIVE_TERMS)
    neg_hits = sum(1 for t in tokens if t in NEGATIVE_TERMS)
    raw = (pos_hits - neg_hits) / max(len(tokens), 1)
    confidence = min(1.0, (pos_hits + neg_hits) / max(len(tokens) * 0.2, 1.0))
    return SentimentResult(score=_clamp(raw, -1.0, 1.0), confidence=float(confidence), provider="heuristic", model="lexicon-v1")


def _http_json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None, timeout_seconds: int = 30) -> dict[str, object]:
    raw = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=raw, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach {url}: {exc.reason}") from exc
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}: {body[:300]}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"Unexpected response payload from {url}: {type(decoded)}")
    return decoded


def _llm_prompt(text: str) -> str:
    return (
        "You are a financial sentiment classifier.\n"
        "Return strict JSON only with keys: score, confidence.\n"
        "score must be a float in [-1, 1] where -1 is very bearish and 1 is very bullish.\n"
        "confidence must be a float in [0, 1].\n"
        f"Text: {text}"
    )


def _score_with_ollama(text: str) -> SentimentResult:
    url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    payload = {
        "model": model,
        "prompt": _llm_prompt(text),
        "stream": False,
        "format": "json",
    }
    response = _http_json_post(url=url, payload=payload)
    raw_response = response.get("response")
    if not isinstance(raw_response, str):
        raise RuntimeError("Ollama response missing 'response' string field.")
    parsed = json.loads(raw_response)
    return SentimentResult(
        score=_clamp(float(parsed["score"]), -1.0, 1.0),
        confidence=_clamp(float(parsed["confidence"]), 0.0, 1.0),
        provider="ollama",
        model=model,
    )


def _score_with_gemini(text: str) -> SentimentResult:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _llm_prompt(text)},
                ]
            }
        ]
    }
    response = _http_json_post(url=url, payload=payload)
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini response missing candidates.")
    first = candidates[0]
    content = first.get("content", {})
    parts = content.get("parts", [])
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Gemini response missing content parts.")
    generated_text = parts[0].get("text")
    if not isinstance(generated_text, str):
        raise RuntimeError("Gemini content part is missing text.")
    parsed = json.loads(generated_text)
    return SentimentResult(
        score=_clamp(float(parsed["score"]), -1.0, 1.0),
        confidence=_clamp(float(parsed["confidence"]), 0.0, 1.0),
        provider="gemini",
        model=model,
    )


def _score_article_sentiment(text: str) -> SentimentResult:
    provider = os.getenv("NEWS_SENTIMENT_PROVIDER", DEFAULT_SENTIMENT_PROVIDER).strip().lower()
    if provider == "heuristic":
        return _score_text_sentiment(text)
    if provider == "ollama":
        return _score_with_ollama(text)
    if provider == "gemini":
        return _score_with_gemini(text)
    if provider != "hybrid":
        raise ValueError("NEWS_SENTIMENT_PROVIDER must be one of: heuristic, ollama, gemini, hybrid")

    errors: list[str] = []
    try:
        ollama_result = _score_with_ollama(text)
        if ollama_result.confidence >= 0.65:
            return ollama_result
        try:
            return _score_with_gemini(text)
        except Exception as exc:
            errors.append(f"gemini fallback failed: {exc}")
            return ollama_result
    except Exception as exc:
        errors.append(f"ollama failed: {exc}")
        try:
            return _score_with_gemini(text)
        except Exception as gemini_exc:
            errors.append(f"gemini failed: {gemini_exc}")
            heuristic = _score_text_sentiment(text)
            return SentimentResult(
                score=heuristic.score,
                confidence=heuristic.confidence,
                provider="heuristic-fallback",
                model=heuristic.model,
            )


def fetch_yahoo_news(
    tickers: Iterable[str] = TECH_TICKERS,
    max_articles_per_ticker: int = 50,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    sentiment_cache_path = DEFAULT_SENTIMENT_CACHE_PATH
    sentiment_cache = _load_sentiment_cache(sentiment_cache_path)

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
            article_key = _article_key(
                ticker=ticker,
                title=title,
                summary=summary,
                source=source,
                link=link,
                published_at=published_at,
            )
            sentiment = sentiment_cache.get(article_key)
            if sentiment is None:
                sentiment = _score_article_sentiment(text)
                sentiment_cache[article_key] = sentiment
                _append_sentiment_cache(sentiment_cache_path, article_key=article_key, result=sentiment)
            rows.append(
                {
                    "Ticker": ticker,
                    "PublishedAt": _to_datetime_utc(published_at),
                    "Title": title,
                    "Summary": summary,
                    "Source": source,
                    "Link": link,
                    "SentimentScore": sentiment.score,
                    "SentimentConfidence": sentiment.confidence,
                    "SentimentProvider": sentiment.provider,
                    "SentimentModel": sentiment.model,
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
    required = {"Ticker", "Date", "SentimentScore", "SentimentConfidence", "SentimentProvider"}
    missing = required - set(news_df.columns)
    if missing:
        raise ValueError(f"Missing required news fields: {sorted(missing)}")

    working = news_df.copy()
    working["IsGemini"] = (working["SentimentProvider"] == "gemini").astype(float)
    working["IsOllama"] = (working["SentimentProvider"] == "ollama").astype(float)
    features = (
        working.groupby(["Ticker", "Date"], as_index=False)
        .agg(
            NewsCount=("SentimentScore", "count"),
            SentimentMean=("SentimentScore", "mean"),
            SentimentStd=("SentimentScore", "std"),
            SentimentMin=("SentimentScore", "min"),
            SentimentMax=("SentimentScore", "max"),
            SentimentConfidenceMean=("SentimentConfidence", "mean"),
            SentimentGeminiShare=("IsGemini", "mean"),
            SentimentOllamaShare=("IsOllama", "mean"),
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
        cached = pd.read_csv(cache_file, parse_dates=["Date"])
        if "SentimentConfidenceMean" not in cached.columns:
            cached["SentimentConfidenceMean"] = 0.0
        if "SentimentGeminiShare" not in cached.columns:
            cached["SentimentGeminiShare"] = 0.0
        if "SentimentOllamaShare" not in cached.columns:
            cached["SentimentOllamaShare"] = 0.0
        return cached

    news = fetch_yahoo_news(tickers=tickers, max_articles_per_ticker=max_articles_per_ticker)
    features = aggregate_daily_news_features(news)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(cache_file, index=False)
    return features


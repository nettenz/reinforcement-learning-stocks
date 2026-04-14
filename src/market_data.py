from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
from src.news_data import get_tech_news_features
from src.feature_engineering import compute_stationary_features


ROOT_DIR = Path(__file__).resolve().parents[1]
TECH_TICKERS = ("AAPL",)  # Single stock for realistic transaction costs
DEFAULT_CACHE_PATH = ROOT_DIR / "data" / "tech_training_data.parquet"
STATIONARY_CACHE_PATH = ROOT_DIR / "data" / "tech_training_data_stationary.parquet"


def normalize_interval_key(interval: str) -> str:
    return str(interval).strip().lower()


def interval_slug(interval: str) -> str:
    return normalize_interval_key(interval).replace(" ", "")


def is_intraday_interval(interval: str) -> bool:
    return normalize_interval_key(interval) not in {"1d", "1day", "daily"}


def get_interval_bars_per_year(interval: str) -> int:
    interval_key = normalize_interval_key(interval)
    if interval_key in {"1d", "1day", "daily"}:
        return 252

    match = re.fullmatch(r"(\d+)([mh])", interval_key)
    if not match:
        return 252

    amount = max(int(match.group(1)), 1)
    unit = match.group(2)
    minutes = amount if unit == "m" else amount * 60
    trading_minutes_per_day = 390
    trading_days_per_year = 252
    return max(int(round((trading_minutes_per_day * trading_days_per_year) / minutes)), 1)

# Ticker presets for different training scenarios
TICKER_PRESETS = {
    "aapl": ("AAPL",),
    "nvda": ("NVDA",),
    "amd": ("AMD",),
    "msft": ("MSFT",),
}
DEFAULT_TICKER = "aapl"


def get_cache_path_for_ticker(ticker_name: str, stationary: bool = False, interval: str = "1d") -> Path:
    """Generate cache path for a specific ticker."""
    ticker_key = ticker_name.lower()
    if ticker_key not in TICKER_PRESETS:
        raise ValueError(f"Unknown ticker preset: {ticker_name}. Available: {list(TICKER_PRESETS.keys())}")

    suffix = "_stationary" if stationary else ""
    interval_key = normalize_interval_key(interval)
    if interval_key in {"1d", "1day", "daily"}:
        cache_file = f"tech_training_data_{ticker_key}{suffix}.parquet"
    else:
        cache_file = f"tech_training_data_{ticker_key}_{interval_slug(interval_key)}{suffix}.parquet"
    return ROOT_DIR / "data" / cache_file


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


def _warn_intraday_gap_ratio(df: pd.DataFrame, interval: str) -> None:
    if not is_intraday_interval(interval) or len(df) < 10:
        return
    diffs = df["Date"].diff().dropna()
    if diffs.empty:
        return
    median_delta = diffs.median()
    if pd.isna(median_delta) or median_delta <= pd.Timedelta(0):
        return
    # Large jumps versus typical step often indicate missing intraday bars.
    gap_mask = diffs > (median_delta * 3)
    gap_ratio = float(gap_mask.mean())
    if gap_ratio > 0.10:
        warnings.warn(
            f"Intraday gap ratio is high ({gap_ratio:.1%}) for interval={interval}; results may be unstable.",
            RuntimeWarning,
            stacklevel=2,
        )


def _validate_training_data_quality(df: pd.DataFrame, interval: str, enforce_min_rows: bool = True) -> None:
    if "Date" not in df.columns:
        raise ValueError("Training data quality check failed: missing Date column.")

    if df["Date"].isna().any():
        raise ValueError("Training data quality check failed: Date column contains null values.")

    if not df["Date"].is_monotonic_increasing:
        raise ValueError("Training data quality check failed: Date is not sorted ascending.")

    duplicate_count = int(df["Date"].duplicated().sum())
    if duplicate_count > 0:
        raise ValueError(f"Training data quality check failed: duplicate Date rows detected ({duplicate_count}).")

    if enforce_min_rows:
        min_rows = 1000 if is_intraday_interval(interval) else 200
        if len(df) < min_rows:
            raise ValueError(
                f"Training data quality check failed: insufficient rows ({len(df)} < {min_rows}) for interval={interval}."
            )

    numeric_cols = [col for col in df.columns if col != "Date" and pd.api.types.is_numeric_dtype(df[col])]
    if not numeric_cols:
        raise ValueError("Training data quality check failed: no numeric columns found.")

    numeric = df[numeric_cols]
    bad_nan = numeric.isna().sum()
    bad_nan = bad_nan[bad_nan > 0]
    if not bad_nan.empty:
        top = ", ".join([f"{col}:{int(cnt)}" for col, cnt in bad_nan.sort_values(ascending=False).head(5).items()])
        raise ValueError(f"Training data quality check failed: NaN values in numeric columns ({top}).")

    values = numeric.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Training data quality check failed: non-finite numeric values (inf/-inf) detected.")

    _warn_intraday_gap_ratio(df, interval=interval)


def _interval_to_timedelta(interval: str) -> pd.Timedelta:
    key = normalize_interval_key(interval)
    match = re.fullmatch(r"(\d+)([mh])", key)
    if not match:
        return pd.Timedelta(days=1)
    amount = max(int(match.group(1)), 1)
    unit = match.group(2)
    if unit == "m":
        return pd.Timedelta(minutes=amount)
    return pd.Timedelta(hours=amount)


def _intraday_cache_needs_topup(df: pd.DataFrame, interval: str, end: str | None = None) -> bool:
    if df.empty or "Date" not in df.columns:
        return True
    latest = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(latest):
        return True
    if end is not None:
        target_end = pd.to_datetime(end, errors="coerce")
    else:
        target_end = pd.Timestamp.now(tz="UTC").tz_localize(None)
    if pd.isna(target_end):
        return True
    lag = target_end - latest
    return lag > (_interval_to_timedelta(interval) * 3)


def _build_training_data_from_raw(
    raw: pd.DataFrame,
    interval: str,
    include_news: bool,
    news_refresh: bool,
    tickers: Iterable[str],
    use_stationary_features: bool,
    enforce_min_rows: bool = True,
) -> pd.DataFrame:
    normalized = parse_and_normalize_ohlcv(raw)
    base_training = build_training_frame(normalized)

    indicators = compute_stationary_features(base_training)

    if use_stationary_features:
        training_data = indicators.copy()
        training_data["RawClose"] = base_training["RawClose"]
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            training_data[f"Orig{col}"] = base_training[col]
    else:
        indic_cols = indicators.drop(columns=["Date"], errors="ignore")
        training_data = pd.concat([base_training.reset_index(drop=True), indic_cols.reset_index(drop=True)], axis=1)

    if include_news:
        if is_intraday_interval(interval):
            warnings.warn(
                "Intraday interval with daily news features aligns news by session date and may introduce timing risk.",
                RuntimeWarning,
                stacklevel=2,
            )
        news_features = get_tech_news_features(tickers=tickers, refresh=news_refresh)
        training_data = merge_news_features(training_data=training_data, news_features=news_features)

    training_data = training_data.sort_values("Date").reset_index(drop=True)
    _validate_training_data_quality(training_data, interval=interval, enforce_min_rows=enforce_min_rows)
    return training_data


def _write_topup_metadata(cache_file: Path, rows_before: int, rows_after: int, rows_added: int, start: pd.Timestamp, end: pd.Timestamp) -> None:
    try:
        meta = {
            "cache_file": str(cache_file),
            "rows_before": int(rows_before),
            "rows_after": int(rows_after),
            "rows_added": int(rows_added),
            "start": str(start),
            "end": str(end),
            "updated_at_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        meta_file = cache_file.with_suffix(cache_file.suffix + ".meta.json")
        meta_file.write_text(pd.Series(meta).to_json(indent=2), encoding="utf-8")
    except Exception:
        # Metadata is optional; never fail main data path.
        pass


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

        history = history.reset_index()
        date_column = next((candidate for candidate in ("Date", "Datetime", "index") if candidate in history.columns), history.columns[0])
        frame = history[[date_column, "Open", "High", "Low", "Close", "Volume"]].rename(columns={date_column: "Date"})
        frame["Ticker"] = ticker
        frame["Date"] = pd.to_datetime(frame["Date"])
        if getattr(frame["Date"].dt, "tz", None) is not None:
            frame["Date"] = frame["Date"].dt.tz_localize(None)
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
    
    # Compute VolumeNorm using an explicit numeric path to avoid pandas warning noise.
    def _volume_log_diff(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce").fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
        if values.size == 0:
            return pd.Series(dtype=float, index=series.index)
        logged = np.log1p(values)
        diffs = np.diff(logged, prepend=logged[0])
        return pd.Series(diffs, index=series.index)

    cleaned["VolumeNorm"] = grouped["Volume"].transform(_volume_log_diff)

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
    date_column: str = "Date",
) -> pd.DataFrame:
    required_training = {date_column}
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
    merge_key = "__merge_date"
    base_training[merge_key] = pd.to_datetime(base_training[date_column]).dt.normalize()
    weighted[merge_key] = pd.to_datetime(weighted[date_column]).dt.normalize()
    weighted["WeightedSentiment"] = weighted["SentimentMean"] * weighted["NewsCount"]

    daily_news = (
        weighted.groupby(merge_key, as_index=False)
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

    merged = base_training.merge(daily_news, on=merge_key, how="left")
    merged = merged.drop(columns=[merge_key])
    fill_values = {col: 0.0 for col in NEWS_FEATURE_COLUMNS}
    merged = merged.fillna(fill_values)
    return merged


def get_tech_training_data(
    cache_path: str | Path | None = None,
    tickers: Iterable[str] | None = None,
    ticker_preset: str | None = None,
    start: str = "2018-01-01",
    end: str | None = None,
    interval: str = "1d",
    include_news: bool = True,
    news_refresh: bool = False,
    refresh: bool = False,
    use_stationary_features: bool = False,
) -> pd.DataFrame:
    effective_start = start
    intraday_default_start = is_intraday_interval(interval) and start == "2018-01-01"
    if intraday_default_start:
        effective_start = (pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.Timedelta(days=55)).strftime("%Y-%m-%d")

    # Resolve ticker: prefer explicit tickers, then preset, then default
    if tickers is None:
        if ticker_preset is None:
            ticker_preset = DEFAULT_TICKER
        if isinstance(ticker_preset, str):
            ticker_key = ticker_preset.lower()
            if ticker_key not in TICKER_PRESETS:
                raise ValueError(f"Unknown ticker preset: {ticker_preset}. Available: {list(TICKER_PRESETS.keys())}")
            tickers = TICKER_PRESETS[ticker_key]
        else:
            tickers = ticker_preset
    
    # Auto-generate cache path if not provided
    if cache_path is None:
        # Try to infer ticker for cache naming
        ticker_str = tickers[0] if isinstance(tickers, (tuple, list)) else str(tickers)
        ticker_key = ticker_str.lower()
        if ticker_key in TICKER_PRESETS:
            cache_path = get_cache_path_for_ticker(ticker_key, stationary=use_stationary_features, interval=interval)
        else:
            cache_path = STATIONARY_CACHE_PATH if use_stationary_features else DEFAULT_CACHE_PATH
    
    cache_file = Path(cache_path)
    if cache_file.exists() and not refresh:
        data = pd.read_parquet(cache_file)
        # If cache exists but missing news columns, merge them
        if include_news and not set(NEWS_FEATURE_COLUMNS).issubset(data.columns):
            news_features = get_tech_news_features(tickers=tickers, refresh=news_refresh)
            data = merge_news_features(training_data=data, news_features=news_features)
            data = data.sort_values("Date").reset_index(drop=True)
            _validate_training_data_quality(data, interval=interval)
            data.to_parquet(cache_file, index=False)
        else:
            data = data.sort_values("Date").reset_index(drop=True)
            _validate_training_data_quality(data, interval=interval)

        # Intraday top-up: extend stale cache using a small overlap window and preserve older local history.
        if is_intraday_interval(interval) and _intraday_cache_needs_topup(data, interval=interval, end=end):
            rows_before = len(data)
            latest_cached = pd.to_datetime(data["Date"], errors="coerce").max()
            if not pd.isna(latest_cached):
                overlap_start = (latest_cached - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
                try:
                    raw_topup = fetch_yahoo_ohlcv(tickers=tickers, start=overlap_start, end=end, interval=interval)
                    topup_data = _build_training_data_from_raw(
                        raw=raw_topup,
                        interval=interval,
                        include_news=include_news,
                        news_refresh=news_refresh,
                        tickers=tickers,
                        use_stationary_features=use_stationary_features,
                        enforce_min_rows=False,
                    )
                    topup_min_date = pd.to_datetime(topup_data["Date"], errors="coerce").min()
                    preserved = data[pd.to_datetime(data["Date"], errors="coerce") < topup_min_date].copy()
                    merged = (
                        pd.concat([preserved, topup_data], ignore_index=True)
                        .sort_values("Date")
                        .drop_duplicates(subset=["Date"], keep="last")
                        .reset_index(drop=True)
                    )
                    _validate_training_data_quality(merged, interval=interval)
                    rows_after = len(merged)
                    rows_added = rows_after - rows_before
                    data = merged
                    data.to_parquet(cache_file, index=False)
                    _write_topup_metadata(
                        cache_file=cache_file,
                        rows_before=rows_before,
                        rows_after=rows_after,
                        rows_added=rows_added,
                        start=pd.to_datetime(data["Date"], errors="coerce").min(),
                        end=pd.to_datetime(data["Date"], errors="coerce").max(),
                    )
                    warnings.warn(
                        f"Intraday cache top-up complete for interval={interval}: rows_before={rows_before}, rows_after={rows_after}, rows_added={rows_added}.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                except Exception as exc:
                    warnings.warn(
                        f"Intraday cache top-up skipped due to fetch/merge issue: {exc}",
                        RuntimeWarning,
                        stacklevel=2,
                    )
        return data

    if intraday_default_start:
        warnings.warn(
            f"Intraday interval {interval} is limited to a recent lookback window; using start={effective_start}.",
            RuntimeWarning,
            stacklevel=2,
        )

    raw = fetch_yahoo_ohlcv(tickers=tickers, start=effective_start, end=end, interval=interval)
    training_data = _build_training_data_from_raw(
        raw=raw,
        interval=interval,
        include_news=include_news,
        news_refresh=news_refresh,
        tickers=tickers,
        use_stationary_features=use_stationary_features,
    )
    
    training_data.to_parquet(cache_file, index=False)
    return training_data

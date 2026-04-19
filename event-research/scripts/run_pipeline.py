from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


DEFAULT_ROOT = Path(__file__).resolve().parents[1]

POSITIVE_TERMS = {
    "beat",
    "beats",
    "growth",
    "higher",
    "improves",
    "improving",
    "outperform",
    "rally",
    "resilient",
    "rise",
    "rises",
    "strong",
    "upgrade",
    "upgraded",
}
NEGATIVE_TERMS = {
    "decline",
    "declines",
    "downgrade",
    "downgraded",
    "fell",
    "loss",
    "miss",
    "misses",
    "risk",
    "risks",
    "slip",
    "slips",
    "weak",
}


def _python_type_for_schema(schema_type: str):
    if schema_type == "string":
        return str
    if schema_type == "number":
        return (int, float)
    if schema_type == "integer":
        return int
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list
    if schema_type == "object":
        return dict
    return object


def _validate_with_simple_schema(record: object, schema: dict[str, object], label: str, idx: int) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"Schema validation failed for {label}[{idx}]: record is not an object")

    required = schema.get("required", [])
    if isinstance(required, list):
        for key in required:
            if key not in record:
                raise ValueError(f"Schema validation failed for {label}[{idx}]: missing required key '{key}'")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return

    for key, rule in properties.items():
        if key not in record:
            continue
        if not isinstance(rule, dict):
            continue
        value = record[key]
        schema_type = rule.get("type")
        if isinstance(schema_type, list):
            allowed = []
            for item in schema_type:
                if item == "null":
                    allowed.append(type(None))
                elif isinstance(item, str):
                    allowed.append(_python_type_for_schema(item))
            if allowed and not isinstance(value, tuple(allowed)):
                raise ValueError(f"Schema validation failed for {label}[{idx}].{key}: unexpected type")
        elif isinstance(schema_type, str):
            if schema_type == "null":
                if value is not None:
                    raise ValueError(f"Schema validation failed for {label}[{idx}].{key}: expected null")
            else:
                py_type = _python_type_for_schema(schema_type)
                if py_type is not object and not isinstance(value, py_type):
                    raise ValueError(f"Schema validation failed for {label}[{idx}].{key}: unexpected type")

        enum_values = rule.get("enum")
        if isinstance(enum_values, list) and value not in enum_values:
            raise ValueError(f"Schema validation failed for {label}[{idx}].{key}: value not in enum")

        if rule.get("type") == "array":
            item_rule = rule.get("items")
            if isinstance(item_rule, dict) and isinstance(value, list):
                item_type = item_rule.get("type")
                if isinstance(item_type, str):
                    item_py_type = _python_type_for_schema(item_type)
                    for item_idx, item in enumerate(value):
                        if item_py_type is not object and not isinstance(item, item_py_type):
                            raise ValueError(
                                f"Schema validation failed for {label}[{idx}].{key}[{item_idx}]: unexpected type"
                            )


def validate_records(root: Path, schema_name: str, records: list[dict[str, object]], label: str) -> None:
    schema_path = root / "schemas" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft202012Validator(schema)
        for idx, record in enumerate(records):
            errors = sorted(validator.iter_errors(record), key=lambda err: list(err.path))
            if errors:
                first = errors[0]
                path = ".".join(str(part) for part in first.path) if first.path else "<root>"
                raise ValueError(f"Schema validation failed for {label}[{idx}] at {path}: {first.message}")
    except ModuleNotFoundError:
        for idx, record in enumerate(records):
            _validate_with_simple_schema(record, schema, label=label, idx=idx)


def load_simple_yaml(path: Path) -> dict[str, object]:
    """Small YAML reader for the starter configs used here."""
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
            return loaded or {}
    except ModuleNotFoundError:
        pass

    result: dict[str, object] = {}
    current_list: list[str] | None = None
    current_map: dict[str, str] | None = None
    current_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        if not raw_line.startswith(" ") and line.endswith(":"):
            current_key = line[:-1]
            current_list = []
            current_map = {}
            result[current_key] = current_list
            continue
        if current_key and line.strip().startswith("- "):
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(line.strip()[2:].strip("\"'"))
            continue
        if current_key and ":" in line and raw_line.startswith("  "):
            if current_map is None:
                current_map = {}
            if not isinstance(result.get(current_key), dict):
                result[current_key] = current_map
            key, value = line.strip().split(":", 1)
            current_map[key.strip()] = value.strip().strip("\"'")
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip("\"'")
            current_key = None
    return result


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def normalized_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def parse_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def parse_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def assign_market_session(published_at_utc: pd.Timestamp, sessions: dict[str, object]) -> str:
    market_tz = ZoneInfo(str(sessions.get("market_timezone", "America/New_York")))
    local_ts = published_at_utc.tz_convert(market_tz)
    if local_ts.weekday() >= 5:
        return "closed"

    local_time = local_ts.time()
    pre_start = parse_time(str(sessions.get("pre_market_start", "04:00")))
    regular_open = parse_time(str(sessions.get("regular_open", "09:30")))
    regular_close = parse_time(str(sessions.get("regular_close", "16:00")))
    after_end = parse_time(str(sessions.get("after_hours_end", "20:00")))

    if pre_start <= local_time < regular_open:
        return "pre_market"
    if regular_open <= local_time < regular_close:
        return "regular"
    if regular_close <= local_time < after_end:
        return "after_hours"
    return "closed"


def load_aliases(root: Path, ticker_config: dict[str, object]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    configured_aliases = ticker_config.get("aliases")
    if isinstance(configured_aliases, dict):
        for key, value in configured_aliases.items():
            aliases[str(key).upper()] = str(value).upper()

    ticker_map = root / "data" / "raw" / "reference" / "ticker_map.csv"
    if ticker_map.exists():
        with ticker_map.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = str(row["raw_ticker"]).upper()
                mapped = str(row["ticker"]).upper()
                aliases.setdefault(raw, mapped)
    return aliases


def normalize_tickers(values: object, aliases: dict[str, str], universe: set[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        ticker = aliases.get(str(value).strip().upper(), str(value).strip().upper())
        if ticker in universe and ticker not in normalized:
            normalized.append(ticker)
    return normalized


def normalize_news(root: Path, raw_rows: list[dict[str, object]]) -> pd.DataFrame:
    sessions = load_simple_yaml(root / "config" / "sessions.yaml")
    ticker_config = load_simple_yaml(root / "config" / "tickers.yaml")
    universe = set(ticker_config.get("universe", ["AAPL", "AMD", "NVDA", "QQQ", "SPY"]))
    aliases = load_aliases(root, ticker_config=ticker_config)

    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        published_at = pd.to_datetime(raw.get("published_at_raw"), errors="coerce", utc=True)
        if pd.isna(published_at):
            continue
        tickers = normalize_tickers(raw.get("tickers_raw"), aliases=aliases, universe=universe)
        headline = str(raw.get("headline") or "").strip()
        date_bucket = published_at.strftime("%Y-%m-%d")
        dedupe_hash = stable_id("dedupe", normalized_text(headline), date_bucket, ",".join(tickers))
        news_id = stable_id("news", raw.get("source_record_id"), raw.get("source_name"), published_at.isoformat(), headline)
        rows.append(
            {
                "news_id": news_id,
                "source_name": str(raw.get("source_name") or "unknown"),
                "published_at_utc": published_at.isoformat(),
                "headline": headline,
                "summary": raw.get("summary"),
                "body": raw.get("body"),
                "url": raw.get("url"),
                "tickers": tickers,
                "primary_ticker": tickers[0] if tickers else None,
                "market_session": assign_market_session(published_at, sessions),
                "dedupe_hash": dedupe_hash,
                "is_duplicate": False,
                "language": raw.get("language"),
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["is_duplicate"] = frame.duplicated("dedupe_hash", keep="first")
    return frame


def score_sentiment(text: str) -> tuple[float, str, float]:
    tokens = [token.strip(".,:;!?()[]{}\"'").lower() for token in text.split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        return 0.0, "neutral", 0.0
    pos_hits = sum(token in POSITIVE_TERMS for token in tokens)
    neg_hits = sum(token in NEGATIVE_TERMS for token in tokens)
    score = max(min((pos_hits - neg_hits) / max(len(tokens), 1), 1.0), -1.0)
    confidence = min((pos_hits + neg_hits) / max(len(tokens) * 0.2, 1.0), 1.0)
    if score > 0.01:
        label = "positive"
    elif score < -0.01:
        label = "negative"
    else:
        label = "neutral"
    return float(score), label, float(confidence)


def build_event_table(normalized: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in normalized.itertuples(index=False):
        if bool(row.is_duplicate):
            continue
        text = f"{row.headline or ''} {row.summary or ''}".strip()
        score, label, confidence = score_sentiment(text)
        for ticker in row.tickers:
            rows.append(
                {
                    "event_id": stable_id("event", row.news_id, ticker),
                    "news_id": row.news_id,
                    "event_source": "news",
                    "event_type": "news",
                    "event_subtype": None,
                    "ticker": ticker,
                    "event_timestamp_utc": row.published_at_utc,
                    "market_session": row.market_session,
                    "headline": row.headline,
                    "summary": row.summary,
                    "sentiment_score": score,
                    "sentiment_label": label,
                    "sentiment_confidence": confidence,
                    "relevance_score": 1.0,
                    "provider_importance": None,
                    "dedupe_group_id": row.dedupe_hash,
                    "source_name": row.source_name,
                    "url": row.url,
                    "metadata": {},
                }
            )
    return pd.DataFrame(rows)


def load_prices(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"date", "ticker", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Price file is missing columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame = frame.dropna(subset=["date", "ticker", "close"]).sort_values(["ticker", "date"])
    return frame


def anchor_index(price_rows: pd.DataFrame, event_ts: pd.Timestamp, market_session: str) -> int | None:
    event_date = event_ts.tz_convert("America/New_York").date()
    dates = list(price_rows["date"].dt.date)
    target_date = event_date
    if market_session in {"after_hours", "closed"}:
        candidates = [idx for idx, date_value in enumerate(dates) if date_value > event_date]
    else:
        candidates = [idx for idx, date_value in enumerate(dates) if date_value >= target_date]
    return candidates[0] if candidates else None


def daily_close_timestamp_utc(date_value: object) -> str:
    market_tz = ZoneInfo("America/New_York")
    close_ts = pd.Timestamp(date_value).replace(hour=16, minute=0, second=0, microsecond=0).tz_localize(market_tz)
    return close_ts.tz_convert("UTC").isoformat()


def build_event_panel(root: Path, events: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    label_config = load_simple_yaml(root / "config" / "labels.yaml")
    ticker_config = load_simple_yaml(root / "config" / "tickers.yaml")
    benchmark_mode = str(label_config.get("benchmark_mode", "excess_vs_spy")).strip().lower()
    horizons = label_config.get("forward_horizons_days", [1, 3, 5])
    if isinstance(horizons, str):
        horizons = [1, 3, 5]
    benchmark = "SPY"
    benchmark_config = ticker_config.get("benchmark")
    if isinstance(benchmark_config, dict):
        benchmark = str(benchmark_config.get("primary", "SPY"))

    windows = label_config.get("event_windows", {})
    pre_minutes = int(windows.get("pre_minutes", 60)) if isinstance(windows, dict) else 60
    post_minutes = int(windows.get("post_minutes", 390)) if isinstance(windows, dict) else 390

    by_ticker = {ticker: group.reset_index(drop=True) for ticker, group in prices.groupby("ticker")}
    benchmark_prices = by_ticker.get(benchmark)

    aligned_rows: list[dict[str, object]] = []
    panel_rows: list[dict[str, object]] = []
    for event in events.itertuples(index=False):
        event_ts = pd.to_datetime(event.event_timestamp_utc, utc=True)
        ticker_prices = by_ticker.get(event.ticker)
        idx = anchor_index(ticker_prices, event_ts, event.market_session) if ticker_prices is not None else None
        has_alignment = ticker_prices is not None and idx is not None

        row = event._asdict()
        row["has_price_alignment"] = bool(has_alignment)
        row["anchor_bar_timestamp_utc"] = None
        row["anchor_price"] = None
        aligned_rows.append(row)

        if not has_alignment or ticker_prices is None or idx is None:
            continue

        anchor = ticker_prices.iloc[idx]
        anchor_price = float(anchor["close"])
        panel = {
            "event_id": event.event_id,
            "ticker": event.ticker,
            "event_type": event.event_type,
            "event_timestamp_utc": event_ts.isoformat(),
            "market_session": event.market_session,
            "anchor_bar_timestamp_utc": daily_close_timestamp_utc(anchor["date"]),
            "anchor_price": anchor_price,
            "close_t0": anchor_price,
            "sentiment_score": event.sentiment_score,
            "sentiment_label": event.sentiment_label,
            "event_window_pre_minutes": pre_minutes,
            "event_window_post_minutes": post_minutes,
            "has_price_alignment": True,
        }

        benchmark_idx = anchor_index(benchmark_prices, event_ts, event.market_session) if benchmark_prices is not None else None
        benchmark_anchor = None
        if benchmark_prices is not None and benchmark_idx is not None:
            benchmark_anchor = float(benchmark_prices.iloc[benchmark_idx]["close"])

        for horizon in horizons:
            horizon = int(horizon)
            future_idx = idx + horizon
            close_value = None
            forward_return = None
            if future_idx < len(ticker_prices):
                close_value = float(ticker_prices.iloc[future_idx]["close"])
                forward_return = close_value / anchor_price - 1.0

            benchmark_return = None
            if benchmark_prices is not None and benchmark_idx is not None and benchmark_anchor is not None:
                benchmark_future_idx = benchmark_idx + horizon
                if benchmark_future_idx < len(benchmark_prices):
                    benchmark_future = float(benchmark_prices.iloc[benchmark_future_idx]["close"])
                    benchmark_return = benchmark_future / benchmark_anchor - 1.0

            panel[f"close_t{horizon}d"] = close_value
            panel[f"forward_return_{horizon}d"] = forward_return
            panel[f"benchmark_return_{horizon}d"] = benchmark_return
            panel[f"excess_return_{horizon}d"] = (
                forward_return - benchmark_return if forward_return is not None and benchmark_return is not None else None
            )
            if benchmark_mode == "excess_vs_spy":
                panel[f"has_label_{horizon}d"] = forward_return is not None and benchmark_return is not None
            else:
                panel[f"has_label_{horizon}d"] = forward_return is not None

        panel_rows.append(panel)

    return pd.DataFrame(aligned_rows), pd.DataFrame(panel_rows)


def write_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        try:
            frame.to_parquet(path, index=False)
            return
        except (ImportError, ValueError, ModuleNotFoundError):
            frame.to_csv(path.with_suffix(".csv"), index=False)
            return
    frame.to_csv(path, index=False)


def write_json(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def quality_report(normalized: pd.DataFrame, events: pd.DataFrame, panel: pd.DataFrame) -> dict[str, object]:
    return {
        "normalized_news_rows": int(len(normalized)),
        "duplicate_headline_rate": float(normalized["is_duplicate"].mean()) if not normalized.empty else 0.0,
        "missing_ticker_rate": float(normalized["tickers"].map(lambda value: len(value) == 0).mean()) if not normalized.empty else 0.0,
        "event_rows": int(len(events)),
        "events_per_ticker": events["ticker"].value_counts().to_dict() if not events.empty else {},
        "events_per_session": events["market_session"].value_counts().to_dict() if not events.empty else {},
        "panel_rows": int(len(panel)),
        "benchmark_alignment_rate": float(panel["benchmark_return_1d"].notna().mean()) if "benchmark_return_1d" in panel else 0.0,
        "label_availability": {
            "1d": float(panel["has_label_1d"].mean()) if "has_label_1d" in panel else 0.0,
            "3d": float(panel["has_label_3d"].mean()) if "has_label_3d" in panel else 0.0,
            "5d": float(panel["has_label_5d"].mean()) if "has_label_5d" in panel else 0.0,
        },
    }


def run(root: Path) -> dict[str, object]:
    sources = load_simple_yaml(root / "config" / "sources.yaml")
    manual_path = root / "data" / "raw" / "news" / "manual" / "sample_news.jsonl"
    price_path = root / "data" / "raw" / "prices" / "daily" / "sample_prices.csv"
    if isinstance(sources.get("sources"), dict):
        source_config = sources["sources"]
        manual_config = source_config.get("manual_news", {})
        price_config = source_config.get("daily_prices", {})
        if isinstance(manual_config, dict):
            if not bool(manual_config.get("enabled", True)):
                raise ValueError("manual_news source is disabled in sources.yaml")
            if manual_config.get("input_path"):
                manual_path = root / str(manual_config["input_path"])
        if isinstance(price_config, dict):
            if not bool(price_config.get("enabled", True)):
                raise ValueError("daily_prices source is disabled in sources.yaml")
            if price_config.get("input_path"):
                price_path = root / str(price_config["input_path"])

    raw_rows = parse_jsonl(manual_path)
    validate_records(root, "news_raw.schema.json", raw_rows, label="news_raw")
    normalized = normalize_news(root, raw_rows)
    validate_records(root, "news_normalized.schema.json", normalized.to_dict(orient="records"), label="news_normalized")
    events = build_event_table(normalized)
    validate_records(root, "event_table.schema.json", events.to_dict(orient="records"), label="event_table")
    prices = load_prices(price_path)
    aligned, panel = build_event_panel(root, events, prices)
    validate_records(root, "event_panel.schema.json", panel.to_dict(orient="records"), label="event_panel")

    write_frame(normalized, root / "data" / "interim" / "normalized_news" / "normalized_news_v1.csv")
    deduped = normalized.loc[~normalized["is_duplicate"]].copy() if not normalized.empty else normalized
    write_frame(deduped, root / "data" / "interim" / "deduped_news" / "deduped_news_v1.csv")
    write_frame(events, root / "data" / "interim" / "tagged_events" / "event_table_v1.csv")
    write_frame(aligned, root / "data" / "interim" / "aligned_events" / "aligned_events_v1.csv")
    write_frame(panel, root / "data" / "interim" / "labeled_events" / "labeled_events_v1.csv")
    write_frame(panel, root / "data" / "processed" / "event_panel" / "event_panel_v1.parquet")

    report = quality_report(normalized, events, panel)
    manifest = {
        "raw_news_path": str(manual_path.relative_to(root)),
        "raw_news_rows": len(raw_rows),
        "price_path": str(price_path.relative_to(root)),
        "price_rows": int(len(prices)),
        "outputs": {
            "event_panel": "data/processed/event_panel/event_panel_v1.parquet",
            "quality_report": "data/audit/quality_reports/event_panel_quality_v1.json",
        },
    }
    write_json(report, root / "data" / "audit" / "quality_reports" / "event_panel_quality_v1.json")
    write_json(manifest, root / "logs" / "manifests" / "pipeline_manifest_v1.json")
    return {"manifest": manifest, "quality_report": report}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local event-research event panel.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Path to event-research root.")
    args = parser.parse_args()
    result = run(args.root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

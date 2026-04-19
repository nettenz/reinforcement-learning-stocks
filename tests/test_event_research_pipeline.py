from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = REPO_ROOT / "event-research" / "scripts" / "run_pipeline.py"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("event_research_pipeline", PIPELINE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_event_research_pipeline_builds_panel(tmp_path: Path) -> None:
    source_root = REPO_ROOT / "event-research"
    work_root = tmp_path / "event-research"
    shutil.copytree(
        source_root,
        work_root,
        ignore=shutil.ignore_patterns(".tmp", "__pycache__", "interim", "processed", "audit", "logs"),
    )

    pipeline = load_pipeline_module()
    result = pipeline.run(work_root)

    parquet_path = work_root / "data" / "processed" / "event_panel" / "event_panel_v1.parquet"
    csv_path = parquet_path.with_suffix(".csv")
    assert parquet_path.exists() or csv_path.exists()

    panel = pd.read_parquet(parquet_path) if parquet_path.exists() else pd.read_csv(csv_path)
    expected_columns = {
        "ticker",
        "event_timestamp_utc",
        "event_type",
        "sentiment_score",
        "market_session",
        "forward_return_1d",
        "forward_return_3d",
        "forward_return_5d",
        "excess_return_1d",
        "excess_return_3d",
        "excess_return_5d",
    }
    assert expected_columns.issubset(panel.columns)
    assert len(panel) == 4
    assert result["quality_report"]["missing_ticker_rate"] == 0.0
    for horizon in (1, 3, 5):
        label_col = f"has_label_{horizon}d"
        excess_col = f"excess_return_{horizon}d"
        bad = panel[(panel[label_col] == True) & (panel[excess_col].isna())]  # noqa: E712
        assert bad.empty, f"{label_col} should require non-null {excess_col} under excess-vs-benchmark labeling"


def test_event_research_pipeline_uses_config_aliases(tmp_path: Path) -> None:
    source_root = REPO_ROOT / "event-research"
    work_root = tmp_path / "event-research"
    shutil.copytree(
        source_root,
        work_root,
        ignore=shutil.ignore_patterns(".tmp", "__pycache__", "interim", "processed", "audit", "logs"),
    )

    tickers_path = work_root / "config" / "tickers.yaml"
    tickers_text = tickers_path.read_text(encoding="utf-8")
    tickers_path.write_text(tickers_text + "\n  NVDA_ALIAS: NVDA\n", encoding="utf-8")

    news_path = work_root / "data" / "raw" / "news" / "manual" / "sample_news.jsonl"
    rows = [json.loads(line) for line in news_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows, "fixture news rows should exist"
    rows[1]["tickers_raw"] = ["NVDA_ALIAS"]
    news_path.write_text("\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")

    pipeline = load_pipeline_module()
    result = pipeline.run(work_root)
    assert result["quality_report"]["missing_ticker_rate"] == 0.0

    panel_path = work_root / "data" / "processed" / "event_panel" / "event_panel_v1.parquet"
    panel = pd.read_parquet(panel_path) if panel_path.exists() else pd.read_csv(panel_path.with_suffix(".csv"))
    assert "NVDA" in set(panel["ticker"]), "config alias should resolve NVDA_ALIAS to NVDA"


def test_event_research_pipeline_fails_on_schema_violation(tmp_path: Path) -> None:
    source_root = REPO_ROOT / "event-research"
    work_root = tmp_path / "event-research"
    shutil.copytree(
        source_root,
        work_root,
        ignore=shutil.ignore_patterns(".tmp", "__pycache__", "interim", "processed", "audit", "logs"),
    )

    news_path = work_root / "data" / "raw" / "news" / "manual" / "sample_news.jsonl"
    bad_row = {
        "source_record_id": "bad-001",
        "source_name": "manual_fixture",
        "retrieved_at_utc": "2026-04-18T18:00:00Z",
        "published_at_raw": "2026-04-15T10:00:00-04:00",
        "summary": "Missing required headline should fail schema validation.",
        "body": None,
        "url": "https://example.local/bad-row",
        "authors": ["Research Desk"],
        "tickers_raw": ["AAPL"],
        "language": "en",
        "metadata": {"fixture": True},
    }
    with news_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(bad_row, separators=(",", ":")) + "\n")

    pipeline = load_pipeline_module()
    try:
        pipeline.run(work_root)
    except ValueError as exc:
        assert "Schema validation failed" in str(exc)
    else:
        raise AssertionError("Expected schema validation failure for malformed raw news record")

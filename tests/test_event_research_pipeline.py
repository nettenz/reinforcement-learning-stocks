from __future__ import annotations

import importlib.util
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
        ignore=shutil.ignore_patterns("interim", "processed", "audit", "logs"),
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

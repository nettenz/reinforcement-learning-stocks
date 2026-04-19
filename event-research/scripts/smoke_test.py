from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


EVENT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = EVENT_ROOT / "scripts" / "run_pipeline.py"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("event_research_pipeline", PIPELINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load pipeline module from {PIPELINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    pipeline = load_pipeline_module()
    result = pipeline.run(EVENT_ROOT)

    parquet_path = EVENT_ROOT / "data" / "processed" / "event_panel" / "event_panel_v1.parquet"
    csv_path = parquet_path.with_suffix(".csv")
    if parquet_path.exists():
        panel = pd.read_parquet(parquet_path)
        output_path = parquet_path
    elif csv_path.exists():
        panel = pd.read_csv(csv_path)
        output_path = csv_path
    else:
        raise AssertionError("Pipeline did not write an event panel output.")

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
    missing = expected_columns - set(panel.columns)
    if missing:
        raise AssertionError(f"Event panel missing columns: {sorted(missing)}")
    if len(panel) != 4:
        raise AssertionError(f"Expected 4 fixture rows, got {len(panel)}")
    if result["quality_report"]["missing_ticker_rate"] != 0.0:
        raise AssertionError("Fixture should have zero missing ticker rate.")

    print(f"Event research smoke test passed: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Event research smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

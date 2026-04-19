# Event Research Dataset

Local-first event dataset tooling for stock-news experiments.

The first pass is intentionally small:

- universe: `AAPL`, `AMD`, `NVDA`, `QQQ`, `SPY`
- source type: local manual JSONL news
- event type: `news`
- sentiment: deterministic lexicon scorer
- labels: `1d`, `3d`, `5d` returns and excess returns versus `SPY`

## Quick Start

From the repo root:

```powershell
python event-research/scripts/run_pipeline.py
```

Expected output:

```text
event-research/data/processed/event_panel/event_panel_v1.parquet
```

If your local pandas install does not have a parquet engine, the pipeline also writes:

```text
event-research/data/processed/event_panel/event_panel_v1.csv
```

## Input Fixtures

The starter pipeline reads:

- `data/raw/news/manual/sample_news.jsonl`
- `data/raw/prices/daily/sample_prices.csv`

Replace these with larger local exports when ready. Keep raw data immutable and write transformed outputs into `data/interim/` and `data/processed/`.

## Leakage Rules

- Event labels are computed only from prices after the event anchor date.
- After-hours and closed events anchor to the next tradeable price row.
- Regular-session events anchor to the same tradeable date in this daily first pass.
- Duplicate filtering uses normalized headline, date bucket, and ticker.

## Main Outputs

- `data/interim/normalized_news/normalized_news_v1.csv`
- `data/interim/tagged_events/event_table_v1.csv`
- `data/interim/aligned_events/aligned_events_v1.csv`
- `data/interim/labeled_events/labeled_events_v1.csv`
- `data/processed/event_panel/event_panel_v1.parquet`
- `data/audit/quality_reports/event_panel_quality_v1.json`
- `logs/manifests/pipeline_manifest_v1.json`

## Next Growth Steps

1. Add a Hugging Face ingestion script that writes raw JSONL plus a manifest.
2. Swap the fixture price CSV for a daily OHLCV loader.
3. Add ticker entity extraction for articles that do not include `tickers_raw`.
4. Add intraday anchor support for pre-market and regular-session event windows.

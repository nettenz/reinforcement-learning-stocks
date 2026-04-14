# Session Note — 2026-04-13 Transfer Follow-Up Analysis

## Context
This note captures the interpretation of the confirmatory follow-up batch after the earlier NVDA champion/baseline comparison. The follow-up tested:
- NVDA baseline re-check on fresh seeds
- AAPL transfer confirmation
- AMD transfer confirmation

## Key Findings
- The earlier NVDA champion did not hold up under fresh-seed confirmation.
- The NVDA baseline re-check was still unstable and low-activity, but slightly less bad on raw return than the earlier champion pattern.
- AAPL transfer confirmation was negative on both alpha and return.
- AMD transfer confirmation was also negative on average, with very high CV risk.

## Evidence Summary
### NVDA baseline re-check
- Mean test actionable accuracy: 0.1080
- Mean test win rate: 0.1045
- Mean test cumulative signal return: 0.0340
- Mean test alpha vs QQQ: -0.1209
- Mean test CV: 2.2361
- Pass count: 0

### AAPL transfer confirmation
- Mean test actionable accuracy: 0.4813
- Mean test win rate: 0.4859
- Mean test cumulative signal return: -0.1346
- Mean test alpha vs QQQ: -0.2795
- Mean test CV: 0.7306
- Pass count: 0

### AMD transfer confirmation
- Mean test actionable accuracy: 0.5020
- Mean test win rate: 0.5005
- Mean test cumulative signal return: -0.0267
- Mean test alpha vs QQQ: -0.1627
- Mean test CV: 23.4018
- Pass count: 0

## Interpretation
- The settings do not transfer reliably across tickers.
- NVDA itself remains too sparse and unstable to treat as a robust promotion candidate.
- AAPL and AMD did not validate the transfer hypothesis.
- Any apparent gains in the earlier runs should be treated as fragile and ticker-specific rather than generalizable.

## Recommended Next Step
- Calibrate per ticker instead of using one shared champion setting.
- Keep NVDA separate from AAPL and AMD.
- Use narrow local sweeps around each ticker’s best baseline, not broad cross-ticker transfer batches.

## Status
- Promotion readiness: not ready
- Current best interpretation: exploratory only, not robust enough for a universal default

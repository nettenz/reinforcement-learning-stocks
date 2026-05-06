# Mean Voting Findings and Experiment Commands

## Summary

AMD is promotable with mean voting. NVDA remains the regime-shift outlier and did not recover with 3-seed majority voting.

## Current Decisions

- AMD: promote with mean voting and the `profit_take_5pct` exit rule.
- NVDA: hold. Adding a third seed did not recover the test regime.
- Leaderboard: now includes `ensemble_voting_method` so the active config is visible in sweep results.

## Findings

### AMD
- Majority voting on a 2-seed ensemble was fragile and could tie into hold/default behavior.
- Mean voting restored trade generation on AMD.
- Validated result: 76 test trades, Sharpe 0.761, exit rate 10.8%.

### NVDA
- 2-seed majority voting did not explain NVDA’s weak test behavior.
- Adding a third seed did not materially recover performance.
- Best tested NVDA result remained below the validation regime, so the issue is still generalization/regime shift rather than aggregation alone.

### Leaderboard update
- Added column: `ensemble_voting_method`
- Current active config value: `mean` for NVDA, AMD, and AAPL in `staging/models/ensemble_config.json`.

## Commands to Run

### AMD promotion check
```bash
.venv/Scripts/python.exe scripts/backtest_exit_rules.py --ticker amd --voting-method mean
```

### NVDA 3-seed majority test
```bash
.venv/Scripts/python.exe scripts/backtest_exit_rules.py --ticker nvda --voting-method voting
```

### Evaluate the sweep leaderboard for AMD
```bash
.venv/Scripts/python.exe scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --ticker AMD --label sweep_amd_baseline_v3
```

### Evaluate the sweep leaderboard for NVDA
```bash
.venv/Scripts/python.exe scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --ticker NVDA --label sweep_overtrade_fix_nvda_stationary_v3
```

## Interpretation Guide

- If AMD mean voting keeps trade count above zero and exit rate near the current validated band, treat it as production-ready.
- If NVDA still fails under 3-seed majority, do not spend more effort on voting-method changes; move to regime analysis or retraining.
- If future sweeps use a different aggregation method, keep `ensemble_voting_method` updated in the leaderboard so runs remain comparable.

## Notes

- The backtest script still only accepts `nvda` and `amd` as tickers.
- AAPL is not wired into the current exit backtest path, so it is excluded from this promotion batch.

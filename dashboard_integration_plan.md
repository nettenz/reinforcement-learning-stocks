# Dashboard Integration Plan — Algorithm Diversity & Structural Cooldowns

Following the **@[/signal-dashboard-troubleshooter]** workflow, this plan outlines the necessary updates to `src/analytics_dashboard.py` to support the evolution of the RL trading pipeline.

## 1. Issue Summary
The dashboard is currently rigid, assuming only the original "Foundation" tickers (NVDA, AAPL, AMD) and the SAC algorithm. It lacks visibility and controls for the new PPO-based binary action architecture and the `min_hold_bars` cooldown constraint.

## 2. Schema Evolution
The following fields must be integrated into the dashboard's data flow:
- `binary_actions`: Boolean (identifies PPO vs SAC).
- `min_hold_bars`: Integer (identifies structural cooldown).
- `ticker`: Expanding from 3 to 5+ tickers.

## 3. Broken Assumptions Found
- **Static Ticker List**: Hardcoded sidebar filters.
- **Algo Monoculture**: Assumes `model.predict` always returns continuous weights.
- **Command Generator**: Omits structural CLI flags, making research reproduction difficult.
- **G6 Hard-Thresholding**: Colors everything > 80% trade rate as "Overtrade", which is incorrect for bull-regime MU/AMZN agents.

## 4. Implementation Steps

### A. Dynamic Ticker Loading
Update `render_sidebar` to derive the ticker list from the leaderboard rather than a constant.
```python
# From:
# TICKERS = ["nvda", "aapl", "amd"]
# To:
available_tickers = sorted(df['ticker'].unique().tolist())
```

### B. Updated Config Grouping
Inject structural parameters into the configuration identifier to ensure proper aggregation of multi-seed sweeps.
```python
# Location: get_leaderboard_data()
# Add 'binary_actions' and 'min_hold_bars' to the group_cols
group_cols = [
    'ticker', 'run_label', 'ent_coef', 'learning_rate', 
    'binary_actions', 'min_hold_bars' # NEW
]
```

### C. Command Generator Sync
Update the copy-paste command builder to include the new CLI flags.
```python
# Location: generate_command()
cmd = f"python src/experiments.py --ticker {ticker} ..."
if row.get('binary_actions'):
    cmd += " --binary-actions"
if row.get('min_hold_bars', 0) > 0:
    cmd += f" --min-hold-bars {row['min_hold_bars']}"
```

### D. Regime-Aware G6 Visualization
Update the metric display to use ticker-specific thresholds (e.g., 1.0 for MU/AMZN, 0.8 for others).

## 5. Leaderboard Comparability Impact
**Impact**: MEDIUM
**Reason**: Re-grouping will split existing experiment rows. Historical data without these columns will need safe fallbacks (`binary_actions=False`, `min_hold_bars=0`) to remain visible alongside new runs.

## 6. Regression Checks
- [ ] Load dashboard with an old `experiment_leaderboard.csv` (pre-MU).
- [ ] Verify MU/AMZN appear in the sidebar automatically.
- [ ] Confirm "Copy Command" for MU includes `--min-hold-bars 3`.
- [ ] Check that accuracy charts still aggregate correctly across seeds.

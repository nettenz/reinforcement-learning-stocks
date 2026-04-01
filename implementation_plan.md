# Implementation Plan - Intelligence Synchronization

This plan addresses the "Model expects (15,), environment provides (17,)" error by ensuring that the results of the `experiments.py` sweep (the weights) are actually saved and promoted to the dashboard.

## User Review Required

> [!IMPORTANT]
> The `experiments.py` script will now save model zip files. For large sweeps, this can consume significant disk space (~5-10MB per run). I will implement a "Champion Selection" logic that only keeps the best model in the main directory but snapshots others.

## Proposed Changes

### Experiment Runner Expansion

#### [MODIFY] [experiments.py](file:///Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/src/experiments.py)
- **Model Saving**: Update the experiment loop to save the model weights for every run into the `snapshot_dir`.
- **Champion Promotion**: Add logic at the end of `run_experiments` to identify the model with the highest `ranking_score` and copy it to the default `models/sac_trading_bot.zip` path.
- **Path Generation**: Ensure model filenames include the timestamp and run label for easy identification.

### Dashboard Resilience

#### [MODIFY] [analytics_dashboard.py](file:///Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/src/analytics_dashboard.py)
- **Model Selection**: Add a sidebar dropdown that lists all available `.zip` models in the `models/` and `snapshots/` directories.
- **Shape Validation**: Add a pre-check that compares the `active_news_columns` and `market_feature_columns` against the model's policy network input layer.
- **Graceful Error Handling**: If a shape mismatch occurs, display a clear table showing "Environment Expected" vs "Model Provided" columns.

## Verification Plan

### Automated Tests
- Run a small experiment sweep with 2 seeds:
  ```bash
  python3 src/experiments.py --seeds 42,84 --timesteps 1000 --run-label sync-test
  ```
- Verify that `models/sac_trading_bot.zip` is updated with a timestamp corresponding to the best run.
- Verify that the dashboard loads the new model without a shape error.

### Manual Verification
- Check the `snapshots/` directory for multiple model zip files.
- Use the dashboard dropdown to switch between an "old" model and the "new" model and confirm the shape error appears/disappears correctly.

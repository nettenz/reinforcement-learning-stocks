# Session Update: Dashboard Integrity and Next Experiment

Date: 2026-04-01

## Scope Completed
- Stabilized dashboard runtime integrity after recent sidebar/model-selection changes.
- Reconciled feature-shape alignment with new news pipeline schema.
- Produced a proposed next experiment based on latest snapshot performance.

## Dashboard Fixes Applied
1. Import/source corrections in `src/analytics_dashboard.py`:
   - `simulate_agent_signals` imported from `src.signal_analytics` (not `src.experiments`).
   - Added missing imports used at runtime:
     - `ACTION_LABELS`
     - `compute_metrics`
     - `DEFAULT_SUMMARY_PATH`
     - `DEFAULT_SNAPSHOT_DIR`
     - `run_experiments`
     - `write_experiment_outputs`
2. Restored missing page function:
   - Reintroduced `render_signal_analytics_page(...)` as a proper top-level function.
3. Shape validation repair:
   - Dashboard now validates dimensions using shared alignment path (`_load_model`, `_expected_observation_dim`, `_align_features_to_model`) before env construction.

## News/Schema Alignment Fixes
1. Updated news feature schema in `src/signal_analytics.py` to include:
   - `NewsCount`, `SentimentMean`, `SentimentStd`, `SentimentMin`, `SentimentMax`,
   - `SentimentConfidenceMean`, `SentimentGeminiShare`, `SentimentOllamaShare`
2. Expanded stationary feature list in `src/signal_analytics.py` to match feature engineering outputs.
3. Synced market feature handling to avoid off-by-one mismatches:
   - Alignment now returns explicit `market_feature_columns`.
   - `TradingEnv` is instantiated with those explicit columns in validation and simulation paths.

## Runtime Verification Highlights
- Alignment checks verified expected observation sizes can resolve correctly for both 13 and 15 dimensions on current datasets.
- Dashboard service restarts succeeded during the session (latest confirmed PID was 41840 when checked).

## Data Artifact State Observed
- Missing in `data/` at time of analysis:
  - `experiment_leaderboard.csv`
  - `experiment_summary.json`
- Present:
  - `experiment_reward_leaderboard.csv`
  - extensive snapshot history in `data/experiment_snapshots/`

## Latest Experiment Readout (Snapshot-driven)
- Sharpe-heavy runs showed repeated validation/test collapse patterns in several recent snapshots.
- Best non-collapsing frontier currently appears near Sortino settings around:
  - `timesteps=40000`
  - `ent_coef=0.02`
  - `reward_direction_scale=1.0`
  - `reward_hold_penalty_scale=0.1`
  - `reward_drawdown_penalty_scale=0.1`
  - `reward_action_bonus_scale=0.25`
- Remaining issue: test alpha vs QQQ is still mostly negative.

## Proposed Next Run
Run label: `sortino-robustness-v2`

```bash
python src/experiments.py \
  --include-news --use-stationary-features \
  --reward-mode sortino \
  --seeds 7,13,21,42,84,121 \
  --timesteps 40000,60000 \
  --learning-rates 0.0003 \
  --gammas 0.99 \
  --ent-coefs 0.015,0.02,0.03 \
  --threshold 0.002 \
  --horizon 1 \
  --transaction-cost-rate 0.001 \
  --trade-penalty 0.05 \
  --reward-return-scale 1.0 \
  --reward-direction-scale 0.8,1.0,1.2 \
  --reward-hold-penalty-scale 0.08,0.10 \
  --reward-drawdown-penalty-scale 0.10,0.15 \
  --reward-action-bonus-scale 0.15,0.25 \
  --reward-clip 1.0 \
  --reward-ignore-transaction-cost \
  --append \
  --run-label sortino-robustness-v2
```

## Promotion Criteria
Promote only configurations satisfying all:
1. `test_actionable_accuracy >= 0.53`
2. `test_trade_win_rate >= 0.52`
3. `test_alpha_vs_qqq >= 0.00`
4. `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05`
5. No seed-level collapse (near-zero test actionable accuracy)

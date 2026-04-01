# Cross-Platform Handoff: SAC Trading Optimization

Updated: 2026-04-01

This document provides context for continuing work on a different machine (Mac). Mention this file or the Conversation ID: 571b035c-0bc2-4bbb-9c86-960241bbb173 to resume quickly.

## Current Status
- Dashboard routing and import integrity issues were fixed in `src/analytics_dashboard.py`.
- Signal Analytics, Experiments, and Experiment Insights pages now resolve previously missing symbols.
- Shape-mismatch logic was corrected by aligning feature-selection with `TradingEnv` market/news schema.
- News pipeline schema is now synchronized across producer/consumer modules.

## Recent Fixes Applied
1. Dashboard import/source fixes:
   - `simulate_agent_signals` import moved to `src.signal_analytics`.
   - Added missing imports used at runtime:
     - `ACTION_LABELS`
     - `compute_metrics`
     - `DEFAULT_SUMMARY_PATH`
     - `DEFAULT_SNAPSHOT_DIR`
     - `run_experiments`
     - `write_experiment_outputs`
2. Dashboard function repair:
   - Reintroduced `render_signal_analytics_page(...)` as a proper top-level function.
3. Shape-alignment fixes:
   - Expanded `NEWS_FEATURE_COLUMNS` in `src/signal_analytics.py` to include:
     - `SentimentConfidenceMean`, `SentimentGeminiShare`, `SentimentOllamaShare`
   - Synced alignment with environment by passing explicit `market_feature_columns` into `TradingEnv`.
   - Updated stationary feature list in `src/signal_analytics.py` to match engineering outputs.

## Verified Runtime Notes
- Main leaderboard and summary files may be absent in `data/`:
  - `data/experiment_leaderboard.csv` not present.
  - `data/experiment_summary.json` not present.
- Snapshot history is present and extensive in `data/experiment_snapshots/`.
- Current reward leaderboard exists at `data/experiment_reward_leaderboard.csv`.

## Latest Experiment Readout (2026-04-01 snapshots)
- Sharpe configurations showed multiple validation/test collapses (very high val actionable with zero/near-zero test actionable in some runs).
- Best non-collapsing frontier currently comes from Sortino runs around:
  - `timesteps=40000`
  - `ent_coef=0.02`
  - `reward_direction_scale=1.0`
  - `reward_hold_penalty_scale=0.1`
  - `reward_drawdown_penalty_scale=0.1`
  - `reward_action_bonus_scale=0.25`
- Test alpha vs benchmark remains mostly negative, so next step should focus on robustness and OOS alpha recovery.

## Proposed Next Experiment (Approved Recommendation)
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

## Promotion Criteria (Go/No-Go)
Promote only configs meeting all:
1. `test_actionable_accuracy >= 0.53`
2. `test_trade_win_rate >= 0.52`
3. `test_alpha_vs_qqq >= 0.00`
4. `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05`
5. No seed-level collapse (test actionable near zero)

## Environment Setup Checklist
- Ensure `.venv` is active and dependencies are installed:
  - `pip install -r requirements.txt`
- Ensure `.env` contains provider keys used by the news sentiment pipeline if running refreshes.
- If data refresh is needed:
  ```bash
  .venv/bin/python -c "from src.market_data import get_tech_training_data; get_tech_training_data(refresh=True, include_news=True, use_stationary_features=True)"
  ```

# Session Summary - 2026-04-13

## Scope

- Stabilize intraday 5m experiment workflow.
- Execute and verify Batch A trigger calibration.
- Prepare Batch B using the selected trigger pair.

## Completed Work

- Implemented interval-aware dashboard/model-path routing and state-reset behavior for 5m vs 1d flows.
- Added intraday 5m triggered runner and realism controls.
- Added market-data quality gates and intraday cache top-up logic.
- Diagnosed Batch A sweep mismatch where `experiment_preset=intraday_5m` overwrote threshold/horizon values.
- Patched preset handling in `src/experiments.py` so explicit CLI values are respected.
- Re-ran and verified Batch A outputs using latest 10 rows per run label.

## Verification Findings (Batch A)

- Parameter consistency across run labels is now correct:

  - `thr0p001-h3`
  - `thr0p001-h5`
  - `thr0p0015-h3`
  - `thr0p0015-h5`
  - `thr0p002-h3`
  - `thr0p002-h5`

- Family-level metrics remain weak and very close across arms:

  - Mean test return remains negative.
  - Mean test alpha vs QQQ remains negative.
  - Collapse behavior persists in multiple seeds.

- Distinguishing signal was minor:

  - `h=3` arms showed better mean test win-rate.
  - Highest mean ranking score was `thr0p0015-h5`, but practical robustness preference favors `thr0p001-h3`.

## Decision

- Selected Batch B trigger pair: `threshold=0.001`, `horizon=3`.
- Rationale: better execution-quality profile (win-rate behavior) with no material return/alpha downside versus alternatives.

## New Artifacts Created

- Script: `run_intraday_5m_batch_B_recommended_thr0p001_h3.ps1`
- Planned outputs:

  - `data/experiment_leaderboard_intraday_5m_batch_b_recommended.csv`
  - `data/experiment_reward_leaderboard_intraday_5m_batch_b_recommended.csv`
  - `data/experiment_summary_intraday_5m_batch_b_recommended.json`
  - `data/experiment_snapshots/intraday_5m_batch_b_recommended/`

## Next Step

- Run `run_intraday_5m_batch_B_recommended_thr0p001_h3.ps1`.
- After completion, evaluate turnover/drawdown/trade-penalty combinations by robust mean return, CV, alpha, and collapse-seed count.

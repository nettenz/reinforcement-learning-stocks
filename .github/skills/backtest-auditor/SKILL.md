---
name: backtest-auditor
description: 'Audit trading evaluation pipelines for leakage, metric validity, robustness, and cross-experiment comparability. Use for src/experiments.py, src/trading_env.py, src/market_data.py, src/signal_analytics.py, and gate/trading artifacts to verify realistic, leakage-free, statistically defensible results. Adapted for SAC multi-seed sweep workflow with 6-gate promotion framework.'
argument-hint: 'What experiment, split, ticker, or evaluation path should be audited? (e.g. AAPL leakage, reward direction term, feature shift correctness)'
user-invocable: true
---

# Backtest Auditor

Quantitative research audit workflow for validating RL backtest integrity and evaluation correctness.

## Objective
Ensure reported SAC trading performance is:
- Realistic
- Leakage-free
- Statistically valid
- Comparable across experiments

## Project Context (read before auditing)
- **Algorithm:** SAC (Stable Baselines3). PPO is deprecated.
- **Execution:** `next_bar` mode only. Same-bar close execution is banned.
- **Observation space:** Stationary features via `compute_stationary_features()` in `src/feature_engineering.py`. Raw 10-feature space is deprecated.
- **Promotion framework:** 6 gates required (not 5). Gate 6 = `test_trade_rate ∈ [0.40, 0.80]`.
- **Critical structural fix:** `max_weight_delta_per_step=0.10` must be set. Without it, agents overtrade at 99%+ rate and pass Gates 1–5 via degenerate always-long behavior.
- **Leaderboard:** `data/experiment_leaderboard.csv` (master, deduplicated 2026-04-30).
- **Known ticker status:** NVDA promoted. AAPL blocked (leakage audit pending). AMD blocked (env fit issue, CV 4.5+).
- **Known reward risk:** `reward_direction_scale=0.35` carries look-ahead bias risk — verify it uses only next_bar execution price, not bar T close.

## Default Focus Files
- `src/experiments.py` — 6-gate promotion logic, walk-forward splits
- `src/trading_env.py` — `TradingEnv`, `PositionManager`, `_apply_max_weight_delta`, reward computation
- `src/feature_engineering.py` — `compute_stationary_features()` — ground truth observation space
- `src/market_data.py` — OHLCV ingestion, parquet caching, feature routing
- `src/signal_analytics.py` — post-run metrics, accuracy label construction
- `src/ensemble.py` — `SparseEnsemble`, seed deduplication (`drop_duplicates(subset=["seed"])`)
- `scripts/evaluate_sweep.py` — primary post-sweep gate evaluation tool
- `scripts/run_exp9_walkforward.py` — ensemble walk-forward validation (TICKER_CONFIG must match champion seeds)
- `data/experiment_leaderboard.csv` — master leaderboard

## Core Audit Procedure

### 0. Confirm delivery mode
Ask whether the user wants review-only output or implementation-inclusive output with patch proposals.

### 1. Validate data splits
- Inspect train/val/test separation in `src/experiments.py` (70/15/15 chronological split).
- Verify chronological ordering is preserved end-to-end.
- Check for duplicate dates or NaN gaps in parquet cache.
- For AAPL specifically: compare val vs test period market regimes before assuming leakage.

### 2. Detect leakage
- Trace reward computation in `TradingEnv._compute_reward`. Specifically audit `reward_direction_scale` — confirm it uses `next_bar` execution price only, not bar T close price.
- Inspect feature construction in `src/feature_engineering.py` — verify all rolling features shift correctly (NaN in early rows is correct behavior, not a bug).
- Inspect news sentiment alignment in `src/news_data.py` — timestamps must be bar-open aligned.
- Confirm `next_bar` execution in `PositionManager` — no same-bar fill.
- Check `_apply_max_weight_delta` is active — `max_weight_delta_per_step=0.0` disables it silently.

### 3. Evaluate metrics
- Audit actionable accuracy, win rate, Sharpe, alpha vs QQQ, CV across seeds.
- Flag degenerate always-long patterns: high accuracy + high trade rate (99%+) + positive alpha only in bullish test periods. Gate 6 should catch this.
- Check val→test accuracy drift. Threshold: ≤ 0.05. AAPL showed severe collapse — investigate regime or leakage.
- CV > 1.0 with < 5 seeds is a seed-count artifact, not necessarily instability. Always run ≥ 5 seeds before classifying CV as a structural problem.

### 4. Validate baselines
- Confirm QQQ benchmark comparison is implemented correctly in alpha gate.
- Confirm no-trade baseline (flat policy) is present.
- Check that Gate 6 is active in `scripts/evaluate_sweep.py` — without it, degenerate always-long passes Gates 1–5.

### 5. Check robustness
- Inspect multi-seed CV. Threshold: < 1.0 with ≥ 5 seeds.
- Check for degenerate seed patterns: `accuracy=1.0, win_rate=1.0, trade_rate≈0` = collapsed seed, not a champion.
- Verify `src/ensemble.py` has `drop_duplicates(subset=["seed"])` in `load_top_n_models` — without this, same seed loads multiple times inflating agreement rate to 1.0.

### 6. Check reproducibility
- Verify model zip files exist for all champion seeds in `data/experiment_snapshots/`.
- Verify `staging/models/ensemble_config.json` seeds match actual champion seeds — `generate_ensemble_config.py` label filtering is unreliable, manual verification required.
- Verify `TICKER_CONFIG` in `scripts/run_exp9_walkforward.py` points to correct leaderboard and seeds before running.

### 7. Produce fixes with comparability guard
- Recommend minimal, testable corrections first.
- Distinguish correctness bugs from methodology upgrades.
- Include leaderboard comparability impact for every fix.

## Decision Logic
- If `max_weight_delta_per_step=0.0` across all sweep rows → structural overtrade bug, not a reward tuning problem. Fix the cap first.
- If trade rate > 80% despite Gate 6 → Gate 6 not active in evaluate_sweep.py, or using old leaderboard without the gate column.
- If val accuracy >> test accuracy with drift > 0.10 → leakage or regime collapse. Run AAPL audit checklist before any sweep.
- If CV > 4.0 → environment fit issue (AMD pattern). Do not attempt reward tuning until root cause is identified.
- If CV > 1.0 with exactly 3–4 seeds → seed count artifact. Re-run with 5 seeds before classifying as instability.
- If duplicate seed rows in leaderboard → run deduplication script before evaluating.
- If `generate_ensemble_config.py` writes wrong seeds → manually write `staging/models/ensemble_config.json`.

## Required Output Format
Always structure output in this order:
1. Audit verdict
2. Trustworthy components
3. Issues found
4. Leakage risks
5. Metric issues
6. Gate coverage gaps
7. Reproducibility gaps
8. Recommended fixes
9. Next proposed experiments or runs (if justified)
10. Leaderboard comparability impact (REQUIRED)

## Run Specification Rule (MANDATORY)
For each proposed run include:
- `.\.venv\Scripts\Activate.ps1` activation
- full relative script path
- all key args including `--max-weight-delta-per-step 0.10`, `--use-stationary-features`, `--append`
- expected output artifact path(s)

## Constraints
- Do not assume leakage without proof — regime shift can produce identical symptoms.
- Distinguish training-data leakage from evaluation-only leakage.
- Never recommend a sweep without confirming Gate 6 is active.
- Never recommend promotion with < 5 seeds (CV instability risk).
- Do not merge AAPL/AMD blocked status into NVDA conclusions.

## Quality Checks Before Finalizing
- Every finding references concrete file/function evidence.
- Leakage claims include proof path and affected stage (train/val/test).
- Gate 6 coverage confirmed before any promotion recommendation.
- `max_weight_delta_per_step` value confirmed before diagnosing overtrade.
- Seed count confirmed before classifying CV as structural instability.
- Leaderboard comparability impact present for each fix.
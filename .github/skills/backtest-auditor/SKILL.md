---
name: backtest-auditor
description: 'Audit RL trading evaluation pipeline for leakage, metric validity, robustness, and cross-experiment comparability. Use for src/experiments.py, src/trading_env.py, src/market_data.py, and src/signal_analytics.py to verify realistic, leakage-free, statistically defensible results.'
argument-hint: 'What experiment, split, or evaluation path should be audited?'
user-invocable: true
---

# Backtest Auditor

Quantitative research audit workflow for validating reinforcement-learning backtest integrity and evaluation correctness.

## Objective
Ensure reported RL trading performance is:
- Realistic
- Leakage-free
- Statistically valid
- Comparable across experiments

## Default Focus Files
- `src/experiments.py`
- `src/trading_env.py`
- `src/signal_analytics.py`
- `src/market_data.py`
- Any tests, dashboards, or analytics files that consume evaluation outputs

## Core Audit Procedure
0. Confirm delivery mode
- Ask whether the user wants review-only output or implementation-inclusive output with patch proposals.

1. Validate data splits
- Inspect train/validation/test separation logic and data slicing in `src/experiments.py`.
- Verify chronological ordering is preserved end-to-end.
- Check dataset adequacy per split and identify too-small windows.

2. Detect leakage
- Trace reward calculation path in `TradingEnv`.
- Inspect label generation in `src/signal_analytics.py`.
- Inspect feature construction and shifting in `src/market_data.py`.
- Confirm no future information enters training/evaluation inputs incorrectly.

3. Evaluate metrics
- Audit actionable accuracy, win rate, cumulative returns, Sharpe/Sortino, and alpha vs QQQ.
- Flag metric contradictions (high accuracy + poor returns, unstable risk-adjusted metrics).
- Check validation vs test degradation and seed variance patterns.

4. Validate baselines
- Confirm buy-and-hold baseline is present and computed consistently.
- Confirm QQQ benchmark comparison is implemented correctly.
- Confirm no-trade baseline exists.
- Check simple strategy baselines (momentum and mean-reversion) when available.

5. Check robustness
- Inspect multi-seed behavior and sensitivity.
- Inspect promotion gates and champion selection logic.
- Check config-level stability assumptions and brittle settings.

6. Check reproducibility
- Verify model-to-config traceability.
- Verify snapshot completeness for reruns.
- Verify cache behavior and consistency across reruns.

7. Produce fixes with comparability guard
- Recommend minimal, testable corrections first.
- Distinguish correctness bug fixes from optional methodology upgrades.
- Include leaderboard comparability impact for every fix.

## Decision Logic
- If data split chronology is violated: classify as critical integrity issue.
- If leakage is only in evaluation labels and not training features: classify as documentation/semantics risk, not training leakage.
- If metric suite shows contradiction (accuracy high, returns low): prioritize actionability and calibration diagnostics.
- If seed variance is high: classify conclusions as unstable unless robustness thresholds are met.
- If baseline set is incomplete: classify outperformance claims as weak.
- If momentum/mean-reversion baselines are missing: flag as non-blocking unless the experiment explicitly claims superiority to simple timing strategies.
- If reproducibility artifacts are incomplete: classify reported champion metrics as non-verifiable.

## Required Output Format
Always structure output in this order:
- Audit verdict
- Trustworthy components
- Issues found
- Leakage risks
- Metric issues
- Missing baselines
- Reproducibility gaps
- Recommended fixes
- Leaderboard comparability impact (REQUIRED)

## Constraints
- Do not assume leakage without proof.
- Distinguish training-data usage from evaluation-only data usage.
- Avoid unnecessary rewrites.
- Call out any recommendation that changes historical leaderboard semantics.

## Quality Checks Before Finalizing
- Every finding references concrete file/function evidence.
- Leakage claims include proof path and affected stage (train/val/test).
- Metric critiques include observed contradiction and likely mechanism.
- Baseline checks explicitly state present/missing status.
- Recommended fixes are small, testable, and impact-ranked.
- Leaderboard comparability impact is present for each recommended fix.

## Example Tasks
- Audit `enrich_with_truth_labels()` for leakage.
- Verify train/val/test slicing in `src/experiments.py` is strictly chronological.
- Diagnose why high actionable accuracy does not convert to cumulative returns.

## Example Output Fragment
- Finding: Uses future returns correctly for evaluation only.
- Risk: None for training leakage.
- Recommendation: Keep behavior but document train-vs-eval boundary.

---
name: backtest-auditor
description: 'Audit trading evaluation pipelines across RL and Stage 1 signal-first pivot workflows for leakage, metric validity, robustness, and cross-experiment comparability. Use for src/experiments.py, src/trading_env.py, src/market_data.py, src/signal_analytics.py, and Stage 1 gate/trading artifacts to verify realistic, leakage-free, statistically defensible results.'
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

Also ensure Stage 1 pivot outputs are evaluated with the correct boundaries between supervised training, trading evaluation, and gate reporting.

## Default Focus Files
- `src/experiments.py`
- `src/trading_env.py`
- `src/signal_analytics.py`
- `src/market_data.py`
- `scripts/stage1_gate.py`
- `scripts/evaluate_stage1_trading.py`
- `scripts/inspect_stage1_data_health.py`
- Any tests, dashboards, or analytics files that consume evaluation outputs
- Stage 1 pivot artifacts when relevant:
	- `results/stage1/`
	- `results/stage1_confirmation_3seed/`
	- `logs/stage1_gate_report*.json`
	- `logs/stage1_trading_eval*.json`

## Core Audit Procedure
0. Confirm delivery mode
- Ask whether the user wants review-only output or implementation-inclusive output with patch proposals.

0.5. Identify evaluation family
- Determine whether the audit target is RL backtest evaluation or Stage 1 pivot evaluation.
- If both are present, keep integrity conclusions separate and compare only within the same artifact family.

1. Validate data splits
- Inspect train/validation/test separation logic and data slicing in `src/experiments.py`.
- Verify chronological ordering is preserved end-to-end.
- Check dataset adequacy per split and identify too-small windows.

2. Detect leakage
- Trace reward calculation path in `TradingEnv`.
- Inspect label generation in `src/signal_analytics.py`.
- Inspect feature construction and shifting in `src/market_data.py`.
- Confirm no future information enters training/evaluation inputs incorrectly.
- For Stage 1 pivot outputs, verify the supervised training split, thresholding logic, and trading-eval split do not leak future bars into the train-side model fit.

3. Evaluate metrics
- Audit actionable accuracy, win rate, cumulative returns, Sharpe/Sortino, and alpha vs QQQ.
- Flag metric contradictions (high accuracy + poor returns, unstable risk-adjusted metrics).
- Check validation vs test degradation and seed variance patterns.

4. Validate baselines
- Confirm buy-and-hold baseline is present and computed consistently.
- Confirm QQQ benchmark comparison is implemented correctly.
- Confirm no-trade baseline exists.
- Check simple strategy baselines (momentum and mean-reversion) when available.
- For Stage 1 pivot, confirm the flat baseline is present and the supervised policy is compared against flat before using buy-and-hold as secondary context.

5. Check robustness
- Inspect multi-seed behavior and sensitivity.
- Inspect promotion gates and champion selection logic.
- Check config-level stability assumptions and brittle settings.

6. Check reproducibility
- Verify model-to-config traceability.
- Verify snapshot completeness for reruns.
- Verify cache behavior and consistency across reruns.
- For Stage 1 pivot, verify each gate/trading report can be regenerated from the saved JSON outputs and the referenced baseline JSON files.

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
- If Stage 1 pivot gates disagree with trading eval or baseline JSON summaries, treat the discrepancy as an evaluation boundary issue before assuming a signal or leakage problem.

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
- Next proposed experiments or runs (if requested or justified)
- Leaderboard comparability impact (REQUIRED)

Run specification rule (MANDATORY):
- For each proposed run, include:
	- environment activation command (for example, `.venv` activation)
	- runner command
	- full relative script path when the runner is not in repository root (for example `scripts/runner_name.py`)
	- key args and expected output artifact path(s)
- Do not provide bare script names when the file lives in a subdirectory.

For Stage 1 pivot audits, also state whether the evidence supports:
- `signal_exists`
- `signal_weak`
- or an unresolved evaluation mismatch

## Constraints
- Do not assume leakage without proof.
- Distinguish training-data usage from evaluation-only data usage.
- Avoid unnecessary rewrites.
- Call out any recommendation that changes historical leaderboard semantics.
- Do not merge Stage 1 gate evidence with RL leaderboard evidence as if they are the same evaluation system.

## Quality Checks Before Finalizing
- Every finding references concrete file/function evidence.
- Leakage claims include proof path and affected stage (train/val/test).
- Metric critiques include observed contradiction and likely mechanism.
- Baseline checks explicitly state present/missing status.
- Recommended fixes are small, testable, and impact-ranked.
- Leaderboard comparability impact is present for each recommended fix.
- Stage 1 pivot and RL backtest conclusions are clearly separated when both appear in scope.

## Example Tasks
- Audit `enrich_with_truth_labels()` for leakage.
- Verify train/val/test slicing in `src/experiments.py` is strictly chronological.
- Diagnose why high actionable accuracy does not convert to cumulative returns.

## Example Output Fragment
- Finding: Uses future returns correctly for evaluation only.
- Risk: None for training leakage.
- Recommendation: Keep behavior but document train-vs-eval boundary.

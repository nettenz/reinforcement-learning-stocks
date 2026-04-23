# Stage 1 Gate Report

Generated at: 2026-04-20T01:02:06.866923+00:00
Verdict: signal_weak

## Baseline gate
Passed: False

- AAPL: False | linear h2 | val_r2=-0.0068 | test_r2=-0.0089
- AMD: False | linear h1 | val_r2=-0.0038 | test_r2=0.0070
- NVDA: False | linear h1 | val_r2=-0.0116 | test_r2=0.0019

## Trading gate
Passed: False

- AAPL: False | policy=supervised-linear-thresholded | supervised_return=-14.59% vs flat=0.00% vs buy_hold=-3.39% | win_rate=0.384 | trades=151
- NVDA: False | policy=supervised-linear-thresholded | supervised_return=-2.76% vs flat=0.00% vs buy_hold=23.43% | win_rate=0.421 | trades=145

## Interpretation
Stage 1 does not clear the gate: the supervised baseline remains below the threshold and/or fails to beat flat on test.

## Leaderboard comparability impact
None. This report only reads existing Stage 1 artifacts and writes a separate summary file.

# Session 2026-04-18 - Stage 1 Pivot Manual Steps

## Context

Current pivot focus remains Stage 1 signal proof before RL complexity.

Latest confirmation report:
- `logs/stage1_gate_report_3seed_confirmation_20260418-040921.json`
- Verdict: `signal_weak`
- Key blocker: NVDA underperformed flat benchmark on test.

Data-health diagnostics run:
- `logs/stage1_data_health_NVDA_h1.json`
- `logs/stage1_data_health_AAPL_h1.json`
- `logs/stage1_data_health_AMD_h1.json`

Interpretation:
- Data completeness appears healthy.
- Main issue appears to be generalization/regime-shift sensitivity and calibration, not obvious data corruption.

## Runner Refactor

Old Stage 1 combined runners removed:
- `run_stage1_3seed_confirmation.ps1`
- `run_stage1_baseline.ps1`

Old Stage 1 split-step runners removed:
- `run_stage1_step1_nvda_threshold_sweep.ps1`
- `run_stage1_step2_nvda_horizon_robustness.ps1`
- `run_stage1_step3_cross_ticker_sanity.ps1`

Current Stage 1 runner:
1. `run_stage1_step4_mixed_threshold_gate.ps1`

## Manual Run Order

From repo root in PowerShell:

```powershell
./run_stage1_step4_mixed_threshold_gate.ps1
```

Optional overrides:

```powershell
./run_stage1_step4_mixed_threshold_gate.ps1 -ThresholdAAPL 0.003 -ThresholdNVDA 0.001 -ThresholdAMD 0.001 -Horizon 1 -ModelType linear
```

## Quant Reporting Update

`src/quant_report.py` now supports a Stage 1 gate JSON mode:

```powershell
python src/quant_report.py --stage1-gate-json logs/stage1_gate_report_step4_<timestamp>.json --output-dir sessions --output-name stage1-step4-quant-report.md
```

This allows quant reporting to read the current Stage 1 implementation outputs directly.

## Next Decision Gate

After running the 3 steps, compare outputs in `logs/` and decide:
- If NVDA improves vs flat with stable behavior, proceed to confirmatory rerun.
- If NVDA still fails across threshold/horizon checks, pause tuning and move to feature/target redesign under Stage 1 rules.

#!/usr/bin/env pwsh
<#
.SYNOPSIS
Stage 1 Step 11: Rolling-Window Validation

Tests signal robustness across multiple market regimes using walk-forward
validation. Validates consistency before RL escalation.

.DESCRIPTION
This script runs rolling-window validation on the full data using sliding
train/val/test windows. It measures whether baseline models maintain
consistent performance across different market periods.

Approach:
1. Create 3-4 rolling windows with 60% train / 20% val / 20% test
2. Train linear + RF baselines on each window
3. Measure test R², returns, and win rates across windows
4. Compute stability metrics (mean, std, CV)
5. Generate comprehensive report

Output:
- JSON file: detailed results per window
- Markdown report: stability analysis and decision guidance

.EXAMPLE
.\run_stage1_step11_rolling_window_validation.ps1
#>

param(
    [string]$Mode = "default",
    [int]$NumWindows = 4
)

$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

# Setup paths
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
$SrcDir = Join-Path $ProjectRoot "src"
$LogsDir = Join-Path $ProjectRoot "logs"
$ResultsDir = Join-Path $ProjectRoot "results/stage1_rolling_window"

# Create directories
New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null

Write-Host "`n" + "="*80
Write-Host "STAGE 1 STEP 11: ROLLING-WINDOW VALIDATION"
Write-Host "="*80

Write-Host "`nMode: $Mode"
Write-Host "Windows: $NumWindows"

# Run rolling-window validation
Write-Host "`nStarting rolling-window validation..."
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$SrcDirEscaped = $SrcDir -replace '\\', '\\'

& $PythonExe -c @"
import sys
sys.path.insert(0, r'$SrcDir')

from rolling_window_validation import run_rolling_window_validation

config = {
    'train_size': 0.20,
    'val_size': 0.20,
    'test_size': 0.20,
    'slide_pct': 0.33,
}

results = run_rolling_window_validation(
    window_config=config,
    model_types=['linear', 'rf'],
    output_dir=r'$ResultsDir'
)

print('\n' + '='*80)
print('VALIDATION COMPLETE')
print('='*80)
print(f'\nWindow count: {len(results["windows"])}')
print(f'Aggregate stats:')
for model, stats in results['aggregate'].items():
    print(f'\n{model}:')
    print(f'  R² mean: {stats["test_r2"]["mean"]:+.4f}')
    print(f'  R² CV: {stats["test_r2"]["cv"]:.3f}')
    print(f'  Return mean: {stats["test_return"]["mean"]:+.4f}')
    print(f'  Win rate mean: {stats["test_win_rate"]["mean"]:.1%}')
"@

if ($LASTEXITCODE -ne 0) {
    Write-Error "Rolling-window validation failed"
    exit 1
}

Write-Host "`n✓ Rolling-window validation complete"
Write-Host "  Results: $ResultsDir"

# Summarize findings
Write-Host "`n" + "-"*80
Write-Host "NEXT STEPS"
Write-Host "-"*80
Write-Host @"
1. Review generated report: results/stage1_rolling_window/rolling_window_report_*.md
2. Check aggregate statistics for signal stability
3. Decision point:
   ✓ If R² CV < 1.0 AND mean > 0.01 → Signal robust, proceed to RL (Option B)
   ✗ If R² CV > 1.0 OR mean ≤ 0.01 → Need feature engineering before RL
   ✗ If win_rate ≈ 50% → Trading success may be random, investigate further
"@

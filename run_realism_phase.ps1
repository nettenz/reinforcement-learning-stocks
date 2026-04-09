#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Realism Phase Batch" -ForegroundColor Green
Write-Host "3-arm realism validation: control / realistic / stress" -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$timesteps = "20000"
$device = "cuda"
$entCoef = "0.10"
$executionMode = "next_bar"

Write-Host "Fixed controls: ent_coef=$entCoef, mode=sharpe, dir_scale=0.35, pnl_scale=0.00" -ForegroundColor DarkYellow
Write-Host "Seeds: $seeds" -ForegroundColor DarkYellow
Write-Host ""

function Invoke-RealismArm {
    param(
        [Parameter(Mandatory = $true)] [string]$RunLabel,
        [Parameter(Mandatory = $true)] [double]$SpreadBps,
        [Parameter(Mandatory = $true)] [double]$SlippageBps,
        [Parameter(Mandatory = $true)] [bool]$IgnoreRewardCosts
    )

    $args = @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--learning-rates", "0.0003",
        "--gammas", "0.99",
        "--ent-coefs", $entCoef,
        "--threshold", "0.002",
        "--horizon", "1",
        "--transaction-cost-rate", "0.001",
        "--trade-penalty", "0.05",
        "--execution-mode", $executionMode,
        "--spread-bps", "$SpreadBps",
        "--slippage-bps", "$SlippageBps",
        "--reward-mode", "sharpe",
        "--reward-return-scale", "1.0",
        "--reward-pnl-scale", "0.00",
        "--reward-direction-scale", "0.35",
        "--reward-hold-penalty-scale", "0.10",
        "--reward-drawdown-penalty-scale", "0.10",
        "--reward-action-bonus-scale", "0.02",
        "--reward-turnover-penalty-scale", "0.05",
        "--reward-clip", "1.0",
        "--max-weight-delta-per-step", "0.25",
        "--append",
        "--run-label", $RunLabel
    )

    if ($IgnoreRewardCosts) {
        $args += "--reward-ignore-transaction-cost"
    }
    else {
        $args += "--no-reward-ignore-transaction-cost"
    }

    Write-Host "Running $RunLabel (spread=$SpreadBps, slippage=$SlippageBps, ignore_reward_costs=$IgnoreRewardCosts)" -ForegroundColor Cyan
    Write-Host "  Command: $pythonExe $($args -join ' ')" -ForegroundColor DarkGray

    & $pythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "Arm failed: $RunLabel"
    }

    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""
}

# Arm 1: Control (optimistic baseline)
Invoke-RealismArm -RunLabel "nvda-realism-phase-control-ent010" -SpreadBps 0.0 -SlippageBps 0.0 -IgnoreRewardCosts $true

# Arm 2: Realistic fills + cost-aware reward
Invoke-RealismArm -RunLabel "nvda-realism-phase-realistic-ent010" -SpreadBps 1.0 -SlippageBps 1.0 -IgnoreRewardCosts $false

# Arm 3: Stress realism
Invoke-RealismArm -RunLabel "nvda-realism-phase-stress-ent010" -SpreadBps 2.0 -SlippageBps 2.0 -IgnoreRewardCosts $false

Write-Host "Computing quick cohort comparison..." -ForegroundColor Yellow
$leaderboardPath = Join-Path $PSScriptRoot "data\experiment_leaderboard.csv"

$rows = Import-Csv $leaderboardPath | Where-Object { $_.run_label -match "^nvda-realism-phase-(control|realistic|stress)-ent010$" }
if ($rows.Count -eq 0) {
    Write-Host "No realism rows found for quick summary." -ForegroundColor Red
}
else {
    $summary = $rows |
        Group-Object run_label |
        ForEach-Object {
            $g = $_.Group
            [PSCustomObject]@{
                arm = $_.Name
                count = $g.Count
                mean_test_alpha = [double](($g | Measure-Object -Property test_alpha_vs_qqq -Average).Average)
                mean_test_sharpe = [double](($g | Measure-Object -Property test_sharpe_ratio -Average).Average)
                mean_test_return = [double](($g | Measure-Object -Property test_cumulative_return -Average).Average)
                mean_test_cv = [double](($g | Measure-Object -Property test_return_cv_by_config -Average).Average)
            }
        } |
        Sort-Object arm

    Write-Host ""
    Write-Host "Quick realism summary:" -ForegroundColor Green
    $summary | Format-Table -AutoSize
}

Write-Host ""
Write-Host "Realism phase complete." -ForegroundColor Green
Write-Host "Next: $pythonExe src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name realism-phase-analysis.md" -ForegroundColor DarkYellow

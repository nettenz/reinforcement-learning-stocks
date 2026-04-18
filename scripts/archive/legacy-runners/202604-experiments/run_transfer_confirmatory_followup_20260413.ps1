#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $RepoRoot

$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $RepoRoot ".venv\Scripts\Activate.ps1")

Write-Host "Transfer Confirmatory Follow-Up Batch (2026-04-13)" -ForegroundColor Green
Write-Host "Purpose: Recheck NVDA baseline on fresh seeds and confirm transfer on AAPL and AMD." -ForegroundColor Yellow

$device = "cuda"
$freshSeeds = "11,22,33,44,55"
$timesteps = "20000"

$common = @(
    "src/experiments.py",
    "--device", $device,
    "--seeds", $freshSeeds,
    "--timesteps", $timesteps,
    "--learning-rates", "0.0003",
    "--gammas", "0.99",
    "--ent-coefs", "0.07",
    "--threshold", "0.002",
    "--horizon", "1",
    "--transaction-cost-rate", "0.001",
    "--trade-penalty", "0.05",
    "--execution-mode", "next_bar",
    "--spread-bps", "1.0",
    "--slippage-bps", "1.0",
    "--max-weight-delta-per-step", "0.25",
    "--reward-mode", "sortino",
    "--rolling-reward-window", "100",
    "--reward-epsilon", "1e-06",
    "--reward-return-scale", "1.3",
    "--reward-direction-scale", "0.55",
    "--reward-hold-penalty-scale", "0.1",
    "--reward-drawdown-penalty-scale", "0.04",
    "--reward-action-bonus-scale", "0.007",
    "--reward-turnover-penalty-scale", "0.04",
    "--reward-pnl-scale", "0.0",
    "--reward-clip", "1.0",
    "--no-reward-ignore-transaction-cost",
    "--n-envs", "4",
    "--append"
)

function Invoke-TransferRun {
    param(
        [Parameter(Mandatory = $true)] [string]$Ticker,
        [Parameter(Mandatory = $true)] [string]$RunLabel
    )

    $commandArgs = $common + @(
        "--ticker", $Ticker,
        "--run-label", $RunLabel
    )

    Write-Host "Running $RunLabel" -ForegroundColor Cyan
    & $pythonExe @commandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment failed: $RunLabel"
    }

    Write-Host "Completed $RunLabel" -ForegroundColor Green
    Write-Host ""
}

# 1) Recheck the NVDA baseline with fresh seeds.
Invoke-TransferRun `
    -Ticker "nvda" `
    -RunLabel "nvda-baseline-recheck-nextbar-20k"

# 2) Confirm AAPL transfer under the same baseline settings.
Invoke-TransferRun `
    -Ticker "aapl" `
    -RunLabel "aapl-transfer-confirm-nextbar-20k"

# 3) Confirm AMD transfer under the same baseline settings.
Invoke-TransferRun `
    -Ticker "amd" `
    -RunLabel "amd-transfer-confirm-nextbar-20k"

Write-Host "Batch complete." -ForegroundColor Green
Write-Host "Next: .venv/Scripts/python.exe src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name transfer-confirmatory-analysis-20260413.md" -ForegroundColor DarkYellow

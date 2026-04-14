#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

# Source the virtual environment activation script
. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "--- April 10, 2026: Sortino Calibration Sweep ---" -ForegroundColor Green
Write-Host "Target: Optimize Sortino reward mode for stable test-period alpha." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$timesteps = "20000"
$device = "cuda"
$executionMode = "next_bar"
$entCoef = "0.07"
$turnoverPenalty = "0.10"
$ddPenalty = "0.15"

# --- Phase 1: Sortino Window Sensitivity ---
# Testing if longer/shorter windows for Sortino calculation improve signal stability.
Write-Host "`n[Phase 1] Sortino Window Sensitivity Sweep" -ForegroundColor Cyan
$windows = @("50", "100", "200")

foreach ($window in $windows) {
    $run_label = "nvda-sortino-window-$window"
    Write-Host "  Running: $run_label (window=$window)" -ForegroundColor DarkCyan

    $args = @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--ent-coefs", $entCoef,
        "--reward-turnover-penalty-scale", $turnoverPenalty,
        "--reward-drawdown-penalty-scale", $ddPenalty,
        "--execution-mode", $executionMode,
        "--reward-mode", "sortino",
        "--rolling-reward-window", $window,
        "--append",
        "--run-label", $run_label
    )

    & $pythonExe @args
}

# --- Phase 2: Sortino Scale Calibration ---
# Testing if higher return scaling helps the Sortino objective overcome penalties.
Write-Host "`n[Phase 2] Sortino Scale Calibration (window=100)" -ForegroundColor Cyan
$scales = @("0.8", "1.0", "1.2")
$fixedWindow = "100"

foreach ($scale in $scales) {
    $run_label = "nvda-sortino-scale-$scale"
    Write-Host "  Running: $run_label (scale=$scale)" -ForegroundColor DarkCyan

    $args = @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--ent-coefs", $entCoef,
        "--reward-turnover-penalty-scale", $turnoverPenalty,
        "--reward-drawdown-penalty-scale", $ddPenalty,
        "--execution-mode", $executionMode,
        "--reward-mode", "sortino",
        "--rolling-reward-window", $fixedWindow,
        "--reward-return-scale", $scale,
        "--append",
        "--run-label", $run_label
    )

    & $pythonExe @args
}

Write-Host "`n--- Sortino Calibration Sweep Complete ---" -ForegroundColor Green
Write-Host "Check data/experiment_leaderboard.csv for the latest rankings." -ForegroundColor Gray

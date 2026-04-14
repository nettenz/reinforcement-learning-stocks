#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

# Source the virtual environment activation script
. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "--- April 10, 2026: NVDA Sortino Finalist Run ---" -ForegroundColor Green
Write-Host "Target: Confirm promotion readiness with 50-seed / 20k-timestep rigor." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = (1..50 -join ",")
$timesteps = "20000"
$device = "cuda"
$executionMode = "next_bar"
$entCoef = "0.07"
$turnoverPenalty = "0.10"
$ddPenalty = "0.15"
$window = "100"
$scale = "1.2"
$run_label = "nvda-finalist-sortino-20k"

Write-Host "`n[Action] Starting 50-seed Finalist Batch..." -ForegroundColor Cyan
Write-Host "  Parameters: Window=$window, Scale=$scale, Ent=$entCoef, Timesteps=$timesteps" -ForegroundColor DarkCyan

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
    "--reward-return-scale", $scale,
    "--append",
    "--run-label", $run_label
)

& $pythonExe @args

Write-Host "`n--- Finalist Run Complete ---" -ForegroundColor Green
Write-Host "Check the 'Experiment Insights' page in the dashboard to analyze the 50-seed distribution." -ForegroundColor Gray

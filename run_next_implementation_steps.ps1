#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Next Implementation Steps Launcher" -ForegroundColor Green
Write-Host "Priority order: realism baseline -> turnover realism -> short-side realism -> sizing/debounce review -> proxy semantics" -ForegroundColor Yellow
Write-Host ""

Write-Host "Step 1: run the current realism baseline batch." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "run_realism_phase.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Realism baseline batch failed."
}

Write-Host ""
Write-Host "Step 2: generate the post-run report." -ForegroundColor Cyan
& $pythonExe @(
    "src/quant_report.py",
    "--input", "data/experiment_leaderboard.csv",
    "--output-dir", "sessions",
    "--output-name", "next-implementation-steps-analysis.md"
)
if ($LASTEXITCODE -ne 0) {
    throw "Report generation failed."
}

Write-Host ""
Write-Host "Next implementation steps launcher complete." -ForegroundColor Green
Write-Host "Reference: sessions/next_implementation_steps_2026-04-06.md" -ForegroundColor DarkYellow
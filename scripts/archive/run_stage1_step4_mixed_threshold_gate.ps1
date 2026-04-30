#!/usr/bin/env pwsh

param(
    [string]$ModelType = "linear",
    [int]$Horizon = 1,
    [string]$ThresholdAAPL = "0.003",
    [string]$ThresholdNVDA = "0.001",
    [string]$ThresholdAMD = "0.001"
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location -Path $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
} else {
    $PythonCmd = "python"
}

$LogsDir = "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$Runs = @(
    @{ ticker = "AAPL"; threshold = $ThresholdAAPL },
    @{ ticker = "NVDA"; threshold = $ThresholdNVDA },
    @{ ticker = "AMD"; threshold = $ThresholdAMD }
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Stage 1 Step 4: Mixed Threshold + Gate" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "Model: $ModelType"
Write-Host "Horizon: $Horizon"
Write-Host "Thresholds: AAPL=$ThresholdAAPL, NVDA=$ThresholdNVDA, AMD=$ThresholdAMD"
Write-Host ""

$total = $Runs.Count
$i = 0

foreach ($run in $Runs) {
    $i++
    $ticker = [string]$run.ticker
    $threshold = [string]$run.threshold
    $safeThreshold = $threshold.Replace('.', 'p')
    $outputPath = "logs/stage1_trading_eval_${ticker}_${ModelType}_${Horizon}h_thr${safeThreshold}_step4.json"

    Write-Host "[$i/$total] ticker=$ticker threshold=$threshold -> $outputPath" -ForegroundColor Green

    & $PythonCmd "scripts/evaluate_stage1_trading.py" `
        "--tickers" $ticker `
        "--horizon" $Horizon `
        "--model-type" $ModelType `
        "--threshold" $threshold `
        "--output" $outputPath

    if ($LASTEXITCODE -ne 0) {
        throw "Step 4 trading eval failed for ticker=$ticker"
    }
}

$gateJson = "logs/stage1_gate_report_step4_${Timestamp}.json"
$gateMd = "logs/stage1_gate_report_step4_${Timestamp}.md"

Write-Host "`nRunning consolidated Stage 1 gate for Step 4 outputs..." -ForegroundColor Cyan
& $PythonCmd "scripts/stage1_gate.py" `
    "--results-dir" "results/stage1_confirmation_3seed" `
    "--trading-eval-glob" "logs/stage1_trading_eval_*_step4.json" `
    "--output-json" $gateJson `
    "--output-md" $gateMd

if ($LASTEXITCODE -ne 0) {
    throw "Step 4 gate evaluation failed"
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 4 Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Gate JSON: $gateJson" -ForegroundColor Green
Write-Host "Gate MD:   $gateMd" -ForegroundColor Green

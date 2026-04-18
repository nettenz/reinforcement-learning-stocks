#!/usr/bin/env pwsh

param(
    [string]$Tickers = "AAPL,NVDA,AMD",
    [string]$ModelTypes = "linear,rf",
    [int]$Horizon = 1,
    [string]$Thresholds = "0.0005,0.0010,0.0020"
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

$ResultsDir = Join-Path $RepoRoot "results\stage1_step5"
$LogsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null
}
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TickerList = $Tickers.Split(',') | ForEach-Object { $_.Trim().ToUpper() } | Where-Object { $_ }
$ModelTypeList = $ModelTypes.Split(',') | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ }
$ThresholdList = $Thresholds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Stage 1 Step 5: Next Diagnostics Batch" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "Tickers: $($TickerList -join ', ')"
Write-Host "Model types: $($ModelTypeList -join ', ')"
Write-Host "Horizon: $Horizon"
Write-Host "Thresholds: $($ThresholdList -join ', ')"
Write-Host "Results dir: $ResultsDir"
Write-Host ""

foreach ($ticker in $TickerList) {
    foreach ($modelType in $ModelTypeList) {
        $baselineArgs = @(
            "src/supervised_baseline.py",
            "--ticker", $ticker,
            "--horizon", $Horizon,
            "--model-type", $modelType,
            "--output-dir", $ResultsDir,
            "--seed", "42"
        )

        Write-Host "Running baseline: ticker=$ticker model=$modelType horizon=$Horizon" -ForegroundColor Green
        & $PythonCmd @baselineArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Baseline run failed for ticker=$ticker modelType=$modelType"
        }
    }
}

foreach ($modelType in $ModelTypeList) {
    foreach ($threshold in $ThresholdList) {
        $safeThreshold = $threshold.Replace('.', 'p')
        $tradingOutput = Join-Path $LogsDir "stage1_trading_eval_step5_${modelType}_thr${safeThreshold}_${Timestamp}.json"
        $tradingArgs = @(
            "scripts/evaluate_stage1_trading.py",
            "--tickers", ($TickerList -join ','),
            "--horizon", $Horizon,
            "--model-type", $modelType,
            "--threshold", $threshold,
            "--output", $tradingOutput
        )

        Write-Host "Running trading eval: model=$modelType threshold=$threshold" -ForegroundColor Green
        & $PythonCmd @tradingArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Trading evaluation failed for modelType=$modelType threshold=$threshold"
        }
    }
}

$gateJson = Join-Path $LogsDir "stage1_gate_report_step5_${Timestamp}.json"
$gateMd = Join-Path $LogsDir "stage1_gate_report_step5_${Timestamp}.md"

Write-Host "`nRunning consolidated Stage 1 gate for Step 5 outputs..." -ForegroundColor Cyan
& $PythonCmd "scripts/stage1_gate.py" `
    "--results-dir" $ResultsDir `
    "--trading-eval-glob" "logs/stage1_trading_eval_step5_*.json" `
    "--output-json" $gateJson `
    "--output-md" $gateMd

if ($LASTEXITCODE -ne 0) {
    throw "Step 5 gate evaluation failed"
}

$reportOutputName = "stage1-step5-quant-report.md"
Write-Host "`nGenerating quant report..." -ForegroundColor Cyan
& $PythonCmd "src/quant_report.py" `
    "--stage1-gate-json" $gateJson `
    "--output-dir" "sessions" `
    "--output-name" $reportOutputName

if ($LASTEXITCODE -ne 0) {
    throw "Step 5 quant report generation failed"
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 5 Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Gate JSON: $gateJson" -ForegroundColor Green
Write-Host "Gate MD:   $gateMd" -ForegroundColor Green
Write-Host "Report:    sessions/$reportOutputName" -ForegroundColor Green
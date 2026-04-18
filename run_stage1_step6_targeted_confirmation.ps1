#!/usr/bin/env pwsh

param(
    [string]$Tickers = "AAPL,NVDA,AMD",
    [string]$ModelTypes = "linear,rf",
    [int]$Horizon = 1,
    [string]$ThresholdAAPL = "0.0030",
    [string]$ThresholdNVDA = "0.0010",
    [string]$ThresholdAMD = "0.0010",
    [string]$ThresholdDeltas = "-0.0005,0.0000,0.0005",
    [switch]$IncludeNews
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

$ResultsDir = Join-Path $RepoRoot "results\stage1_step6"
$LogsDir = Join-Path $RepoRoot "logs"
$SessionsDir = Join-Path $RepoRoot "sessions"
foreach ($dir in @($ResultsDir, $LogsDir, $SessionsDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

$InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TickerList = $Tickers.Split(',') | ForEach-Object { $_.Trim().ToUpper() } | Where-Object { $_ }
$ModelTypeList = $ModelTypes.Split(',') | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ }
$DeltaList = $ThresholdDeltas.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ } | ForEach-Object { [double]::Parse($_, $InvariantCulture) }

if ($TickerList.Count -eq 0) {
    throw "No tickers were provided."
}
if ($ModelTypeList.Count -eq 0) {
    throw "No model types were provided."
}
if ($DeltaList.Count -eq 0) {
    throw "No threshold deltas were provided."
}

$BaseThresholdMap = @{
    "AAPL" = [double]::Parse($ThresholdAAPL, $InvariantCulture)
    "NVDA" = [double]::Parse($ThresholdNVDA, $InvariantCulture)
    "AMD"  = [double]::Parse($ThresholdAMD, $InvariantCulture)
}

function Invoke-CheckedPython {
    param(
        [string[]]$PythonArgs,
        [string]$FailureMessage
    )

    & $PythonCmd @PythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Get-ThresholdGrid {
    param(
        [double]$BaseThreshold,
        [double[]]$Deltas
    )

    $raw = @()
    foreach ($delta in $Deltas) {
        $candidate = $BaseThreshold + $delta
        if ($candidate -lt 0.0) {
            $candidate = 0.0
        }
        $raw += [Math]::Round($candidate, 6)
    }

    return $raw | Sort-Object -Unique
}

function Format-Number {
    param([double]$Value)
    return [string]::Format($InvariantCulture, "{0:0.0000}", $Value)
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Stage 1 Step 6: Targeted Confirmation Batch" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "Tickers: $($TickerList -join ', ')"
Write-Host "Model types: $($ModelTypeList -join ', ')"
Write-Host "Horizon: $Horizon"
Write-Host "Include news: $IncludeNews"
$formattedDeltas = $DeltaList | ForEach-Object { Format-Number $_ }
Write-Host "Threshold deltas: $($formattedDeltas -join ', ')"
Write-Host "Results dir: $ResultsDir"
Write-Host ""

$ThresholdGridByTicker = @{}
foreach ($ticker in $TickerList) {
    if (-not $BaseThresholdMap.ContainsKey($ticker)) {
        throw "No base threshold configured for ticker '$ticker'. Add a parameter/map entry first."
    }
    $ThresholdGridByTicker[$ticker] = Get-ThresholdGrid -BaseThreshold $BaseThresholdMap[$ticker] -Deltas $DeltaList
    $formatted = $ThresholdGridByTicker[$ticker] | ForEach-Object { Format-Number $_ }
    Write-Host "Threshold grid [$ticker]: $($formatted -join ', ')"
}
Write-Host ""

$PhaseCount = 3
$CurrentPhase = 0

# Phase 1: Train supervised baselines for each ticker/model pair.
$CurrentPhase++
$phaseName = "Phase 1/4 - Baseline training"
$baselineTotal = $TickerList.Count * $ModelTypeList.Count
$baselineDone = 0
Write-Progress -Id 1 -Activity "Stage 1 Step 6" -Status $phaseName -PercentComplete (($CurrentPhase - 1) / $PhaseCount * 100)

foreach ($ticker in $TickerList) {
    foreach ($modelType in $ModelTypeList) {
        $baselineDone++
        $pct = [Math]::Floor(($baselineDone / [double]$baselineTotal) * 100)
        $status = "[$baselineDone/$baselineTotal] ticker=$ticker model=$modelType"
        Write-Progress -Id 2 -ParentId 1 -Activity $phaseName -Status $status -PercentComplete $pct

        $args = @(
            "src/supervised_baseline.py",
            "--ticker", $ticker,
            "--horizon", $Horizon,
            "--model-type", $modelType,
            "--output-dir", $ResultsDir,
            "--seed", "42"
        )

        if ($IncludeNews) {
            $args += "--use-news"
        }

        Invoke-CheckedPython -PythonArgs $args -FailureMessage "Baseline run failed for ticker=$ticker model=$modelType"
    }
}
Write-Progress -Id 2 -Activity $phaseName -Completed

# Phase 2: Local threshold sweep for each ticker/model pair.
$CurrentPhase++
$phaseName = "Phase 2/4 - Trading eval threshold sweep"
$sweepTotal = 0
foreach ($ticker in $TickerList) {
    $sweepTotal += ($ModelTypeList.Count * $ThresholdGridByTicker[$ticker].Count)
}
$sweepDone = 0
Write-Progress -Id 1 -Activity "Stage 1 Step 6" -Status $phaseName -PercentComplete (($CurrentPhase - 1) / $PhaseCount * 100)

foreach ($ticker in $TickerList) {
    foreach ($modelType in $ModelTypeList) {
        foreach ($threshold in $ThresholdGridByTicker[$ticker]) {
            $sweepDone++
            $thresholdText = Format-Number $threshold
            $pct = [Math]::Floor(($sweepDone / [double]$sweepTotal) * 100)
            $status = "[$sweepDone/$sweepTotal] ticker=$ticker model=$modelType threshold=$thresholdText"
            Write-Progress -Id 2 -ParentId 1 -Activity $phaseName -Status $status -PercentComplete $pct

            $safeThreshold = $thresholdText.Replace('.', 'p')
            $outputPath = Join-Path $LogsDir "stage1_trading_eval_step6_${ticker}_${modelType}_h${Horizon}_thr${safeThreshold}_${Timestamp}.json"

            $args = @(
                "scripts/evaluate_stage1_trading.py",
                "--tickers", $ticker,
                "--horizon", $Horizon,
                "--model-type", $modelType,
                "--threshold", $thresholdText,
                "--output", $outputPath
            )

            if ($IncludeNews) {
                $args += "--include-news"
            }

            Invoke-CheckedPython -PythonArgs $args -FailureMessage "Trading eval failed for ticker=$ticker model=$modelType threshold=$thresholdText"
        }
    }
}
Write-Progress -Id 2 -Activity $phaseName -Completed

# Phase 3: Consolidated Stage 1 gate for this Step 6 batch.
$CurrentPhase++
$phaseName = "Phase 3/4 - Consolidated gate"
Write-Progress -Id 1 -Activity "Stage 1 Step 6" -Status $phaseName -PercentComplete (($CurrentPhase - 1) / $PhaseCount * 100)
Write-Progress -Id 2 -ParentId 1 -Activity $phaseName -Status "Running stage1_gate.py" -PercentComplete 35

$gateJson = Join-Path $LogsDir "stage1_gate_report_step6_${Timestamp}.json"
$gateMd = Join-Path $LogsDir "stage1_gate_report_step6_${Timestamp}.md"
$tradingGlob = "logs/stage1_trading_eval_step6_*_${Timestamp}.json"

$gateArgs = @(
    "scripts/stage1_gate.py",
    "--results-dir", $ResultsDir,
    "--trading-eval-glob", $tradingGlob,
    "--output-json", $gateJson,
    "--output-md", $gateMd
)
Invoke-CheckedPython -PythonArgs $gateArgs -FailureMessage "Step 6 gate evaluation failed"
Write-Progress -Id 2 -ParentId 1 -Activity $phaseName -Status "Gate report complete" -PercentComplete 100
Write-Progress -Id 2 -Activity $phaseName -Completed

Write-Progress -Id 1 -Activity "Stage 1 Step 6" -Completed

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 6 Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Gate JSON: $gateJson" -ForegroundColor Green
Write-Host "Gate MD:   $gateMd" -ForegroundColor Green

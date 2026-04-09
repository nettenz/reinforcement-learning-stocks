#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Reward Calibration (Phased)" -ForegroundColor Green
Write-Host "Phase 1 -> Phase 2 with automatic winner carry-forward" -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$timesteps = "20000"
$device = "cuda"
$rewardMode = "sharpe"
$executionMode = "next_bar"
$entCoef = "0.10"

Write-Host "Fixed controls: ent_coef=$entCoef, dir_scale=0.35, reward_mode=sharpe" -ForegroundColor DarkYellow
Write-Host "Seeds: $seeds" -ForegroundColor DarkYellow
Write-Host ""

function Invoke-RewardArm {
    param(
        [Parameter(Mandatory = $true)] [string]$RunLabel,
        [Parameter(Mandatory = $true)] [string]$Pnl,
        [Parameter(Mandatory = $true)] [string]$Turnover,
        [Parameter(Mandatory = $true)] [string]$Drawdown,
        [string]$ReturnScale = "1.0"
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
        "--spread-bps", "0.0",
        "--slippage-bps", "0.0",
        "--reward-mode", $rewardMode,
        "--reward-return-scale", $ReturnScale,
        "--reward-pnl-scale", $Pnl,
        "--reward-direction-scale", "0.35",
        "--reward-hold-penalty-scale", "0.10",
        "--reward-drawdown-penalty-scale", $Drawdown,
        "--reward-action-bonus-scale", "0.02",
        "--reward-turnover-penalty-scale", $Turnover,
        "--reward-clip", "1.0",
        "--reward-ignore-transaction-cost",
        "--max-weight-delta-per-step", "0.25",
        "--append",
        "--run-label", $RunLabel
    )

    Write-Host "  Running: $pythonExe $($args -join ' ')" -ForegroundColor DarkGray
    & $pythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "Arm failed: $RunLabel"
    }
}

function Get-Phase1WinnerPnl {
    param(
        [Parameter(Mandatory = $true)] [string]$LeaderboardPath,
        [Parameter(Mandatory = $true)] [string]$ControlLabel,
        [Parameter(Mandatory = $true)] [string]$PnlLabel
    )

    if (-not (Test-Path $LeaderboardPath)) {
        throw "Leaderboard not found at $LeaderboardPath"
    }

    $rows = Import-Csv $LeaderboardPath | Where-Object { $_.run_label -eq $ControlLabel -or $_.run_label -eq $PnlLabel }
    if (-not $rows -or $rows.Count -eq 0) {
        throw "No Phase 1 rows found for labels: $ControlLabel / $PnlLabel"
    }

    $groups = $rows | Group-Object run_label | ForEach-Object {
        $label = $_.Name
        $vals = $_.Group
        [PSCustomObject]@{
            run_label = $label
            mean_alpha = ($vals | Measure-Object -Property test_alpha_vs_qqq -Average).Average
            mean_cv = ($vals | Measure-Object -Property test_return_cv_by_config -Average).Average
            mean_sharpe = ($vals | Measure-Object -Property test_sharpe_ratio -Average).Average
        }
    }

    $winner = $groups |
        Sort-Object @{Expression = { [double]$_.mean_alpha }; Descending = $true},
                    @{Expression = { [double]$_.mean_cv }; Descending = $false},
                    @{Expression = { [double]$_.mean_sharpe }; Descending = $true} |
        Select-Object -First 1

    if ($winner.run_label -eq $ControlLabel) {
        return "0.00"
    }
    return "0.05"
}

Write-Host "Phase 1: baseline control vs micro P&L change" -ForegroundColor Cyan
$phase1Control = "nvda-reward-phase1-control-ent010"
$phase1Pnl = "nvda-reward-phase1-pnl005-ent010"

Write-Host "Arm: control (pnl=0.00, turnover=0.05, dd=0.10)" -ForegroundColor DarkCyan
Invoke-RewardArm -RunLabel $phase1Control -Pnl "0.00" -Turnover "0.05" -Drawdown "0.10"
Write-Host "  OK" -ForegroundColor Green
Write-Host ""

Write-Host "Arm: micro-pnl (pnl=0.05, turnover=0.05, dd=0.10)" -ForegroundColor DarkCyan
Invoke-RewardArm -RunLabel $phase1Pnl -Pnl "0.05" -Turnover "0.05" -Drawdown "0.10"
Write-Host "  OK" -ForegroundColor Green
Write-Host ""

$leaderboardPath = Join-Path $PSScriptRoot "data\experiment_leaderboard.csv"
$winnerPnl = Get-Phase1WinnerPnl -LeaderboardPath $leaderboardPath -ControlLabel $phase1Control -PnlLabel $phase1Pnl
Write-Host "Phase 1 winner pnl scale: $winnerPnl" -ForegroundColor Yellow
Write-Host ""

Write-Host "Phase 2: turnover vs drawdown rebalance around Phase 1 winner" -ForegroundColor Cyan

$phase2Turnover = "nvda-reward-phase2-turnoverplus-ent010"
$phase2Drawdown = "nvda-reward-phase2-drawdownplus-ent010"

Write-Host "Arm: turnover+ (pnl=$winnerPnl, turnover=0.06, dd=0.10)" -ForegroundColor DarkCyan
Invoke-RewardArm -RunLabel $phase2Turnover -Pnl $winnerPnl -Turnover "0.06" -Drawdown "0.10"
Write-Host "  OK" -ForegroundColor Green
Write-Host ""

Write-Host "Arm: drawdown+ (pnl=$winnerPnl, turnover=0.05, dd=0.12)" -ForegroundColor DarkCyan
Invoke-RewardArm -RunLabel $phase2Drawdown -Pnl $winnerPnl -Turnover "0.05" -Drawdown "0.12"
Write-Host "  OK" -ForegroundColor Green
Write-Host ""

Write-Host "Reward calibration phases complete." -ForegroundColor Green
Write-Host "Next: .\.venv\Scripts\python.exe src\quant_report.py --input data\experiment_leaderboard.csv --output-dir sessions --output-name reward-phase1-phase2-analysis.md"
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

$ticker = "nvda"
$phase1Seeds = "7,13,21,42,84"
$phase3Seeds = "34,55,89,144,233"
$timesteps = "20000"
$learningRates = "0.0003"
$gammas = "0.99"
$threshold = "0.002"
$transactionCostRate = "0.001"
$tradePenalty = "0.05"
$rewardReturnScale = "1.0"
$rewardDirectionScale = "0.35"
$rewardHoldPenaltyScale = "0.10"
$rewardDrawdownPenaltyScale = "0.10"
$rewardActionBonusScale = "0.02"
$rewardTurnoverPenaltyScale = "0.05"
$rewardClip = "1.0"
$maxWeightDeltaPerStep = "0.25"
$leaderboardPath = Join-Path $PSScriptRoot "data\experiment_leaderboard.csv"

function Invoke-Experiment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RunLabel,
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    Write-Host "Running: $pythonExe $($Args -join ' ')" -ForegroundColor Yellow
    & $pythonExe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment failed: $RunLabel"
    }
}

function New-BaseArgs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Seeds,
        [Parameter(Mandatory = $true)]
        [string]$EntCoef,
        [Parameter(Mandatory = $true)]
        [string]$ActionBonus,
        [Parameter(Mandatory = $true)]
        [string]$RunLabel
    )

    return @(
        "src/experiments.py",
        "--ticker", $ticker,
        "--seeds", $Seeds,
        "--timesteps", $timesteps,
        "--learning-rates", $learningRates,
        "--gammas", $gammas,
        "--ent-coefs", $EntCoef,
        "--threshold", $threshold,
        "--horizon", "1",
        "--transaction-cost-rate", $transactionCostRate,
        "--trade-penalty", $tradePenalty,
        "--execution-mode", "next_bar",
        "--spread-bps", "0.0",
        "--slippage-bps", "0.0",
        "--reward-mode", "sharpe",
        "--reward-return-scale", $rewardReturnScale,
        "--reward-direction-scale", $rewardDirectionScale,
        "--reward-hold-penalty-scale", $rewardHoldPenaltyScale,
        "--reward-drawdown-penalty-scale", $rewardDrawdownPenaltyScale,
        "--reward-action-bonus-scale", $ActionBonus,
        "--reward-turnover-penalty-scale", $rewardTurnoverPenaltyScale,
        "--reward-clip", $rewardClip,
        "--reward-ignore-transaction-cost",
        "--max-weight-delta-per-step", $maxWeightDeltaPerStep,
        "--append",
        "--run-label", $RunLabel
    )
}

function Get-RunLabelMeanRankingScore {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RunLabel
    )

    if (-not (Test-Path $leaderboardPath)) {
        throw "Leaderboard not found at $leaderboardPath"
    }

    $rows = Import-Csv $leaderboardPath | Where-Object { $_.run_label -eq $RunLabel }
    if (-not $rows -or $rows.Count -eq 0) {
        return [double]::NegativeInfinity
    }

    $scores = $rows | ForEach-Object { [double]$_.ranking_score }
    return ($scores | Measure-Object -Average).Average
}

Write-Host "Starting NVDA experiment batch (entropy A/B -> guardrail ablation -> confirmatory replay)..." -ForegroundColor Cyan

# Phase 1: Entropy A/B at 20k (confirmatory)
$phase1RunLabels = @{}
foreach ($entCoef in @("0.02", "0.05")) {
    $runLabel = "nvda-exp1-entab-20k-ent$($entCoef -replace '\\.', '')"
    $phase1RunLabels[$entCoef] = $runLabel
    $args = New-BaseArgs -Seeds $phase1Seeds -EntCoef $entCoef -ActionBonus $rewardActionBonusScale -RunLabel $runLabel
    Invoke-Experiment -RunLabel $runLabel -Args $args
}

$ent02Score = Get-RunLabelMeanRankingScore -RunLabel $phase1RunLabels["0.02"]
$ent05Score = Get-RunLabelMeanRankingScore -RunLabel $phase1RunLabels["0.05"]
$winningEntCoef = if ($ent05Score -ge $ent02Score) { "0.05" } else { "0.02" }
Write-Host "Phase 1 winner: ent_coef=$winningEntCoef (mean ranking score comparison)" -ForegroundColor Magenta

# Phase 2: Collapse-guardrail ablation under winning entropy
foreach ($actionBonus in @("0.02", "0.05")) {
    $runLabel = "nvda-exp2-guardrail-20k-ent$($winningEntCoef -replace '\\.', '')-bonus$($actionBonus -replace '\\.', '')"
    $args = New-BaseArgs -Seeds $phase1Seeds -EntCoef $winningEntCoef -ActionBonus $actionBonus -RunLabel $runLabel
    Invoke-Experiment -RunLabel $runLabel -Args $args
}

# Phase 3: Confirmatory replay with fresh seeds
$confirmRunLabel = "nvda-exp3-confirm-20k-ent$($winningEntCoef -replace '\\.', '')-bonus002-freshseeds"
$confirmArgs = New-BaseArgs -Seeds $phase3Seeds -EntCoef $winningEntCoef -ActionBonus "0.02" -RunLabel $confirmRunLabel
Invoke-Experiment -RunLabel $confirmRunLabel -Args $confirmArgs

# Phase 4: Promotion push - increase direction scale to 0.40 (Option B)
Write-Host "Phase 4: Direction-scale tune (Option B)..." -ForegroundColor Magenta
$tunerRunLabel = "nvda-tuner-direction-040-ent0.05-bonus002"
$tunerArgs = @(
    "src/experiments.py",
    "--ticker", $ticker,
    "--seeds", $phase1Seeds,
    "--timesteps", $timesteps,
    "--learning-rates", $learningRates,
    "--gammas", $gammas,
    "--ent-coefs", $winningEntCoef,
    "--threshold", $threshold,
    "--horizon", "1",
    "--transaction-cost-rate", $transactionCostRate,
    "--trade-penalty", $tradePenalty,
    "--execution-mode", "next_bar",
    "--spread-bps", "0.0",
    "--slippage-bps", "0.0",
    "--reward-mode", "sharpe",
    "--reward-return-scale", $rewardReturnScale,
    "--reward-direction-scale", "0.40",
    "--reward-hold-penalty-scale", $rewardHoldPenaltyScale,
    "--reward-drawdown-penalty-scale", $rewardDrawdownPenaltyScale,
    "--reward-action-bonus-scale", "0.02",
    "--reward-turnover-penalty-scale", $rewardTurnoverPenaltyScale,
    "--reward-clip", $rewardClip,
    "--reward-ignore-transaction-cost",
    "--max-weight-delta-per-step", $maxWeightDeltaPerStep,
    "--append",
    "--run-label", $tunerRunLabel
)

Invoke-Experiment -RunLabel $tunerRunLabel -Args $tunerArgs
Write-Host "Phase 4 complete. If test_actionable >= 0.530, ready for promotion." -ForegroundColor Green

Write-Host "NVDA experiment batch complete." -ForegroundColor Green
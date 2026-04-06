$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

# Baseline setup held constant across Phase 1.
$ticker = "nvda"
$seeds = "7,13,21,42,84"
$timesteps = "12000"
$learningRates = "0.0001"
$gammas = "0.99"
$entCoefs = "0.05"
$threshold = "0.002"
$horizon = "1"
$transactionCostRate = "0.001"
$tradePenalty = "0.05"
$executionMode = "next_bar"
$rewardMode = "sharpe"
$rewardReturnScale = "1.0"
$rewardDirectionScale = "0.22"
$rewardHoldPenaltyScale = "0.08"
$rewardDrawdownPenaltyScale = "0.12"
$rewardActionBonusScale = "0.00"
$rewardTurnoverPenaltyScale = "0.03"
$rewardClip = "1.0"
$nEnvs = "8"

$prefix = "nvda-rx-v1"
$phaseGrid = @(0, 5, 10, 15)

function Invoke-Experiment {
    param(
        [Parameter(Mandatory = $true)]
        [int]$SpreadBps,
        [Parameter(Mandatory = $true)]
        [int]$SlippageBps,
        [Parameter(Mandatory = $true)]
        [string]$RunLabel
    )

    $args = @(
        "src/experiments.py",
        "--ticker", $ticker,
        "--include-news",
        "--use-stationary-features",
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--learning-rates", $learningRates,
        "--gammas", $gammas,
        "--ent-coefs", $entCoefs,
        "--threshold", $threshold,
        "--horizon", $horizon,
        "--transaction-cost-rate", $transactionCostRate,
        "--trade-penalty", $tradePenalty,
        "--execution-mode", $executionMode,
        "--reward-mode", $rewardMode,
        "--reward-return-scale", $rewardReturnScale,
        "--reward-direction-scale", $rewardDirectionScale,
        "--reward-hold-penalty-scale", $rewardHoldPenaltyScale,
        "--reward-drawdown-penalty-scale", $rewardDrawdownPenaltyScale,
        "--reward-action-bonus-scale", $rewardActionBonusScale,
        "--reward-turnover-penalty-scale", $rewardTurnoverPenaltyScale,
        "--reward-clip", $rewardClip,
        "--no-reward-ignore-transaction-cost",
        "--spread-bps", "$SpreadBps",
        "--slippage-bps", "$SlippageBps",
        "--n-envs", $nEnvs,
        "--append",
        "--run-label", $RunLabel
    )

    Write-Host "Running: $pythonExe $($args -join ' ')" -ForegroundColor Yellow
    & $pythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment failed: $RunLabel"
    }
}

function Get-RunStats {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [array]$Rows
    )

    $rs = $Rows | Where-Object { $_.run_label -eq $Label } | Sort-Object seed -Unique
    if ($rs.Count -eq 0) {
        return [pscustomobject]@{
            Label = $Label
            Count = 0
            AlphaMean = [double]::NaN
            AlphaPosCount = 0
            CvMean = [double]::NaN
            TradeRateMean = [double]::NaN
            CollapseSeedCount = 0
        }
    }

    $alpha = $rs | ForEach-Object { [double]$_.test_alpha_vs_qqq }
    $cv = $rs | ForEach-Object { [double]$_.test_return_cv_by_config }
    $tradeRate = $rs | ForEach-Object { [double]$_.test_trade_rate }

    # Collapse heuristic: very low participation or zero-value behavior.
    $collapse = $rs | Where-Object {
        ([double]$_.test_trade_rate -lt 0.05) -or
        (([double]$_.test_actionable_accuracy -eq 0.0) -and ([double]$_.test_trade_win_rate -eq 0.0))
    }

    return [pscustomobject]@{
        Label = $Label
        Count = $rs.Count
        AlphaMean = ($alpha | Measure-Object -Average).Average
        AlphaPosCount = ($rs | Where-Object { [double]$_.test_alpha_vs_qqq -gt 0 }).Count
        CvMean = ($cv | Measure-Object -Average).Average
        TradeRateMean = ($tradeRate | Measure-Object -Average).Average
        CollapseSeedCount = $collapse.Count
    }
}

Write-Host "Starting Phase 1 realism grid (control + spread/slippage stress) in local .venv..." -ForegroundColor Cyan

foreach ($bps in $phaseGrid) {
    if ($bps -eq 0) {
        $label = "$prefix-control-s0-l0"
    }
    else {
        $label = "$prefix-realism-s$bps-l$bps"
    }

    Invoke-Experiment -SpreadBps $bps -SlippageBps $bps -RunLabel $label
}

Write-Host "Phase 1 runs complete. Summarizing control vs realism..." -ForegroundColor Cyan

$rows = Import-Csv "data/experiment_leaderboard.csv"
$labels = @(
    "$prefix-control-s0-l0",
    "$prefix-realism-s5-l5",
    "$prefix-realism-s10-l10",
    "$prefix-realism-s15-l15"
)

$stats = @()
foreach ($label in $labels) {
    $s = Get-RunStats -Label $label -Rows $rows
    $stats += $s
    Write-Host ("{0} | seeds={1} alpha_mean={2:N6} alpha_pos={3} cv_mean={4:N6} trade_rate_mean={5:N6} collapse_seeds={6}" -f $s.Label, $s.Count, $s.AlphaMean, $s.AlphaPosCount, $s.CvMean, $s.TradeRateMean, $s.CollapseSeedCount)
}

$control = $stats | Where-Object { $_.Label -eq "$prefix-control-s0-l0" }
$realism = $stats | Where-Object { $_.Label -ne "$prefix-control-s0-l0" }

if (-not $control -or $control.Count -eq 0) {
    throw "Missing control run stats; cannot interpret Phase 1 results."
}

$allRealismNegative = ($realism | Where-Object { $_.AlphaMean -ge 0 }).Count -eq 0
$anyRealismHighCv = ($realism | Where-Object { $_.CvMean -gt 1.0 }).Count -gt 0
$anyCollapse = ($realism | Where-Object { $_.CollapseSeedCount -gt 0 }).Count -gt 0
$anyHighTurnover = ($realism | Where-Object { $_.TradeRateMean -gt 0.85 }).Count -gt 0

Write-Host "" 
Write-Host "Interpretation criteria:" -ForegroundColor Cyan
Write-Host "- Alpha resilience: realism alpha should stay close to control or improve."
Write-Host "- Stability: realism CV should trend down and stay below 1.0 when possible."

Write-Host "" 
Write-Host "Decision:" -ForegroundColor Cyan
if ($allRealismNegative -and $anyRealismHighCv) {
    Write-Host "STOP + ESCALATE: all realism runs remain benchmark-negative and unstable." -ForegroundColor Red
    Write-Host "Next step: escalate to environment realism/execution-focused diagnostics (do not broaden sweeps)." -ForegroundColor Red
}
elseif ($anyHighTurnover -or $anyCollapse) {
    Write-Host "IMPLEMENT max_weight_delta_per_step next: churn/collapse signature detected under realism." -ForegroundColor Yellow
    Write-Host "Then rerun the same realism grid with the same cohort label family v2." -ForegroundColor Yellow
}
else {
    Write-Host "Proceed with cautious refinement: realism does not show severe churn/collapse pattern." -ForegroundColor Green
    Write-Host "Keep cohort versioning and avoid cross-cohort winner comparisons." -ForegroundColor Green
}

Write-Host "" 
Write-Host "Comparability strategy:" -ForegroundColor Cyan
Write-Host "- Control:   $prefix-control-s0-l0"
Write-Host "- Realism:   $prefix-realism-s5-l5 / s10-l10 / s15-l15"
Write-Host "- Compare only within the $prefix cohort and dedupe by seed for analysis."

Write-Host "Phase 1 realism audit script complete." -ForegroundColor Green
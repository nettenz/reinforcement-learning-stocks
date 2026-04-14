# Sharpe vs Sortino Retest Experiment
# Purpose: Confirm Sharpe's edge is real (not noise) using best params from all experiments
# Target: Determine if Sharpe >= 50% && Sortino < 45%, or both similar
# Uses: Best params from Experiments 1, 3, 4 (entropy, reward, timesteps)
# Duration: ~2.5-3.5 hours, 12-15 GPU hours

param(
    [string]$Ticker = "nvda",
    [int[]]$Seeds = @(7, 13, 21, 27, 123),  # Full seed set for statistical power
    [int]$Timesteps = 20000,                 # Or best from Exp 4
    [double]$EntCoef = 0.06,                 # From Exp 1 best
    [string]$EntropySchedule = "fixed",      # From Exp 1 best
    [double]$RewardClip = 1.0,               # From Exp 3 best
    [double]$DrawdownPenalty = 0.15,         # From Exp 3 best
    [double]$TurnoverPenalty = 0.05          # From Exp 3 best
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SHARPE VS SORTINO RETEST EXPERIMENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Config:" -ForegroundColor Yellow
Write-Host "  Ticker:              $Ticker"
Write-Host "  Seeds:               $($Seeds -join ',')"
Write-Host "  Timesteps:           $Timesteps (from Exp 4 best)"
Write-Host "  Entropy Coef:        $EntCoef (from Exp 1 best)"
Write-Host "  Entropy Schedule:    $EntropySchedule (from Exp 1 best)"
Write-Host "  Reward Clip:         $RewardClip (from Exp 3 best)"
Write-Host "  Drawdown Penalty:    $DrawdownPenalty (from Exp 3 best)"
Write-Host "  Turnover Penalty:    $TurnoverPenalty (from Exp 3 best)"
Write-Host ""
Write-Host "Treatments:" -ForegroundColor Yellow
Write-Host "  A: reward_mode=sharpe (new best params)"
Write-Host "  B: reward_mode=sortino (new best params)"
Write-Host ""

# Activate venv
& .\.venv\Scripts\Activate.ps1

$modes = @(
    @{
        name = "A_Sharpe"
        reward_mode = "sharpe"
        label = "mode-sharpe"
        description = "Sharpe reward mode with best-found params"
    },
    @{
        name = "B_Sortino"
        reward_mode = "sortino"
        label = "mode-sortino"
        description = "Sortino reward mode with best-found params"
    }
)

$totalRuns = $modes.Length * $Seeds.Length
Write-Host "Total runs to execute: $totalRuns" -ForegroundColor Cyan
Write-Host ""

$runCount = 0

foreach ($mode in $modes) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Reward Mode: $($mode.name)" -ForegroundColor Green
    Write-Host "Description: $($mode.description)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    foreach ($seed in $Seeds) {
        $runCount++
        Write-Host "  [$runCount/$totalRuns] Running mode=$($mode.reward_mode) seed=$seed..."
        
        # Construct command
        $cmd = @(
            "python", "src/experiments.py",
            "--ticker", $Ticker,
            "--seeds", $seed.ToString(),
            "--timesteps", $Timesteps.ToString(),
            "--ent-coefs", $EntCoef.ToString(),
            "--reward-mode", $mode.reward_mode,
            "--learning-rates", "0.0003",
            "--gammas", "0.99",
            "--threshold", "0.002",
            "--horizon", "1",
            "--transaction-cost-rate", "0.001",
            "--trade-penalty", "0.05",
            "--execution-mode", "next_bar",
            "--spread-bps", "0.0",
            "--slippage-bps", "0.0",
            "--max-weight-delta-per-step", "0.0",
            "--rolling-reward-window", "100",
            "--reward-epsilon", "1e-6",
            "--reward-return-scale", "1.0",
            "--reward-direction-scale", "0.35",
            "--reward-hold-penalty-scale", "0.1",
            "--reward-drawdown-penalty-scale", $DrawdownPenalty.ToString(),
            "--reward-action-bonus-scale", "0.02",
            "--reward-turnover-penalty-scale", $TurnoverPenalty.ToString(),
            "--reward-clip", $RewardClip.ToString(),
            "--reward-ignore-transaction-cost",
            "--max-runs", "1",
            "--run-label", "mode-compare-$($mode.label)-seed$seed",
            "--append"
        )
        
        & $cmd[0] $cmd[1..($cmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      ✓ Completed" -ForegroundColor Green
        } else {
            Write-Host "      ✗ Failed (exit code $LASTEXITCODE)" -ForegroundColor Red
        }
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EXPERIMENT COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Check leaderboard: data/experiment_leaderboard.csv"
Write-Host "2. Filter to runs starting with 'mode-compare-'"
Write-Host "3. Calculate statistics for each mode:"
Write-Host "   - Sharpe mode: mean test_actionable_accuracy, std, cv"
Write-Host "   - Sortino mode: mean test_actionable_accuracy, std, cv"
Write-Host "4. Decision logic:"
Write-Host "   - If Sharpe >= 50% AND Sortino < 45%: Sharpe is clear winner"
Write-Host "   - If both >= 48%: No clear winner; use Sharpe as default (simpler)"
Write-Host "   - If Sortino wins: Investigate why downside protection helps for NVDA"
Write-Host ""
Write-Host "Success Criteria:" -ForegroundColor Yellow
Write-Host "  [ ] Sharpe achieves >= 50% test accuracy"
Write-Host "  [ ] Sortino achieves < 45% test accuracy"
Write-Host "  [ ] If tie: Recommend Sharpe as default"
Write-Host ""

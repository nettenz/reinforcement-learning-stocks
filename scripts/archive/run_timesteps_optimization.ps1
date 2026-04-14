# Timesteps Optimization Experiment
# Purpose: Find optimal timesteps in range [10k-30k] to confirm 20k is optimal
# Target: Confirm test accuracy >= 50% AND config_cv < 2.0
# Uses: Best entropy schedule + best reward params from Experiments 1 & 3
# Duration: ~3-4 hours, 10-12 GPU hours (reduced seed set to manage cost)

param(
    [string]$Ticker = "nvda",
    [int[]]$Seeds = @(7, 13, 21),  # Reduced seed set for cost management
    [int[]]$Timesteps = @(10000, 15000, 20000, 25000, 30000),
    [string]$RewardMode = "sharpe",
    [double]$EntCoef = 0.06,
    [string]$EntropySchedule = "fixed",  # From Exp 1 best
    [double]$RewardClip = 1.0,           # From Exp 3 best
    [double]$DrawdownPenalty = 0.15,     # From Exp 3 best
    [double]$TurnoverPenalty = 0.05      # From Exp 3 best
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TIMESTEPS OPTIMIZATION EXPERIMENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Config:" -ForegroundColor Yellow
Write-Host "  Ticker:              $Ticker"
Write-Host "  Seeds:               $($Seeds -join ',') (reduced for cost)"
Write-Host "  Timesteps to test:   $($Timesteps -join ', ')"
Write-Host "  Reward Mode:         $RewardMode"
Write-Host "  Entropy Coef:        $EntCoef"
Write-Host "  Entropy Schedule:    $EntropySchedule"
Write-Host "  Reward Clip:         $RewardClip (from Exp 3)"
Write-Host "  Drawdown Penalty:    $DrawdownPenalty (from Exp 3)"
Write-Host "  Turnover Penalty:    $TurnoverPenalty (from Exp 3)"
Write-Host ""

# Activate venv
& .\.venv\Scripts\Activate.ps1

$totalRuns = $Timesteps.Length * $Seeds.Length
Write-Host "Total runs to execute: $totalRuns" -ForegroundColor Cyan
Write-Host ""

$runCount = 0

foreach ($ts in $Timesteps) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Timesteps: $ts" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    foreach ($seed in $Seeds) {
        $runCount++
        Write-Host "  [$runCount/$totalRuns] Running timesteps=$ts seed=$seed..."
        
        # Construct command
        $cmd = @(
            "python", "src/experiments.py",
            "--ticker", $Ticker,
            "--seeds", $seed.ToString(),
            "--timesteps", $ts.ToString(),
            "--ent-coefs", $EntCoef.ToString(),
            "--reward-mode", $RewardMode,
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
            "--run-label", "timesteps-opt-${ts}k-seed$seed",
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
Write-Host "2. Filter to runs starting with 'timesteps-opt-'"
Write-Host "3. For each timesteps value, calculate:"
Write-Host "   - Mean test_actionable_accuracy across seeds"
Write-Host "   - Mean test_return_cv_by_config across seeds"
Write-Host "   - Std of test_actionable_accuracy (stability)"
Write-Host "4. Plot test_accuracy vs timesteps to find peak"
Write-Host "5. Confirm optimal timesteps (target: >= 50% accuracy AND < 2.0 CV)"
Write-Host ""
Write-Host "Success Criteria:" -ForegroundColor Yellow
Write-Host "  [ ] Identify timesteps where test_accuracy >= 50% AND config_cv < 2.0"
Write-Host "  [ ] Confirm 20k is within top 2 timesteps, OR discover new optimum"
Write-Host "  [ ] If 20k not optimal: investigate why (learning rate? early stopping?)"
Write-Host ""

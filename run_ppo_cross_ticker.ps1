# run_ppo_cross_ticker.ps1
# Validates the PPO-Binary architecture across multiple legacy and new tickers

$TICKERS = @("nvda", "amd", "aapl")
$LABEL_BASE = "ppo_binary_cross_val"
$PYTHON = "./.venv/Scripts/python.exe"
$env:PYTHONUTF8 = 1

foreach ($TICKER in $TICKERS) {
    $LABEL = "${LABEL_BASE}_${TICKER}"
    Write-Host "🚀 Running PPO-Binary Validation for $TICKER..." -ForegroundColor Cyan
    
    & $PYTHON src/experiments.py `
        --ticker $TICKER `
        --seeds 7,13,42 `
        --timesteps 60000 `
        --ent-coefs 0.05 `
        --binary-actions `
        --min-hold-bars 3 `
        --run-label $LABEL `
        --append

    Write-Host "📊 Evaluating $TICKER..." -ForegroundColor Yellow
    & $PYTHON scripts/evaluate_sweep.py `
        --leaderboard data/experiment_leaderboard.csv `
        --label $LABEL `
        --ticker $TICKER `
        --g6-max-trade-rate 1.00
}

Write-Host "✅ Cross-ticker validation complete." -ForegroundColor Green

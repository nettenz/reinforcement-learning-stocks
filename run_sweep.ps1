$seeds = 2..5
$modes = @(
    @{mode="legacy"; window=100},
    @{mode="sharpe"; window=50},
    @{mode="sharpe"; window=100},
    @{mode="sharpe"; window=250},
    @{mode="sortino"; window=50},
    @{mode="sortino"; window=100},
    @{mode="sortino"; window=250}
)

Write-Host "Starting Quant Sweep (35 total runs)..." -ForegroundColor Cyan

foreach ($seed in $seeds) {
    foreach ($cfg in $modes) {
        $cmd = ".venv\Scripts\python src\experiments.py --device cpu --append --reward-mode $($cfg.mode) --rolling-reward-window $($cfg.window) --seed $seed"
        Write-Host "Running: $cmd" -ForegroundColor Yellow
        Invoke-Expression $cmd
    }
}

Write-Host "All sweeps completed! Check your dashboard on http://127.0.0.1:8501" -ForegroundColor Green

```powershell
# 1. Inspect the full sweep results
python scripts/evaluate_sweep.py `
    --leaderboard data/experiment_leaderboard.csv `
    --label sweep_overtrade_fix_nvda

# 2. Champion found — auto-trigger ensemble config regeneration
python scripts/evaluate_sweep.py `
    --leaderboard data/experiment_leaderboard.csv `
    --label sweep_overtrade_fix_nvda `
    --promote

# 3. No label column yet / want full leaderboard view
python scripts/evaluate_sweep.py `
    --leaderboard data/experiment_leaderboard.csv `
    --ticker NVDA --top 20
```
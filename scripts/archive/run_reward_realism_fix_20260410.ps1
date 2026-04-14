# Reward Realism Fix - 2026-04-10
# Goal: Force agent to see 10bps costs and reduce drawdown paralysis.

$CommonArgs = "--ticker nvda --timesteps 20000 --learning-rates 0.0003 --ent-coefs 0.07 --reward-mode sortino --rolling-reward-window 100 --transaction-cost-rate 0.001 --no-reward-ignore-transaction-cost --n-envs 4"

# Variant A: Conservative (No action bonus, higher penalties)
python src/experiments.py $CommonArgs --run-label "nvda-reward-realism-A-cons" --reward-drawdown-penalty-scale 0.10 --reward-action-bonus-scale 0.0 --reward-turnover-penalty-scale 0.10 --reward-return-scale 1.0 --seeds 10

# Variant B: Balanced (Minimal bonus, light DD penalty)
python src/experiments.py $CommonArgs --run_label "nvda-reward-realism-B-bal" --reward-drawdown-penalty-scale 0.05 --reward-action-bonus-scale 0.005 --reward-turnover-penalty-scale 0.05 --reward-return-scale 1.2 --reward-direction-scale 0.50 --seeds 10

# Variant C: Aggressive (Moderate bonus, very light DD penalty)
python src/experiments.py $CommonArgs --run_label "nvda-reward-realism-C-agg" --reward-drawdown-penalty-scale 0.02 --reward-action-bonus-scale 0.01 --reward-turnover-penalty-scale 0.02 --reward-return-scale 1.5 --reward-direction-scale 0.60 --seeds 10

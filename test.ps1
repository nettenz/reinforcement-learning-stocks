
# Hybrid acceleration runbook (CPU broad -> GPU deep -> CPU robustness)
# Stage A: broad search (cheap, fast)
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13,21 --timesteps 10000,15000 --learning-rates 0.0003,0.0001 --gammas 0.99 --ent-coefs 0.03,0.05 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-mode sharpe --reward-return-scale 1.0 --reward-direction-scale 0.30,0.35 --reward-hold-penalty-scale 0.10 --reward-drawdown-penalty-scale 0.10 --reward-action-bonus-scale 0.02 --reward-clip 1.0 --reward-ignore-transaction-cost --n-envs 8 --max-runs 24 --append --run-label hybrid-stage-a

# Stage B: narrowed deepening (device auto)
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13,21,42,84 --timesteps 40000,60000 --learning-rates 0.0003 --gammas 0.99,0.995 --ent-coefs 0.02,0.03 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-mode sharpe --reward-return-scale 1.0 --reward-direction-scale 0.35 --reward-hold-penalty-scale 0.10 --reward-drawdown-penalty-scale 0.10,0.15 --reward-action-bonus-scale 0.02,0.04 --reward-clip 1.0 --reward-ignore-transaction-cost --n-envs 4 --max-runs 20 --append --run-label hybrid-stage-b

# Stage C: robustness/variance gate
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13,21,42,84,121,233 --timesteps 40000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.03 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-mode sharpe --reward-return-scale 1.0 --reward-direction-scale 0.35 --reward-hold-penalty-scale 0.10 --reward-drawdown-penalty-scale 0.10 --reward-action-bonus-scale 0.02 --reward-clip 1.0 --reward-ignore-transaction-cost --n-envs 8 --max-runs 7 --append --run-label hybrid-stage-c

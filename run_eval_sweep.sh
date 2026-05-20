#!/bin/bash
# run_eval_sweep.sh
# Script to run the evaluation commands sequentially on macOS

PYTHON_EXEC=".venv/bin/python3"

echo "======================================================"
echo "1. Inspect the AMD Sweep results"
echo "======================================================"
$PYTHON_EXEC scripts/evaluate_sweep.py \
    --leaderboard data/experiment_leaderboard.csv \
    --ticker AMD \
    --label amd-masked-ppo-v1-tuned

echo -e "\n======================================================"
echo "2. Auto-promote AMD champion if found"
echo "======================================================"
$PYTHON_EXEC scripts/evaluate_sweep.py \
    --leaderboard data/experiment_leaderboard.csv \
    --ticker AMD \
    --label amd-masked-ppo-v1-tuned \
    --promote

echo -e "\n======================================================"
echo "3. Inspect the MU Sweep results (with Gate 6 waiver)"
echo "======================================================"
$PYTHON_EXEC scripts/evaluate_sweep.py \
    --leaderboard data/experiment_leaderboard.csv \
    --ticker MU \
    --label mu-masked-ppo-v1-tuned \
    --g6-max-trade-rate 1.00

echo -e "\n======================================================"
echo "4. Auto-promote MU champion if found (with Gate 6 waiver)"
echo "======================================================"
$PYTHON_EXEC scripts/evaluate_sweep.py \
    --leaderboard data/experiment_leaderboard.csv \
    --ticker MU \
    --label mu-masked-ppo-v1-tuned \
    --g6-max-trade-rate 1.00 \
    --promote

echo -e "\nSweep evaluation completed."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # POSIX/macOS/Linux virtual environment activation.
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
elif [[ -f "$ROOT_DIR/.venv/Scripts/activate" ]]; then
  # Fallback for bash environments on Windows.
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/Scripts/activate"
else
  echo "Virtual environment activation script not found under .venv." >&2
  exit 1
fi

PYTHON="${PYTHON:-python}"

if "$PYTHON" -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  DEVICE="cuda"
elif "$PYTHON" -c "import torch; exit(0 if torch.backends.mps.is_available() else 1)" 2>/dev/null; then
  DEVICE="mps"
else
  DEVICE="cpu"
fi

echo "Environment detected."
echo "Acceleration: $DEVICE (CUDA preferred, then MPS, then CPU)"

TICKER="nvda"
SEEDS_BASE="101,202,303,404,505"
TIMESTEPS="20000"
LEARNING_RATES="0.0003"
GAMMAS="0.99"
THRESHOLD="0.002"
TRANSACTION_COST_RATE="0.001"
TRADE_PENALTY="0.05"
REWARD_RETURN_SCALE="1.0"
REWARD_DIRECTION_SCALE="0.35"
REWARD_HOLD_PENALTY_SCALE="0.10"
REWARD_DRAWDOWN_PENALTY_SCALE_BASE="0.10"
REWARD_DRAWDOWN_PENALTY_SCALE_HIGH="0.15"
REWARD_ACTION_BONUS_SCALE="0.02"
REWARD_TURNOVER_PENALTY_SCALE="0.05"
REWARD_CLIP="1.0"
MAX_WEIGHT_DELTA_PER_STEP="0.25"
REWARD_MODE="sharpe"
EXECUTION_MODE="next_bar"

run_experiment() {
  local run_label="$1"
  local drawdown_penalty="$2"

  echo "Running: $PYTHON src/experiments.py --device $DEVICE --ticker $TICKER --seeds $SEEDS_BASE --timesteps $TIMESTEPS --learning-rates $LEARNING_RATES --gammas $GAMMAS --ent-coefs 0.05 --threshold $THRESHOLD --horizon 1 --transaction-cost-rate $TRANSACTION_COST_RATE --trade-penalty $TRADE_PENALTY --execution-mode $EXECUTION_MODE --spread-bps 0.0 --slippage-bps 0.0 --reward-mode $REWARD_MODE --reward-return-scale $REWARD_RETURN_SCALE --reward-direction-scale $REWARD_DIRECTION_SCALE --reward-hold-penalty-scale $REWARD_HOLD_PENALTY_SCALE --reward-drawdown-penalty-scale $drawdown_penalty --reward-action-bonus-scale $REWARD_ACTION_BONUS_SCALE --reward-turnover-penalty-scale $REWARD_TURNOVER_PENALTY_SCALE --reward-clip $REWARD_CLIP --reward-ignore-transaction-cost --max-weight-delta-per-step $MAX_WEIGHT_DELTA_PER_STEP --append --run-label $run_label"
  "$PYTHON" src/experiments.py \
    --device "$DEVICE" \
    --ticker "$TICKER" \
    --seeds "$SEEDS_BASE" \
    --timesteps "$TIMESTEPS" \
    --learning-rates "$LEARNING_RATES" \
    --gammas "$GAMMAS" \
    --ent-coefs 0.05 \
    --threshold "$THRESHOLD" \
    --horizon 1 \
    --transaction-cost-rate "$TRANSACTION_COST_RATE" \
    --trade-penalty "$TRADE_PENALTY" \
    --execution-mode "$EXECUTION_MODE" \
    --spread-bps 0.0 \
    --slippage-bps 0.0 \
    --reward-mode "$REWARD_MODE" \
    --reward-return-scale "$REWARD_RETURN_SCALE" \
    --reward-direction-scale "$REWARD_DIRECTION_SCALE" \
    --reward-hold-penalty-scale "$REWARD_HOLD_PENALTY_SCALE" \
    --reward-drawdown-penalty-scale "$drawdown_penalty" \
    --reward-action-bonus-scale "$REWARD_ACTION_BONUS_SCALE" \
    --reward-turnover-penalty-scale "$REWARD_TURNOVER_PENALTY_SCALE" \
    --reward-clip "$REWARD_CLIP" \
    --reward-ignore-transaction-cost \
    --max-weight-delta-per-step "$MAX_WEIGHT_DELTA_PER_STEP" \
    --append \
    --run-label "$run_label"
}

echo "Starting NVDA sharpe downside-control A/B batch..."

run_experiment "nvda-downside-ab-20k-ent05-dir035-dd010" "$REWARD_DRAWDOWN_PENALTY_SCALE_BASE"
run_experiment "nvda-downside-ab-20k-ent05-dir035-dd015" "$REWARD_DRAWDOWN_PENALTY_SCALE_HIGH"

echo "NVDA sharpe downside-control A/B batch complete."
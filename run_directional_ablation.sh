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
TICKER="nvda"
SEEDS="7,13,21,42,84"
TIMESTEPS="20000"
LEARNING_RATES="0.0003"
GAMMAS="0.99"
THRESHOLD="0.002"
TRANSACTION_COST_RATE="0.001"
TRADE_PENALTY="0.05"
REWARD_RETURN_SCALE="1.0"
REWARD_ACTION_BONUS_SCALE="0.02"
REWARD_HOLD_PENALTY_SCALE="0.10"
REWARD_DRAWDOWN_PENALTY_SCALE="0.10"
REWARD_TURNOVER_PENALTY_SCALE="0.05"
REWARD_CLIP="1.0"
MAX_WEIGHT_DELTA_PER_STEP="0.25"
REWARD_MODE="sharpe"
EXECUTION_MODE="next_bar"

run_experiment() {
  local run_label="$1"
  local direction_scale="$2"

  echo "Running: $PYTHON src/experiments.py --ticker $TICKER --seeds $SEEDS --timesteps $TIMESTEPS --learning-rates $LEARNING_RATES --gammas $GAMMAS --ent-coefs 0.05 --threshold $THRESHOLD --horizon 1 --transaction-cost-rate $TRANSACTION_COST_RATE --trade-penalty $TRADE_PENALTY --execution-mode $EXECUTION_MODE --spread-bps 0.0 --slippage-bps 0.0 --reward-mode $REWARD_MODE --reward-return-scale $REWARD_RETURN_SCALE --reward-direction-scale $direction_scale --reward-hold-penalty-scale $REWARD_HOLD_PENALTY_SCALE --reward-drawdown-penalty-scale $REWARD_DRAWDOWN_PENALTY_SCALE --reward-action-bonus-scale $REWARD_ACTION_BONUS_SCALE --reward-turnover-penalty-scale $REWARD_TURNOVER_PENALTY_SCALE --reward-clip $REWARD_CLIP --reward-ignore-transaction-cost --max-weight-delta-per-step $MAX_WEIGHT_DELTA_PER_STEP --append --run-label $run_label"
  "$PYTHON" src/experiments.py \
    --ticker "$TICKER" \
    --seeds "$SEEDS" \
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
    --reward-direction-scale "$direction_scale" \
    --reward-hold-penalty-scale "$REWARD_HOLD_PENALTY_SCALE" \
    --reward-drawdown-penalty-scale "$REWARD_DRAWDOWN_PENALTY_SCALE" \
    --reward-action-bonus-scale "$REWARD_ACTION_BONUS_SCALE" \
    --reward-turnover-penalty-scale "$REWARD_TURNOVER_PENALTY_SCALE" \
    --reward-clip "$REWARD_CLIP" \
    --reward-ignore-transaction-cost \
    --max-weight-delta-per-step "$MAX_WEIGHT_DELTA_PER_STEP" \
    --append \
    --run-label "$run_label"
}

echo "Starting NVDA directional-strength A/B batch..."

run_experiment "nvda-direction-ab-20k-ent05-bonus002-dir035" "0.35"
run_experiment "nvda-direction-ab-20k-ent05-bonus002-dir040" "0.40"

echo "Directional-strength A/B batch complete."

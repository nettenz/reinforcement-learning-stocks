#!/usr/bin/env bash
set -euo pipefail

# Reward Realism Fix - 2026-04-10
# Goal: Force agent to see 10bps costs and reduce drawdown paralysis.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
while [[ "$ROOT_DIR" != "/" && ! -f "$ROOT_DIR/src/experiments.py" ]]; do
  ROOT_DIR="$(dirname "$ROOT_DIR")"
done

if [[ ! -f "$ROOT_DIR/src/experiments.py" ]]; then
  echo "Could not locate repository root containing src/experiments.py." >&2
  exit 1
fi

cd "$ROOT_DIR"

resolve_python() {
  if [[ -x "$ROOT_DIR/.venv-wsl/bin/python" ]]; then
    echo "$ROOT_DIR/.venv-wsl/bin/python"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv-wsl/bin/python3" ]]; then
    echo "$ROOT_DIR/.venv-wsl/bin/python3"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/bin/python3" ]]; then
    echo "$ROOT_DIR/.venv/bin/python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT_DIR/.venv/Scripts/python.exe"
    return 0
  fi
  return 1
}

PYTHON_EXEC="$(resolve_python)"

COMMON_ARGS=(
  --ticker nvda
  --timesteps 20000
  --learning-rates 0.0003
  --ent-coefs 0.07
  --reward-mode sortino
  --rolling-reward-window 100
  --transaction-cost-rate 0.001
  --no-reward-ignore-transaction-cost
  --n-envs 4
)

# Variant A: Conservative (No action bonus, higher penalties)
"$PYTHON_EXEC" src/experiments.py "${COMMON_ARGS[@]}" --run-label "nvda-reward-realism-A-cons" --reward-drawdown-penalty-scale 0.10 --reward-action-bonus-scale 0.0 --reward-turnover-penalty-scale 0.10 --reward-return-scale 1.0 --seeds 10

# Variant B: Balanced (Minimal bonus, light DD penalty)
"$PYTHON_EXEC" src/experiments.py "${COMMON_ARGS[@]}" --run-label "nvda-reward-realism-B-bal" --reward-drawdown-penalty-scale 0.05 --reward-action-bonus-scale 0.005 --reward-turnover-penalty-scale 0.05 --reward-return-scale 1.2 --reward-direction-scale 0.50 --seeds 10

# Variant C: Aggressive (Moderate bonus, very light DD penalty)
"$PYTHON_EXEC" src/experiments.py "${COMMON_ARGS[@]}" --run-label "nvda-reward-realism-C-agg" --reward-drawdown-penalty-scale 0.02 --reward-action-bonus-scale 0.01 --reward-turnover-penalty-scale 0.02 --reward-return-scale 1.5 --reward-direction-scale 0.60 --seeds 10

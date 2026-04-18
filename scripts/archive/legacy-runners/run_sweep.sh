#!/usr/bin/env bash
set -euo pipefail

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
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/bin/python3" ]]; then
    echo "$ROOT_DIR/.venv/bin/python3"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT_DIR/.venv/Scripts/python.exe"
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
  return 1
}

PYTHON_EXEC="$(resolve_python)"

# Array of target seeds
SEEDS=(2 3 4 5)

# Configurations formatted as "mode:window"
CONFIGS=(
    "legacy:100"
    "sharpe:50"
    "sharpe:100"
    "sharpe:250"
    "sortino:50"
    "sortino:100"
    "sortino:250"
)

echo -e "\033[1;36mStarting Quant Sweep (35 total runs) using CUDA GPU...\033[0m"

for seed in "${SEEDS[@]}"; do
    for config in "${CONFIGS[@]}"; do
        # Parse the mode and window
        IFS=':' read -r mode window <<< "$config"
        
        # Execute the python script for Windows bash
        CMD="$PYTHON_EXEC src/experiments.py --device cuda --append --reward-mode $mode --rolling-reward-window $window --seed $seed"
        
        echo -e "\033[1;33mRunning: $CMD\033[0m"
        
        # Execute the command
        "$PYTHON_EXEC" src/experiments.py --device cuda --append --reward-mode "$mode" --rolling-reward-window "$window" --seed "$seed"
    done
done

echo -e "\033[1;32mAll sweeps completed! Check your results!\033[0m"

# ============================================================================
# AMD UNLOCK EXPERIMENTS (Exp 2a/2b/2c - Sequential)
# Current: 0.5226 accuracy vs 0.5300 gate (0.18% short = ~2 samples)
# Strategy: Run sequentially, stop on first success
# ============================================================================

echo -e "\033[1;35m\nAMD UNLOCK SEQUENCE (Sequential - Stop on Success)\033[0m"
echo -e "\033[1;33mCurrent AMD Test Accuracy: 0.5226 (0.18% short of 0.5300 gate)\033[0m"

# Fix 1a: Lower Action Bonus (0.01) - Reduce trading noise
echo -e "\033[1;36m\n[1a] Running AMD Fix: Lower Action Bonus (0.01)...\033[0m"
"$PYTHON_EXEC" src/experiments.py --ticker amd --seeds 7,21,13 --timesteps 20000 --reward-mode sharpe --reward-action-bonus-scale 0.01 --append --run-label amd-sharpe-bonus-001
if [[ $? -eq 0 ]]; then
    echo -e "\033[1;32m✓ Fix 1a potential success! Check leaderboard for accuracy >= 0.5300\033[0m"
    echo -e "\033[1;32mIf successful, promotion ready.\033[0m"
else
    echo -e "\033[1;33mFix 1a did not reach threshold, trying Fix 1b...\033[0m"
fi

# Fix 1b: Higher Entropy (0.10) - More exploration, better decision boundary
echo -e "\033[1;36m\n[1b] Running AMD Fix: Higher Entropy (0.10)...\033[0m"
"$PYTHON_EXEC" src/experiments.py --ticker amd --seeds 7 --timesteps 20000 --reward-mode sharpe --ent-coefs 0.10 --append --run-label amd-sharpe-entropy-010
if [[ $? -eq 0 ]]; then
    echo -e "\033[1;32m✓ Fix 1b potential success! Check leaderboard for accuracy >= 0.5300\033[0m"
    echo -e "\033[1;32mIf successful, promotion ready.\033[0m"
else
    echo -e "\033[1;33mFix 1b did not reach threshold, trying Fix 1c...\033[0m"
fi

# Fix 1c: Longer Rolling Window (200) - More stable Sharpe in early episodes
echo -e "\033[1;36m\n[1c] Running AMD Fix: Longer Rolling Window (200)...\033[0m"
"$PYTHON_EXEC" src/experiments.py --ticker amd --seeds 7 --timesteps 20000 --reward-mode sharpe --rolling-reward-window 200 --append --run-label amd-sharpe-window-200
if [[ $? -eq 0 ]]; then
    echo -e "\033[1;32m✓ Fix 1c potential success! Check leaderboard for accuracy >= 0.5300\033[0m"
    echo -e "\033[1;32mIf successful, promotion ready.\033[0m"
else
    echo -e "\033[1;33mAll AMD fixes attempted. If none succeeded, NVDA-only deployment is conservative option.\033[0m"
fi

echo -e "\033[1;35m\nAMD UNLOCK SEQUENCE COMPLETE\033[0m"

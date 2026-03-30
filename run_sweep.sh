#!/bin/bash

# Array of target seeds
SEEDS=(1 2 3 4 5)

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

echo -e "\033[1;36mStarting Quant Sweep (35 total runs) using M4 (MPS Acceleration)...\033[0m"

for seed in "${SEEDS[@]}"; do
    for config in "${CONFIGS[@]}"; do
        # Parse the mode and window
        IFS=':' read -r mode window <<< "$config"
        
        # Execute the python script. 
        # (Assuming you use 'python' after running `source .venv/bin/activate` on your Mac)
        CMD="python src/experiments.py --reward-mode $mode --rolling-reward-window $window --seed $seed"
        
        echo -e "\033[1;33mRunning: $CMD\033[0m"
        
        # Execute the generated argument string
        eval "$CMD"
        
        # Check for user termination (Ctrl+C)
        if [ $? -ne 0 ]; then
            echo "Sweep interrupted by user."
            exit 1
        fi
    done
done

echo -e "\033[1;32mAll sweeps completed! Check your results!\033[0m"

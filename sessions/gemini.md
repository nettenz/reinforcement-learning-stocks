# Gemini Experiment Session

## Last Updated
2026-03-30 (Sortino Sweep Currently Running)

## Project State
- Algorithm: PPO (SAC Migration Pending)
- Observation space: Stationary features (log returns, etc.)
- Action space: Discrete Buy/Sell/Hold
- Look-ahead bias audited: YES (Fixed and validated)
- Reward metrics added: YES (Sharpe, Sortino, Max DD now tracked in leaderboard)

## Runs Completed
| Run Label | Sharpe (val) | Sharpe (test) | Max DD | Collapse Rate | Verdict |
|---|---|---|---|---|---|
| sortino-sweep-in-progress | PENDING | PENDING | PENDING | PENDING | PENDING |

*(Note: Prior runs showed val/test generalization improvement but lack of conviction due to discrete action space. A 24-config multi-seed sweep testing the Sortino reward across windows of 50, 100, and 250 is currently running in the background).*

## Configs Ruled Out
- Future-price directional rewards (Look-ahead bias was identified and removed).
- Overwriting experiment files (Fixed by adding `--append` to `experiments.py`).
- GPU (MPS) acceleration on this architecture (CPU is significantly faster/more stable).

## What Was Interpreted
The look-ahead bias in the reward function was successfully fixed and verified. The environment now correctly uses realized returns. Financial metrics (Sharpe, Sortino, Max Drawdown) and a QQQ benchmark tie-in have been successfully added to `experiments.py`. We are currently running a large sweep evaluating the newly added `sortino` reward mode across different seeds and configurations to establish a clean, risk-adjusted baseline without look-ahead bias.

## What Was Added or Changed
- Added `--device` flag to `train_bot.py` to ensure CPU enforcement works properly.
- Added `--append` flag to `experiments.py` so sweeps properly aggregate all configurations into a single master leaderboard.
- Updated `run_sweep.ps1` and `run_sweep.sh` to leverage `--append` and restart sweeps gracefully.

## Next Steps for Copilot
When the user returns, the current sweep will be finished. Gemini will evaluate the results first. Following that evaluation, the primary development tasks for Copilot are:

1. **Migrate PPO → SAC with continuous action space (`src/train_bot.py` context)**
   - Import `SAC` from `stable_baselines3`.
   - Update the action space in `TradingEnv` to `gym.spaces.Box(low=-1.0, high=1.0, shape=(1,))` (representing short to long sizing).
2. **Add position state to observation (`src/trading_env.py`)**
   - The agent requires explicit knowledge of its current exposure. Add `[current_position, unrealized_pnl_pct, time_in_position]` to the observation vector.

## Next Experiment Command
```bash
# Evaluate the new continuous SAC run once implemented:
.venv/Scripts/python src/train_bot.py --device cpu --algo SAC --continuous-actions --timesteps 50000
```

## Autonomy Status
- [ ] Continuing autonomously
- [ ] Escalating to user
- [X] Hard stop — diagnosis: Waiting for the 24-config Sortino sweep to finish processing before analyzing the leaderboard.

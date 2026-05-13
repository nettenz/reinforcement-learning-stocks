# Current Session: Stabilizing RL Stock Trading (May 12, 2026)

## Objective
The primary objective of the current session is to resolve the action collapse observed in "Binary PPO" reinforcement learning experiments for NVDA and AAPL. AMD has been successfully promoted via the `amd-ppo-hold-fix` sweep, proving the viability of the Binary PPO architecture.

## Current Roadblock
NVDA and AAPL are exhibiting severe inaction bias (0.0% trade rate). Previous sweeps attempting to isolate and lower either the turnover penalty or the hold penalty were insufficient. The current roadblock is finding the correct reward combination that allows them to trade over the transaction cost barriers.

*(Note: The previous OS-level file descriptor limit issue "Too many open files" was bypassed using `--n-envs 1`, which is now standard for these sweeps until a permanent fix is merged).*

## Active Work
- **Double Loosen Sweeps:** Running Phase 2 sweeps for NVDA and AAPL, dropping both `reward-hold-penalty-scale` and `reward-turnover-penalty-scale` to `0.01` simultaneously.
- Exit Signal Phase 1 (deferred until base architectures are stabilized).

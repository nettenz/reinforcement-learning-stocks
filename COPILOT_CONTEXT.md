# COPILOT CONTEXT — RL Trading Agent (Development)

## Project
Reinforcement learning trading bot. Stack: Python, Gymnasium, Stable Baselines3, Streamlit, Yahoo Finance, NewsAPI.
Repo: https://github.com/netteNz/reinforcement-learning-stocks

## Current State
- Algorithm: PPO (Stable Baselines3)
- Environment: custom `TradingEnv` (Gymnasium), action space = Buy/Sell/Hold
- Observation: OHLCV + news sentiment columns (SentimentMean, SentimentStd, SentimentMin, SentimentMax, NewsCount)
- Reward: portfolio return + directional alignment + hold penalty + drawdown penalty + transaction cost
- Validation: walk-forward, multi-seed sweeps, experiment leaderboard CSV
- Dashboard: Streamlit analytics with signal analytics, experiment runner, leaderboard

## Immediate Dev Tasks (Priority Order)

### TASK 1 — Audit reward function for look-ahead bias
File: `src/trading_env.py`
Risk: `--reward-direction-scale` uses "next-step movement" — verify this does NOT use future price in reward at timestep t.
UNSAFE pattern:
  next_return = (price[t+1] - price[t]) / price[t]  # future leak
  reward += direction_scale * sign(action) * next_return
SAFE pattern:
  reward uses only price[t], price[t-1], portfolio state at t

### TASK 2 — Migrate observation space to stationary features
File: `src/market_data.py` and `src/trading_env.py`
Replace raw OHLCV with:
  - log_return = ln(close_t / close_{t-1})
  - volume_ratio = volume_t / volume.rolling(20).mean()
  - rsi_z = (rsi - rsi.rolling(60).mean()) / rsi.rolling(60).std()
  - atr_norm = ATR_14 / close_t
  - sentiment_delta = sentiment_t - sentiment_{t-1}

### TASK 3 — Add financial metrics to experiment leaderboard
File: `src/experiments.py`
Add columns: sharpe_ratio, sortino_ratio, max_drawdown, calmar_ratio, turnover
  sharpe = sqrt(252) * returns.mean() / returns.std()
  max_dd = (equity - equity.cummax()) / equity.cummax()).min()
Add benchmark row: buy-and-hold QQQ returns over same period

### TASK 4 — Migrate PPO → SAC with continuous action space
File: `src/train_bot.py`
  from stable_baselines3 import SAC
  Action space: gym.spaces.Box(low=-1.0, high=1.0, shape=(1,))
  -1 = full short, 0 = flat, +1 = full long
  SAC params: buffer_size=100_000, batch_size=256, ent_coef="auto", tau=0.005

### TASK 5 — Add position state to observation
The agent needs to know its current exposure.
Add to obs vector: [current_position, unrealized_pnl_pct, time_in_position]

## Code Conventions
- Python 3.10+
- Type hints everywhere
- Gymnasium API: `reset() -> (obs, info)`, `step() -> (obs, reward, terminated, truncated, info)`
- No raw `done` flag (deprecated)
- Logging via Python `logging` module, not print statements
- Config via argparse, not hardcoded constants

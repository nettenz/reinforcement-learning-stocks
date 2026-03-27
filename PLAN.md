# Reinforcement Learning Trading Bot - Strategy Plan

## Phase 1: Basic Bot (Completed)
- [x] Create custom Gymnasium environment (`trading_env.py`).
- [x] Generate mock price data (`mock_data.csv`).
- [x] Implement PPO training script (`train_bot.py`).

## Phase 2: Shorting Strategy (Planned)
### Action Space (Position-Based)
- `0`: Neutral (Cash) - Close all positions.
- `1`: Long - Close shorts, open/hold long.
- `2`: Short - Close longs, open/hold short.

### Reward Function
- **Inverse Returns:** Reward = -1 * (Price Change) when in Short state.
- **Borrowing Fees:** Constant penalty (e.g., 0.01%) for holding a Short position.
- **Squeeze Penalty:** Exponentially increasing negative reward for losses while short.

### Observation Space
- Current Stance: `[-1, 0, 1]` (Short, Neutral, Long).
- OHLCV + Portfolio Value.

## Phase 3: Advanced Features (To Be Planned)
- Technical Indicators (RSI, MACD, Bollinger Bands).
- Real-time data fetching (Binance or Yahoo Finance).
- Multi-asset trading.

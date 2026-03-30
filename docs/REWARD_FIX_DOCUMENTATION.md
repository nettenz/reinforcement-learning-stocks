# Reward Function Fix - Look-Ahead Bias Elimination

**Date:** March 30, 2026  
**Status:** [PASS] FIXED  
**Files Modified:** `trading_env.py`, `experiments.py`, `signal_analytics.py`, `analytics_dashboard.py`

---

## Problem

The original reward function used **future price information** to calculate rewards at timestep t, creating look-ahead bias that would cause production failure.

### Original (UNSAFE) Code

```python
# Line 96-97: Uses FUTURE price
next_price = max(float(self.df.loc[next_step, self.price_column]), 1e-8)
raw_step_return = (next_price / current_price) - 1.0  # ← LOOK-AHEAD!

# Line 186: Directional reward uses future return
directional_reward = target_position_value * raw_step_return  # ← LEAK!

# Line 189: Hold penalty uses future return
hold_penalty = -self.reward_hold_penalty_scale * abs(raw_step_return)  # ← LEAK!

# Line 182: Portfolio valuation uses future price
reward_new_net_worth = self.reward_balance + (self.reward_shares_held * next_price)  # ← LEAK!
```

### Why This Matters

**Training with look-ahead bias produces models that:**
- Perform well in backtests (they "know" the future)
- Fail catastrophically in production (no future information available)
- Overfit to unrealistic reward signals
- Cannot generalize to live trading

---

## Solution

Replace all future-based calculations with **realized returns** computed from past/current prices only.

### Fixed (SAFE) Code

```python
# Calculate REALIZED return using only past/current prices
prev_step = max(0, self.current_step - 1)
prev_price = max(float(self.df.loc[prev_step, self.price_column]), 1e-8)
realized_return = (current_price / prev_price) - 1.0 if self.current_step > 0 else 0.0

# Directional reward based on REALIZED return (what actually happened)
directional_reward = target_position_value * realized_return  # [OK] SAFE

# Hold penalty uses realized return
hold_penalty = -self.reward_hold_penalty_scale * abs(realized_return)  # [OK] SAFE

# Portfolio valuation uses CURRENT price
reward_new_net_worth = self.reward_balance + (self.reward_shares_held * current_price)  # [OK] SAFE
```

---

## Reward Function Components (Post-Fix)

The environment now uses a multi-component reward function with **NO LOOK-AHEAD BIAS**:

### 1. Portfolio Return
```python
portfolio_return = (reward_new_net_worth / reward_prev_net_worth) - 1.0
```
- Measures actual P&L from position changes
- Uses current portfolio valuation (current_price only)

### 2. Directional Reward
```python
directional_reward = target_position_value * realized_return
```
- Rewards position alignment with **realized** price movement
- Positive when: Long + price up, or Short + price down
- Uses `(current_price / prev_price) - 1` (not future price)

### 3. Hold Penalty
```python
hold_penalty = -scale * abs(realized_return) if position == 0 else 0.0
```
- Penalizes staying neutral when market is moving
- Uses magnitude of realized return

### 4. Action Bonus
```python
action_bonus = scale if trade_executed else 0.0
```
- Small bonus for taking positions
- Prevents collapse to all-Hold strategy

### 5. Drawdown Penalty
```python
drawdown = (peak_net_worth - current_net_worth) / peak_net_worth
drawdown_penalty = -scale * drawdown
```
- Penalizes portfolio drawdown from peak
- Risk management component

### Final Reward
```python
reward = (
    (return_scale * portfolio_return)
    + (direction_scale * directional_reward)
    + hold_penalty
    + action_bonus
    + drawdown_penalty
)
reward = clip(reward, -reward_clip, +reward_clip)
```

---

## Changes to Info Dictionary

The `info` dict returned by `env.step()` now includes:

**Changed:**
- `raw_step_return` → `realized_return` (renamed for clarity)

**Added:**
- `realized_return`: The (current_price / prev_price) - 1 value used in reward

**Unchanged:**
- All other reward component fields (`reward_direction`, `reward_portfolio_return`, etc.)

---

## Validation

### Tests Added

1. **`tests/test_reward_no_lookahead.py`**
   - Confirms reward calculation uses only past/current prices
   - Verifies directional reward uses realized returns
   - Checks portfolio valuation uses current price

2. **`tests/test_experiments_integration.py`**
   - Validates `experiments.py` captures new `realized_return` field
   - Ensures simulation pipeline works with fixed reward

### Test Results

```
[PASS] ALL SMOKE TESTS PASSED - NO LOOK-AHEAD BIAS DETECTED

Reward function now uses ONLY realized returns.
Agent learns from past/current prices, NOT future prices.
```

---

## Impact on Training

### Expected Changes

**Backtest Metrics:**
- May see initial drop in reported accuracy/returns (model can no longer cheat)
- Metrics will now reflect **realistic** production performance
- Walk-forward validation becomes more meaningful

**Model Behavior:**
- Agent learns from achievable signals only
- Better generalization to unseen data
- Production-ready reward structure

**Training Time:**
- May require slightly longer training (harder signal)
- Consider increasing timesteps by 20-30%

---

## Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `src/trading_env.py` | Core reward logic | Replaced future prices with realized returns |
| `src/experiments.py` | Info dict tracking | Added `realized_return` field to captured signals |
| `src/signal_analytics.py` | Comments added | Clarified that `future_return` is for evaluation only |
| `src/analytics_dashboard.py` | Help text updated | Clarified directional reward uses realized returns |

---

## What's Still OK to Use Future Prices For

**Evaluation/Backtesting (NOT Training):**
- `signal_analytics.py` computes `future_return` for truth label generation
- Used to score model predictions **after** they're made
- Never fed back into the training reward

This is standard practice in quant research: you can use future prices to **evaluate** past decisions, just not to **train** the decision-maker.

---

## Next Steps

### Immediate
- [x] Core reward function fixed
- [x] Experiments tracking updated
- [x] Dashboard help text clarified
- [x] Tests added and passing
- [x] Documentation written

### Follow-Up (Separate Tasks)
- [ ] Migrate observation space to stationary features (log returns, z-scored indicators)
- [ ] Add financial metrics (Sharpe, Sortino, Max DD) to leaderboard
- [ ] Migrate PPO → SAC with continuous action space
- [ ] Add benchmark (buy-and-hold QQQ) to experiments

---

## References

- **Analysis Document:** `RL_Stocks_Quant_Analysis.md` (Section: Critical Issues #1)
- **Context File:** `COPILOT_CONTEXT.md` (Task 1)
- **Test Files:** `tests/test_reward_no_lookahead.py`, `tests/test_experiments_integration.py`

---

## Verification Command

```bash
# Run all tests
source .venv/bin/activate
python tests/test_reward_no_lookahead.py
python tests/test_experiments_integration.py

# Should see:
# [PASS] ALL SMOKE TESTS PASSED - NO LOOK-AHEAD BIAS DETECTED
# [PASS] EXPERIMENTS.PY INTEGRATION TEST PASSED
```

---

**Author:** Copilot CLI  
**Review Status:** Ready for production use

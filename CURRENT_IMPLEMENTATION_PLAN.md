# Current Implementation Plan (Reality-Checked)

**Generated:** 2026-03-30  
**Status:** In Progress

## Current Phase

**Phase 2: Reward/Objective Modernization (Partially Complete)**  
We fixed look-ahead bias and added drawdown-aware shaping, but we have **not** fully shifted to a rolling risk-adjusted objective (Sharpe/Sortino) as the primary training reward.

## Reality Check: Did we successfully do this?

Target request:
- Shift reward from absolute return to rolling risk-adjusted metric (Sharpe/Sortino)
- Train agent to maximize return per unit risk and penalize volatile drawdowns

**Answer: Partially, not fully.**

What is done:
- Reward now uses realized returns only (no future leak)
- Includes drawdown penalty term
- Includes multi-term reward shaping (portfolio return, directional term, hold penalty, action bonus, drawdown penalty)

What is not done:
- No rolling Sharpe reward term in `TradingEnv.step()`
- No rolling Sortino reward term in `TradingEnv.step()`
- Reward is still centered on per-step return components, not explicit return-per-unit-risk optimization

## Evidence in Code

- `src/trading_env.py`
  - Reward terms currently combined as:
    - `reward_return_scale * portfolio_return`
    - `reward_direction_scale * directional_reward`
    - `hold_penalty`
    - `action_bonus`
    - `drawdown_penalty`
  - No rolling window volatility/downside-deviation state or Sharpe/Sortino computation in reward.

- `src/experiments.py`
  - Contains performance summarization fields and max drawdown stats
  - No active use of Sharpe/Sortino as the environment training reward

## Updated Plan

### Phase A (Complete)
- Eliminate look-ahead bias from reward
- Keep reward computed from realized information only

### Phase B (Current)
- Add rolling risk-adjusted reward mode to environment:
  - Rolling Sharpe reward option
  - Rolling Sortino reward option
  - Configurable lookback window and epsilon stability guard
- Keep current reward as fallback mode for backward compatibility

### Phase C
- Wire new reward mode through training and experiment CLI arguments
- Log reward-mode-specific diagnostics in experiment outputs

### Phase D
- Validate with controlled runs:
  - Compare old reward vs Sharpe mode vs Sortino mode
  - Track return, Sharpe, Sortino, max drawdown, stability across seeds

## Success Criteria

- Environment can run with `reward_mode = {legacy, sharpe, sortino}`
- Sharpe/Sortino modes compute reward from rolling window risk-adjusted returns
- No look-ahead introduced
- Experiment outputs clearly show objective mode and risk metrics
- At least one risk-adjusted mode improves return/drawdown tradeoff over legacy baseline

## Immediate Next Action

Implement `reward_mode`, rolling return buffers, and Sharpe/Sortino reward computation directly in `src/trading_env.py`, then propagate flags through `src/train_bot.py` and `src/experiments.py`.

# Assessment

## Honest assessment

The project has good experimentation infrastructure, but the core learning problem is still framed in a way that makes real progress unlikely.

The current system asks one RL agent to learn all of the following at once:
- market signal extraction
- directional forecasting
- execution timing
- position sizing
- turnover discipline
- transaction cost awareness
- drawdown control

That is too much for the current setup.

## What is working

- The repository has a real custom environment and a reproducible training pipeline.
- The experiment runner already supports walk-forward validation, multi-seed runs, and benchmark comparison.
- The codebase has useful diagnostics around rewards, risk metrics, and leaderboard history.
- The project is far enough along that it can be recovered without starting over.

## What is not working

### 1. Reward design is doing too much

The reward is a blend of multiple incentives: portfolio return, directional shaping, hold penalty, action bonus, turnover penalty, and drawdown penalty.

This makes it easy for the agent to optimize shaped behavior instead of true economic quality.

### 2. The task is not sufficiently simplified

The agent uses continuous target weights, which makes the control problem harder than necessary. It is trying to solve forecasting and sizing at the same time.

### 3. The evaluation stack is partially misaligned

Metrics like actionable accuracy and trade win rate are useful diagnostics, but they are not the same thing as a profitable and robust strategy after costs.

### 4. There are too many knobs too early

The experiments framework is strong, but too much time can be wasted sweeping reward scales and hyperparameters before the base task is proven learnable.

### 5. The development flow mixes learning and validation concerns

There is a split-aware experiment runner, but the project still risks spending effort on policies that look promising under proxy metrics rather than real out-of-sample economic performance.

## Root conclusion

The project is not one reward tweak away from success.

The main issue is not lack of effort or lack of infrastructure. The issue is that the current RL problem definition is too ambitious and too shaped.

## Most likely current failure mode

The agent is learning policy behavior that scores well on proxy objectives while failing to uncover a durable market edge.

That means more reward tuning is likely to continue consuming time without materially improving real performance.

## Recovery direction

The fastest path forward is:
1. prove there is predictive signal without RL
2. simplify the environment and reward
3. reduce the action space
4. promote only on economic out-of-sample results
5. reintroduce complexity only after a simple baseline works

## Bottom line

This project is recoverable, but only if the next phase prioritizes proving learnability over adding more tuning.

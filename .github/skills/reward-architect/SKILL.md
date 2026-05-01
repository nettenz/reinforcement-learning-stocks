---
name: reward-architect
description: 'Diagnose RL reward misalignment, reward hacking, and economic objective drift for SAC agents. Use when gate failures or agent behavior suggest reward miscalibration. Adapted for the 6-gate promotion framework, max_weight_delta structural fix, and known reward component risks in this codebase.'
argument-hint: 'What reward failure mode, gate failure, or behavior anomaly should be diagnosed? (e.g. alpha gate failing despite good accuracy, AMD CV instability, direction_scale look-ahead risk)'
user-invocable: true
---

# Reward Architect

Diagnose whether the RL reward system is teaching economically correct behavior.

## Objective
Improve reward design so the SAC agent learns behavior that is economically meaningful, robust, and survives out-of-sample evaluation.

## Project Context (read before diagnosing)
- **Algorithm:** SAC. Reward computed in `TradingEnv._compute_reward` in `src/trading_env.py`.
- **Execution:** `next_bar` mode. Reward must reference only prices available at or before bar T's close.
- **Known reward components and risks:**

| Component | Parameter | Risk |
|-----------|-----------|------|
| Portfolio return | `reward_return_scale=1.0` | Dominates all penalties if miscalibrated |
| Directional shaping | `reward_direction_scale=0.35` | **HIGH RISK** — potential look-ahead if uses bar T close |
| Hold penalty | `reward_hold_penalty_scale=0.01` | Can suppress action entirely if too high |
| Turnover penalty | `reward_turnover_penalty_scale=0.10` | Ineffective without `max_weight_delta` cap |
| Action bonus | `reward_action_bonus_scale=0.02` | Can incentivize churn if dominant |
| Drawdown penalty | `reward_drawdown_penalty_scale=0.10` | Under-weighted — AMD instability may need this raised |
| Reward clip | `reward_clip=1.0` | Can mask extreme behavior |

- **The overtrade root cause is NOT a reward problem.** It was a structural cap issue (`max_weight_delta_per_step=0.0`). Do not recommend increasing turnover penalty as a fix for 99%+ trade rates — set the cap instead.
- **Reward penalty tuning is only effective after `max_weight_delta=0.10` is set.** Without the cap, the return signal dominates all penalties regardless of scale.
- **NVDA champion config (reference baseline):**
  ```
  reward_mode: sharpe
  reward_hold_penalty_scale: 0.01
  reward_turnover_penalty_scale: 0.10
  reward_direction_scale: 0.35  ← audit this before trusting it
  reward_action_bonus_scale: 0.02
  reward_drawdown_penalty_scale: 0.10
  reward_clip: 1.0
  max_weight_delta_per_step: 0.10
  ```

## Default Focus Files
- `src/trading_env.py` — `TradingEnv._compute_reward`, `PositionManager`, `_apply_max_weight_delta`
- `src/experiments.py` — reward config wiring, CLI args
- `data/experiment_leaderboard.csv` — master leaderboard with reward component columns
- `data/experiment_reward_leaderboard.csv` — per-step reward breakdown

## Core Procedure

### 1. Confirm the cap is set
Before any reward diagnosis, verify:

```python
import pandas as pd
lb = pd.read_csv('data/experiment_leaderboard.csv')
label = 'your_label'
sweep = lb[lb['run_label'].str.contains(label, na=False)]
print(sweep['max_weight_delta_per_step'].value_counts())
```

If `max_weight_delta_per_step=0.0` → this is a structural bug, not a reward problem. Fix the cap first.

### 2. Audit the direction term look-ahead risk
The `reward_direction_scale` term is the highest-risk component in this codebase.

```powershell
python -c "
import inspect
from src.trading_env import TradingEnv
src = inspect.getsource(TradingEnv._compute_reward)
print(src)
" 2>&1 | Select-String -Pattern "direction|close|price|next|shift"
```

- If direction uses `next_bar` execution price → acceptable
- If direction uses `df.iloc[current_step]['Close']` or any same-bar reference → **critical leakage, fix before any sweep**

### 3. Check reward-to-objective alignment
Evaluate whether current reward config produces:
- Trade rate in 60–75% band (Gate 6) — if not, cap is the fix, not penalty scaling
- Positive test alpha vs QQQ (Gate 3) — if failing despite cap set, check if direction term is dominating
- CV < 1.0 across seeds (Gate 5) — if CV > 4.0, reward config may not fit the ticker's dynamics

### 4. Detect reward hacking risks
- **Action bonus exploitation:** If `reward_action_bonus_scale` is high relative to return scale, agent trades to collect bonuses not returns
- **Churn incentive:** If turnover penalty is set but cap is not → penalty is noise, return signal dominates → agent churns
- **Hold-bias collapse:** If hold penalty + turnover penalty both active at high values → agent learns to not trade at all (under-trade pattern, seen in NVDA stationary sweeps)
- **Direction dominance:** If `reward_direction_scale=0.35` and return signal is weak → agent optimizes directional hits not economic return

### 5. Diagnose the failure mode
Classify one primary issue:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Trade rate 99%+, penalties ignored | `max_weight_delta=0.0` | Set cap to 0.10 |
| Trade rate < 40%, agent barely trades | Hold + turnover penalty both too high | Drop one, keep cap |
| CV > 4.0 across all seeds | Ticker dynamics incompatible with reward config | Investigate env fit, not reward tuning |
| Alpha fails, accuracy passes | Degenerate always-long in bullish test period | Check Gate 6, not reward |
| Direction term suspicious | `direction_scale` using same-bar price | Fix look-ahead before any further work |
| 2/5 seeds pass, 3 collapse | Underfitting — needs more timesteps | Try 60k before changing reward |

### 6. Propose reward variants
Only propose variants after confirming:
1. `max_weight_delta=0.10` is set
2. Direction term look-ahead is resolved
3. The failure mode is genuinely reward-related

**Variant A — Conservative (stability-first):**
```
reward_direction_scale: 0.10   (reduced from 0.35)
reward_action_bonus_scale: 0.0 (removed)
reward_drawdown_penalty_scale: 0.20 (increased)
reward_turnover_penalty_scale: 0.05 (reduced — cap does the work)
```

**Variant B — Balanced (current NVDA champion baseline):**
```
reward_direction_scale: 0.35
reward_action_bonus_scale: 0.02
reward_drawdown_penalty_scale: 0.10
reward_turnover_penalty_scale: 0.10
```

**Variant C — Return-focused (aggressive):**
```
reward_direction_scale: 0.0    (removed — pure return signal)
reward_action_bonus_scale: 0.0 (removed)
reward_drawdown_penalty_scale: 0.05
reward_turnover_penalty_scale: 0.05
```

## Required Output Format

1. **Cap verification result**
2. **Direction term look-ahead status**
3. **Current reward system summary**
4. **Misalignment risks**
5. **Reward hacking risks**
6. **Failure mode classification**
7. **Recommended variants (only if cap and direction are clean)**
8. **Execution-ready sweep commands**
9. **Success criteria**
10. **Leaderboard comparability impact (REQUIRED)**
11. **Recommendation: proceed / fix direction term / fix cap / blocked**

## Constraints
- Never recommend increasing turnover penalty to fix overtrade — set the cap
- Never diagnose reward misalignment before confirming `max_weight_delta` is set
- Never recommend reward variants when direction term look-ahead is unresolved
- Never recommend RL reward work for AAPL until leakage audit clears
- Prefer removing reward components over adding new ones
- AMD CV > 4.0 is an environment fit issue — do not treat as reward miscalibration without more evidence
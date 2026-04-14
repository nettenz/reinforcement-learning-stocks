# Gemini Handoff: Reward Mode Flag Alignment & Hybrid Logic Fix

## 🚨 Status Overview
During the validation of `run_directional_ablation.sh` for Apple Silicon (MPS), a critical logic gap was identified in how `src/trading_env.py` handles reward-shaping flags across different modes.

## 🔍 The Problem: "Flag Ghosting"
While the CLI and Dashboard correctly parse and pass flags like `--reward-direction-scale`, the underlying `RewardEvaluator` engine ignores these terms when certain modes are active.

### Affected Logic (`src/trading_env.py`)
```python
if self.mode == "sharpe":
    risk_metric = self._sharpe()
    base_reward = self.return_scale * risk_metric # <--- directional_reward is ignored here
elif self.mode == "sortino":
    risk_metric = self._sortino()
    base_reward = self.return_scale * risk_metric # <--- directional_reward is ignored here
else:  # legacy
    # directional_reward is ONLY used here
    base_reward = (self.return_scale * portfolio_return) + (self.dir_scale * directional_reward)
```

**Impact:**
- Ablation studies (like `run_directional_ablation.sh`) using `REWARD_MODE="sharpe"` will show NO variance between different `direction_scale` values, leading to false conclusions.
- The Dashboard UI allows tuning these sliders in all modes, but they only "work" in `legacy` mode.

## 🛠️ Proposed Fix: Hybrid Reward Architecture
To ensure flags are consistently handled regardless of the core risk metric (Sharpe/Sortino), the `RewardEvaluator.calculate` method should be refactored to a hybrid model.

### Target Implementation
```python
# 1. Calculate the core risk-adjusted base
if self.mode == "sharpe":
    risk_metric = self._sharpe()
    base_reward = self.return_scale * risk_metric
elif self.mode == "sortino":
    risk_metric = self._sortino()
    base_reward = self.return_scale * risk_metric
else: # legacy
    base_reward = self.return_scale * portfolio_return

# 2. Add universal regularizers (The "Hybrid" Fix)
# This ensures dir_scale is ALWAYS active if provided (>0)
total = base_reward + (self.dir_scale * directional_reward) + hold_penalty + action_bonus + turnover_penalty + dd_penalty
```

## ⚠️ Immediate Workaround
The `run_directional_ablation.sh` script has been updated to use `REWARD_MODE="legacy"`. This ensures the current experiments are mathematically valid while the architectural fix is pending.

## 📋 Next Steps for Implementation Agent
1.  **Refactor `src/trading_env.py`**: Update `RewardEvaluator.calculate` to the hybrid model described above.
2.  **Verify via CLI**: Run a 2-seed experiment with `sharpe` mode and two different `direction_scale` values; verify the `reward` output in the logs actually changes.
3.  **Update Dashboard**: Ensure the "Insights" tool recognizes that `direction_scale` is now a valid hyperparameter for all reward modes.

---
**Author:** Gemini CLI
**Date:** 2026-04-06
**Context:** Directional Ablation Validation (Apple Silicon/MPS)

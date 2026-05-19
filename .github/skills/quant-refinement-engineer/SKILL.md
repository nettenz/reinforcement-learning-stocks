---
id: quant-refinement-engineer
name: Quantitative Refinement & Experimentation Engineer
description: Technical framework for refactoring RL environments, designing differential trading experiments, and running cross-platform verification pipelines to eliminate algorithmic rot and reward hacking.
version: 1.0.0
capabilities:
  - environment-mutation-protocols
  - differential-experiment-design
  - cross-platform-pipeline-execution
  - maskable-ppo-integration
  - gate-repromotion-validation
---

## Overview

The `quant-refinement-engineer` skill translates diagnostic algorithmic audits (such as policy collapse, value overestimation, and reward hacking) into precise codebase mutations, rigorous experimental designs, and executable CLI pipelines. 

This skill ensures that environment modifications (e.g., removing action loops, enforcing economic drag, and integrating action masking) are executed systematically across platforms (Windows/macOS), keeping champion models (NVDA, AMD, MU) aligned with strict institutional-grade validation baselines before production promotion.

---

## Dependencies

To execute this skill, the agent must have access to:
* **Core Environment Code:** Python source files managing the simulation layer (`src/trading_env.py`, `src/exit_manager.py`).
* **Configuration Layer:** Centralized hyperparameter and environment profiles (`configs/ensemble_config.json`, `configs/training_sweep.yaml`).
* **Execution Toolkit:** Virtual environment entry points, build automation tools, and ML tracking systems (TensorBoard, Weights & Biases).
* **Extended Libraries:** Deep reinforcement learning frameworks supporting discrete action masking (e.g., `stable-baselines3`, `sb3-contrib`).

---

## Technical Workflow

The agent must execute engineering and experimentation tasks across four distinct operational phases:

### 1. Environment Codebase Mutation Protocols
The agent will systematically execute code refactoring within `src/trading_env.py` and configuration updates to eliminate environment loopholes.
* **Economic Drag Enforcement:** Locate the reward generation loop. Hardcode or map parameters to ensure transaction penalties, spread costs, and borrow costs are directly deducted from the step reward:
  ```python
  # Target implementation framework within TradingEnv.step()
  reward_ignore_transaction_cost = False
  ```

* **Action Bonus Excision:** Eliminate structural reward-hacking loops by removing positive constants tied purely to trade execution flags. Swap out transaction bonuses for a turnover penalty scalar.
* **Observation Space Expansion:** Append the `cooldown_active` boolean flag (from the Min-Hold tracker) as a normalized scalar ($0.0$ or $1.0$) to the observation vector array so the model natively registers structural temporal constraints.

### 2. Action Masking Implementation (`MaskablePPO`)

To resolve constraint friction and lag spikes caused by hard environment blocks (like the 3-bar hold on AMD), the agent must convert the model routing from standard PPO to an explicit action-masked framework.

* **Mask Generation Function:** Implement an explicit `action_masks()` method inside `TradingEnv`:
```python
def action_masks(self) -> np.ndarray:
    # Returns a boolean array indicating valid actions
    # e.g., if min-hold is active, invalid actions are masked out (False)
    return np.array([True, False]) if self.cooldown_active else np.array([True, True])
```


* **Algorithm Adaptation:** Upgrade training execution scripts to swap `stable_baselines3.PPO` for `sb3_contrib.MaskablePPO`, preventing the model from building up toxic latent disadvantage values ($\hat{A}_t \ll 0$) on restricted frames.

### 3. Differential Experiment Design

Every programmatic fix must be treated as an isolated treatment variant ($V_1$) to be statistically tested against the current broken baseline baseline configuration ($V_0$).

* **Control ($V_0$):** The legacy production model running under legacy settings (e.g., `reward_ignore_transaction_cost = True`).
* **Treatment ($V_1$):** The mutated architecture containing the targeted fix.
* **Validation Parameters:** Run identical seeds, lookback intervals, and market regimes across variants. Evaluate tracking metrics: Policy Entropy stability, Value Network MSE, Turnover Rate reduction, and Max Drawdown containment.

### 4. Cross-Platform Execution Framework

The agent must provide bulletproof, platform-agnostic terminal execution blocks to invoke the engineering pipelines cleanly on both Windows (PowerShell/CMD) and macOS/Linux (Zsh/Bash).

---

## Mandatory Output Format

The agent must output its operational blueprint in the exact structure defined below.

### 1. Experiment Design Specification

A clear outline defining the experimental boundaries.

* **Target Tickers:** Specify model variants to run (e.g., `MU-Retrain-EntropyFix`, `AMD-MaskedPPO`).
* **Hyperparameter Matrix Changes:** Clear key-value diff blocks detailing configuration updates.
* **Hypothesis Criteria:** Mathematical statements of success (e.g., $\text{Value MSE}_{V_1} < \text{Value MSE}_{V_0}$ by at least 30%; Policy Entropy $H(\pi) > 0.40$).

### 2. Automated Refactoring Code Diff

Provide clean, copy-pasteable Unified Git Diffs or direct file mutation templates showing exactly where code needs to change in `src/trading_env.py` or configuration files.

### 3. Cross-Platform Execution Block

Provide explicit terminal code blocks structured cleanly for easy copy-pasting.

#### 🌐 macOS / Linux (Zsh & Bash Terminal-Centric Workflow)

```bash
# 1. Navigate to repository root and activate virtual environment
cd /path/to/your/algorithmic-trading-repo
source .venv/bin/activate

# 2. Verify dependencies include the maskable environment packages
pip install sb3-contrib

# 3. Execute individual target model experiment sweeps via python3 CLI
python3 src/train.py --config configs/ensemble_config.json --ticker MU --mode retrain_entropy
python3 src/train.py --config configs/ensemble_config.json --ticker AMD --use_action_masking

# 4. Launch TensorBoard to track real-time Value Network Loss and Policy Entropy
tensorboard --logdir=runs/quant_experiments --port=6006
```

#### 🪟 Windows (PowerShell Execution Policy & Commands)

```powershell
# 1. Navigate to repository root and activate virtual environment safely
cd "C:\path\to\your\algorithmic-trading-repo"
.venv\Scripts\Activate.ps1

# 2. Verify dependencies include the maskable environment packages
pip install sb3-contrib

# 3. Execute individual target model experiment sweeps via standard python CLI
python src/train.py --config configs/ensemble_config.json --ticker MU --mode retrain_entropy
python src/train.py --config configs/ensemble_config.json --ticker AMD --use_action_masking

# 4. Launch TensorBoard to monitor live optimization changes
tensorboard --logdir=runs/quant_experiments --port=6006
```

### 4. Success Metrics & Promotion Acceptance Criteria

A rigorous quantitative scorecard defining what qualifies a model for promotion back to the main offline framework.

* **Entropy Bounds:** Realized out-of-sample entropy tracking limits.
* **Slippage & Drag Realism Test:** Minimum validation score when transaction costs are completely uninsulated.
* **The 6-Gate Re-Evaluation Hook:** Clear passing directives mapping the variant back into the offline gates framework for ultimate deployment verification.

---

## Common Mistakes to Avoid

> ❌ **Asymmetric Environment Signatures:** Modifying reward logic or adding action masks in the training code without updating the evaluation wrappers, leading to broken data streams and immediate state-contract mismatches in production.
> ❌ **Relative Path Breakage across OS Environments:** Using hardcoded Unix forward-slashes (`/`) or Windows back-slashes (`\`) inside Python path scripts. Always enforce platform-agnostic file pathing using `os.path` or `pathlib.Path`.
> ❌ **Failing to Verify Virtual Environment Scope:** Running execution pipelines globally instead of forcing the exact environment layer target, masking missing dependencies (like missing `sb3-contrib` modules) until runtime execution fails.
> ❌ **Over-tuning Entropy Weights ($\beta$):** Cranking up the entropy penalty so high to fix an always-long model (like MU) that the agent drops down into complete white-noise random behavior, breaking structural alpha entirely.

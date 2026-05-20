---
id: wave-aware-refinement-fallback
name: Wave-Aware RL Refinement & Fallback Exit Workflow
description: 'Use when refining Binary PPO trading strategies with Elliott-style wave awareness, cleaner exits, telemetry-first diagnostics, and a conservative fallback path if wave features do not improve expectancy.'
version: 1.0.0
capabilities:
  - wave-aware-feature-design
  - fallback-exit-rules
  - telemetry-first-diagnostics
  - low-friction-recovery-planning
  - expectancy-preserving-validation
---

## Overview

The `wave-aware-refinement-fallback` skill packages the workflow used to refine a Binary PPO trading system when the current policy is too buy-skewed, exit-light, or constrained by min-hold friction. It translates the chat’s working hypothesis into a reusable process: add wave-aware structure only if it improves measured behavior, and fall back to a simpler conservative exit stack if it does not.

This skill is intended for cases where the strategy looks promising on paper but needs better exit discipline, lower reward distortion, and stronger out-of-sample robustness before further promotion.

## Dependencies

To execute this skill, the agent should have access to:
* **Policy telemetry:** logits before masking, action probabilities, entropy traces, advantage estimates, and critic value outputs.
* **Environment state:** `min_hold_bars`, cooldown flags, `ExitManager` state, and realized reward components.
* **Experiment artifacts:** leaderboards, sweep outputs, audit CSVs, and config files for NVDA, AMD, and MU.
* **Training code:** environment, experiments, and exit-rule wiring for Binary PPO and action masking.

## Technical Workflow

The agent must follow a staged refinement process with an explicit fallback branch.

### 1. Diagnose the Current Failure Mode
* Check whether the policy is static long, under-exiting, or fighting the min-hold constraint.
* Measure entropy, long/flat ratio, exit frequency, and confidence distribution.
* Compare NVDA, AMD, and MU to identify whether the issue is structural, ticker-specific, or regime-specific.
* Confirm whether poor performance is due to algorithmic behavior rather than execution noise.

### 2. Add Wave-Aware Context Carefully
* Introduce compact Elliott-style features only if they can be computed without look-ahead.
* Prefer swing structure, retracement depth, pivot spacing, and momentum-change context over heavy handcrafted rules.
* Keep the feature set small and interpretable.
* Validate that new features improve decision quality without making the policy overfit to local noise.

### 3. Separate Entry Logic From Exit Logic
* Keep PPO focused on directional bias and regime selection.
* Move exits into `ExitManager` or a comparable rule layer.
* Test conservative exit candidates such as trailing stop, profit take, and wave-break invalidation.
* Compare the result against a `no_exit` baseline on the same split.

### 4. Preserve Realism and Remove Reward Distortion
* Ensure transaction costs are always active during realism checks.
* Avoid bonuses that reward trading for its own sake.
* Keep hold penalties and turnover penalties interpretable.
* Use action masking and cooldown observations rather than teaching the policy to guess impossible actions.

### 5. Execute the Fallback Branch
If wave-aware changes do not improve validation quality, immediately fall back to the simpler conservative path:
* disable any added wave feature candidates that do not help
* keep the original feature pipeline intact
* use the validated low-friction or no-exit configuration
* prioritize telemetry and exit rules over additional model complexity
* rerun the control baseline before attempting another wave-inspired modification

### 6. Validate Against Expectancy, Not Just PnL
* Evaluate cumulative return, max drawdown, win rate, trade rate, and Sharpe together.
* Do not treat a single positive run as proof of robustness.
* Prefer strategies that improve expectancy and drawdown while keeping turnover explainable.
* Reject configurations that only look good on one split or one seed.

## Mandatory Output Format

The agent must return a concise refinement plan in the following order:

### 1. Strategy Health Summary
* Active ticker/model set
* Current behavior diagnosis
* Constraint-friction classification

### 2. Wave-Aware Feature Plan
* Proposed features
* Look-ahead risk check
* Expected behavioral effect

### 3. Exit Design Plan
* Selected exit rule candidates
* Fallback exit rule if wave logic fails
* Comparison baseline

### 4. Fallback Decision
* Keep wave features / drop wave features / revert to conservative baseline
* Reason for the choice

### 5. Validation Plan
* Metrics to compare
* Seed and split requirements
* Promotion-readiness criteria

## Common Mistakes to Avoid

> ❌ Treating a buy-heavy policy as wave conviction instead of entropy collapse.
>
> ❌ Adding Elliott-style rules that peek into the future or encode the answer directly.
>
> ❌ Letting the exit layer become a hidden reward hack for a weak entry policy.
>
> ❌ Keeping wave features after they fail the fallback check.
>
> ❌ Optimizing for raw return only and ignoring drawdown, turnover, and generalization.

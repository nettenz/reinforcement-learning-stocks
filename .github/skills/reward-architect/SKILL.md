---
name: reward-architect
description: 'Design, audit, and iterate RL trading reward functions for better out-of-sample alpha, robustness, and deployable behavior. Use for src/trading_env.py, src/experiments.py, src/signal_analytics.py, leaderboard artifacts, and reward-driven experiment planning when reward misalignment or reward hacking is suspected.'
argument-hint: 'What reward setup, experiment batch, or failure mode should be analyzed?'
user-invocable: true
---

# Reward Architect

Quantitative reward-design workflow for reinforcement-learning trading systems.

## Objective
Improve the reward system so the agent learns behavior that is economically meaningful, robust across seeds, and more likely to produce positive out-of-sample return and alpha.

Use this skill when:
- validation metrics look decent but test alpha/return are weak
- the agent may be overtrading or selectively gaming metrics
- reward terms may be misaligned with deployable performance
- you need concrete reward variants and a tightly scoped experiment plan

## Default Focus Files
- `src/trading_env.py`
- `src/experiments.py`
- `src/signal_analytics.py`
- `data/experiment_leaderboard.csv`
- `data/experiment_reward_leaderboard.csv`
- `data/experiment_summary.json`
- relevant experiment snapshots and reports when available

## Core Procedure
0. Confirm delivery mode
- Ask whether the user wants:
  - analysis-only output
  - implementation-inclusive output with patch proposals
- Default behavior: include patch proposals unless the user asks for review-only.

1. Decompose the current reward
- Identify every active reward component in `RewardEvaluator` and surrounding environment logic:
  - realized / portfolio return
  - directional shaping
  - hold penalty
  - action bonus
  - drawdown penalty
  - clipping
  - any transaction-cost or trade-penalty interactions
- Determine which terms dominate behavior.
- Identify whether any config flags are exposed but not actually used.

2. Check reward-to-objective alignment
Evaluate whether the reward is aligned with:
- positive test cumulative return
- positive test alpha vs benchmark
- stable trade win rate
- acceptable drawdown
- realistic turnover and trade frequency
- generalization from validation to test

Flag patterns such as:
- strong validation but weak test alpha
- high actionable accuracy with negative return
- low-support “good-looking” metrics
- reward components optimizing local correctness rather than portfolio quality

3. Detect reward hacking risks
Search for:
- action bonus exploitation
- oscillation or churn strategies
- hold-penalty avoidance without real edge
- clipping masking poor behavior
- sparse-support metric inflation
- reward behavior that looks good only on one regime or one seed

4. Map cost semantics
Trace whether:
- transaction costs are applied in execution only, reward only, or both
- trade penalties duplicate other frictions
- turnover is penalized explicitly or only indirectly
- reward-related cost flags are wired correctly

If a reward/cost flag exists but is not functionally used, classify it as a correctness issue, not an enhancement.

5. Diagnose likely reward failure mode
Classify the current issue into one or more buckets:
- return misalignment
- turnover/churn bias
- over-penalized holding
- under-penalized drawdown
- risk metric instability (rolling Sharpe/Sortino noise)
- cost-insensitive reward
- low-support metric gaming

6. Propose 3 reward variants
Always propose:
- **Variant A — Conservative**
  - stability-first
  - stronger drawdown + turnover control
  - lower or zero action bonus
- **Variant B — Balanced**
  - default candidate
  - realized return primary
  - moderate directional shaping
  - moderate drawdown / turnover control
- **Variant C — Aggressive**
  - higher return seeking
  - lighter penalties
  - still economically interpretable

For each variant include:
- intended behavior
- tradeoffs
- exact parameter changes
- code-level patch sketch
- recommended sweep variables
- success criteria
- failure interpretation

7. Define the next experiment batch
Recommend a small, hypothesis-driven batch, not a broad random sweep.

Each experiment must specify:
- goal
- why it matters
- exact variables to change
- what to hold constant
- success criteria
- failure interpretation

Prioritize:
- information gain first
- then performance gain
- then implementation cost

8. Preserve research discipline
- Favor multi-seed robustness over best single run.
- Do not treat higher validation metrics as sufficient.
- Distinguish evidence-backed conclusions from hypotheses.
- Keep changes incremental and testable.
- Call out when reward changes break historical leaderboard comparability.

## Decision Logic
- If test alpha is negative while validation metrics are good: classify as reward misalignment candidate.
- If action bonus is present and turnover is high: suspect churn incentive.
- If directional reward dominates return quality: reduce directional shaping and increase economic realism.
- If drawdown remains poor despite decent win rate: strengthen downside control.
- If rolling Sharpe/Sortino is noisy early in episodes: propose warm-up handling or alternative calibration.
- If no reward variant clears test alpha and stability thresholds: recommend pivot to environment realism before further reward complexity.

## Required Output Format
Always return sections in this exact order:
1. **Current reward system summary**
2. **Strengths**
3. **Misalignment risks**
4. **Reward hacking risks**
5. **Recommended reward variants**
6. **Patch plan (code-level)**
7. **Experiment plan**
8. **Success criteria**
9. **Leaderboard comparability impact (REQUIRED)**
10. **Recommendation: proceed / revise / pivot**

## Leaderboard Comparability Rule (MANDATORY)
For every recommendation set, include:
- impact level: Low / Medium / High
- reason:
  - reward semantics changed?
  - metric interpretation changed?
  - feature/input space changed?
  - historical winner comparisons weakened?

Never omit this.

## Constraints
- Do not introduce future leakage.
- Do not optimize purely for classification-style metrics.
- Do not recommend reward formulas that are not economically interpretable.
- Do not silently break experiment semantics.
- Prefer small, testable changes over reward rewrites.
- Keep compatibility with `src/experiments.py` and downstream analytics unless explicitly told otherwise.

## Quality Checks Before Finalizing
- Every diagnosis ties back to concrete experiment evidence or code behavior.
- Every proposed reward variant is economically interpretable.
- Every experiment recommendation is hypothesis-driven.
- Comparability impact is explicit.
- Success/failure criteria are measurable using existing artifacts.
- Conclusions distinguish evidence from hypothesis.

## Example Invocations
- `/reward-architect Diagnose why strong validation accuracy still produces negative test alpha.`
- `/reward-architect Review action bonus, hold penalty, and drawdown penalty interactions in src/trading_env.py.`
- `/reward-architect Propose a turnover-aware reward variant and the next experiment batch.`
- `/reward-architect Design conservative, balanced, and aggressive reward variants for the current SAC setup.`

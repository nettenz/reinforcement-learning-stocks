# Stages

## Stage 1 — Prove signal exists without RL

Goal:
Determine whether the feature set contains usable predictive information before spending more time on RL.

Actions:
- Build a supervised baseline for next-step or next-horizon return prediction.
- Use the same stationary features already available in the project.
- Convert predictions into a simple trading rule:
  - long if prediction exceeds threshold
  - short if prediction is below threshold
  - otherwise flat
- Evaluate on walk-forward validation and test splits after costs.

Success criteria:
- Out-of-sample performance is better than naive baselines.
- Alpha versus benchmark is positive often enough to justify further work.
- Behavior remains stable across seeds or model retrains.

Failure meaning:
- If this stage fails, the main issue is likely weak signal, not weak RL tuning.

---

## Stage 2 — Simplify the RL task

Goal:
Create a learnable RL setup that does not force the agent to solve everything at once.

Actions:
- Replace continuous target weights with a smaller discrete action space:
  - flat / long / short
  - or flat / long only
- Use a minimal reward based on post-cost economic return.
- Remove action bonus, hold penalty, and directional shaping from training reward.
- Keep drawdown and win rate as evaluation metrics, not main reward terms.

Success criteria:
- Training becomes more stable across seeds.
- The agent produces interpretable policies.
- Out-of-sample results no longer depend on reward tricks.

---

## Stage 3 — Freeze the experiment family

Goal:
Stop spending time on too many interacting variables.

Actions:
- Fix one ticker, one interval, one split protocol, one execution mode, and one reward definition.
- Only sweep a very small set of variables:
  - seed
  - timesteps
  - learning rate
- Avoid broad reward-weight sweeps until the base setup proves itself.

Success criteria:
- Results become easier to compare honestly.
- Failures can be traced to one cause at a time.

---

## Stage 4 — Align evaluation with trading reality

Goal:
Make the system optimize what actually matters.

Actions:
- Use economic out-of-sample metrics as primary selection criteria:
  - cumulative return after costs
  - alpha versus benchmark
  - Sharpe / Sortino
  - max drawdown
- Keep actionable accuracy and trade win rate as secondary diagnostics only.
- Promote models only if they pass minimum real-world performance gates.

Success criteria:
- Top-ranked models are also economically credible.
- Proxy metrics stop dominating model selection.

---

## Stage 5 — Reintroduce complexity only after success

Goal:
Add sophistication only after the simple system works.

Actions:
- Add sizing back after discrete policies show real edge.
- Re-test continuous control only if simpler policies are already robust.
- Add sentiment or other auxiliary signals only when they prove measurable value.
- Expand to more instruments only after one family of setups works reliably.

Success criteria:
- Each added layer improves results measurably.
- Complexity is justified by performance, not curiosity.

## Final principle

Each stage must earn the right to move to the next one.
Do not move forward just because the infrastructure is available.

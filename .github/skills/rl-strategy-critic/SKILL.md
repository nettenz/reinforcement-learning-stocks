---
id: rl-strategy-critic
name: Reinforcement Learning Strategy Critic & Pattern Auditor
description: Technical framework for auditing, critiquing, and diagnosing RL pattern degeneration, policy collapse, value function divergence, and reward exploitation within discrete action spaces.
version: 1.0.0
capabilities:
  - policy-entropy-analysis
  - value-function-divergence-tracking
  - reward-shaping-critique
  - regime-shift-epistemic-audit
  - action-space-saturation-detection
---

## Overview

The `rl-strategy-critic` skill provides a rigorous diagnostic lens focused specifically on the internal mechanics of Reinforcement Learning (RL) policies—such as our Binary PPO architectures deployed on NVDA, AMD, and MU. 

While operational performance can be tracked via standard execution metrics, this skill identifies underlying algorithmic rot before it manifests as catastrophic capital drawdowns. It treats the model not as a black box, but as a dynamic optimization system prone to policy collapse, value network overestimation, reward hacking, and out-of-distribution (OOD) generalization failures when confronted with real-world market regimes.

---

## Dependencies

To execute this skill, the agent must have access to:
* **Policy Telemetry:** Softmax probabilities for actions, step-by-step advantage estimates $\hat{A}_t$, and target value estimations $V(s)$.
* **Training Logs & Baselines:** Historical distribution profiles, baseline policy entropy curves, and loss landscapes from the 6-gate promotion phase.
* **Environment Trajectories:** State vectors $s_t$, executed actions $a_t$, realized environment rewards $r_t$, and `ExitManager` state flags.

---

## Technical Workflow

The agent must execute critiques across five specialized deep-algorithmic focus areas:

### 1. Policy Entropy & Action Space Collapse
For a Binary PPO agent restricted to a discrete long/flat ($1 \mid 0$) action space governed by a Min-Hold constraint, the policy is highly vulnerable to structural polarization.
* **Entropy Tracking:** Compute the policy entropy $H(\pi)$ to measure behavioral diversity:

$$H(\pi) = -\sum_{a \in \{0,1\}} \pi(a \mid s) \log \pi(a \mid s)$$

* **Action Saturation & Bang-Bang Control:** Diagnose instances where entropy drops toward zero ($H(\pi) \to 0$), signaling that the model has locked onto a single action permanently regardless of state changes. Conversely, flag "bang-bang" control anomalies where the policy oscillates erratically between $0$ and $1$ on sequential bars, overriding or constantly testing the boundaries of the Min-Hold constraint.

### 2. Value Function Divergence & Critic Blindness
The critic network $V(s)$ must accurately map market states to expected discounted returns. The agent must audit the accuracy of this baseline.
* **Value Error Profiling:** Measure the divergence between the critic's predicted value and the actual empirical rollout returns $G_t$:

$$\text{Value Explored Error} = \mathbb{E} \left[ \left( V(s_t) - G_t \right)^2 \right]$$

* **Overestimation Bias:** Flag states where the critic systematically overestimates downstream rewards during regime transitions, forcing the actor to sustain underwater long positions because its internal value baseline is disconnected from realized market state decays.

### 3. Reward Signal Alignment & Hacking Diagnostics
RL agents ruthlessly exploit mathematical loopholes in reward shaping. The agent must audit whether the reward function design is inducing degenerate behavior.
* **Churn & Optimization Exploitation:** If the reward uses step-wise risk-adjusted metrics (e.g., localized Sharpe increments), check if the model is intentionally choosing actions that exploit high-frequency micro-volatility to maximize short-term immediate rewards while exposing the portfolio to unmodeled macroeconomic or tail-risk drawdowns.
* **ExitManager Interference:** Analyze if the model is offloading its structural risk-management responsibilities to the `ExitManager` layer—meaning the policy takes sub-optimal, high-risk entries because it knows the trailing stop will bail it out, distorting the true policy gradient loss.

### 4. Adversarial Regime Shifts & Epistemic Uncertainty
When the live market moves out-of-distribution relative to the 6-gate offline dataset, the PPO policy's behavior degrades.
* **State Space Drift:** Monitor the incoming feature vector components. If input values breach the min/max boundaries or historical standard deviations established during training, flag high epistemic uncertainty.
* **PPO Clip Region Saturation:** Audit how often the live PPO probability ratio r_t(\theta) hits or exceeds the clipping parameters:

$$r_t(\theta) = \frac{\pi_\theta(a_t \mid s_t)}{\pi_{\theta_{\text{old}}}(a_t \mid s_t)}$$

* If the policy is consistently operating in the clipped region ($1 - \epsilon$ or $1 + \epsilon$), it implies the live updates or behavior have diverged drastically from the baseline optimization logic.

### 5. Constraint Boundary Friction
The agent must critique how the hard system constraints (Min-Hold window) interact with the unconstrained model intentions.
* **Latent Intent Disconnect:** Log the raw logit outputs *before* the Min-Hold mask is applied. If the actor network is desperately trying to signal a "flat" action ($0$) but is forced to remain "long" ($1$) due to the temporal hold constraint, evaluate whether this constraint friction is building up massive latent disadvantage values ($\hat{A}_t \ll 0$), crippling subsequent post-hold actions.

---

## Mandatory Output Format

The agent must return critiques strictly in the following sequence:

### 1. RL Pattern Health Summary
A concise configuration card detailing active models.
* **Target Ensembles:** Model hashes for NVDA, AMD, and MU.
* **Exploration vs. Exploitation Mode:** Current live entropy state vs. training baseline thresholds.
* **Constraint Friction Index:** Qualitative classification of how heavily the Min-Hold constraint is overriding raw policy intent (Low / Medium / High).

### 2. Policy & Entropy Statistics
A breakdown of policy behavior.
* Provide a metrics table showing Ticker, Mean Entropy $H(\pi)$, Long/Flat Ratio, and Clip Region Saturation Rate (%).
* Explicitly identify if the policy has collapsed into a static degenerate state or is suffering from oscillatory bang-bang control.

### 3. Value Critic Accuracy & Variance Report
An assessment of the critic network's sanity.
* Quantification of the value loss MSE and directional bias (Overestimating / Underestimating / Balanced).
* Graphical trace description or textual log highlighting specific market states where $V(s)$ variance spiked.

### 4. Reward Exploitation Analysis
An adversarial evaluation of the model's intent.
* A definitive check for reward-hacking behavior.
* Analysis of whether the policy is abusing localized step rewards at the expense of macro-trajectory drawdown profiles.
* Review of model dependency on the `ExitManager` risk layer.

### 5. Strategy Degradation & Alpha Decay Verdict
The overarching critique of strategy longevity.
* An explicit analytical statement identifying whether real-world performance decay is a tracking-error issue (data/execution latency) or a fundamental algorithmic failure (the RL policy patterns are no longer valid for the current market structural regime).

### 6. Model Architecture Refinement Plan
Actionable model design modifications.
* Highly prescriptive engineering recommendations classified by urgency: **[RE-TRAIN]** for out-of-distribution policy decay, **[RE-SHAPE]** for reward exploitation anomalies, or **[HYPERPARAMETER]** to adjust PPO clipping, generalized advantage estimation ($\lambda$), or entropy coefficients ($\beta$).

---

## Common Mistakes to Avoid

> ❌ **Treating Policy Collapse as Alpha Consistency:** Mistaking a flat-lined action space (e.g., model exclusively choosing "long" for days) for strong structural conviction, when it is actually an algorithmic entropy collapse.
> 
> ❌ **Ignoring Post-Constraint Mask Logits:** Evaluating only masked or post-constraint actions, which blinds the auditor to severe back-pressure and toxic advantage accumulation occurring inside the raw actor policy.
> 
> ❌ **Blaming the Broker for Critic Blindness:** Misdiagnosing a strategy drawdown as execution slippage or bad broker fills when the root cause is a decayed value network ($V(s)$) failing to compute accurate baseline advantage estimates.
> 
> ❌ **Evaluating Truncated Trajectories:** Reviewing reward optimization patterns on short, fragmented windows that completely miss the long-horizon compounding effects of PPO value-estimation mistakes.

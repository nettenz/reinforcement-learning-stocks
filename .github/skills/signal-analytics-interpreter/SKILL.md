---
name: signal-analytics-interpreter
description: 'Analyze RL trading signals, behavior, and decision patterns to explain what the model is actually doing and why. Use for src/signal_analytics.py, analytics_dashboard.py, and experiment outputs when diagnosing model behavior, trade quality, and regime response.'
argument-hint: 'What model run, ticker, or signal dataset should be analyzed?'
user-invocable: true
---

# Signal Analytics Interpreter

Quantitative signal and behavior analysis workflow for reinforcement-learning trading systems.

## Objective
Explain what the model is actually doing:

- How it trades (behavior)
- When it trades (timing)
- Why it succeeds or fails (pattern)
- Whether behavior is realistic and deployable

This is NOT about metrics alone — this is about **behavior interpretation**.

---

## Use This Skill When
- You have signal outputs and want to understand behavior
- Results look “good” but you don’t trust them
- Results look “bad” and you want to know why
- You want to diagnose:
  - overtrading
  - hold bias
  - directional bias
  - regime dependence
- You want to validate if signals make economic sense

---

## Default Focus Files
- `src/signal_analytics.py`
- `src/analytics_dashboard.py`
- experiment outputs:
  - signal DataFrames
  - leaderboard rows
  - trade logs
  - equity curves

---

## Core Procedure

### 1. Summarize trading behavior
Extract:

- trade frequency
- hold vs buy vs sell distribution
- average holding time
- turnover rate
- net exposure bias (long / short / neutral)

Classify behavior:

- trend-following
- mean-reversion
- hold-heavy
- churn/overtrading
- inactive

---

### 2. Analyze trade quality
Evaluate:

- win rate
- average trade edge
- distribution of trade returns
- large winners vs frequent small losses
- symmetry (long vs short performance)

Flag:

- high win rate but negative returns
- low win rate but positive returns
- skewed distributions
- inconsistent edge

---

### 3. Analyze timing quality
Check:

- entry timing vs price movement
- exits vs reversals
- reaction to volatility spikes
- reaction to trend changes

Detect:

- late entries
- premature exits
- overreaction
- lagging signals

---

### 4. Analyze regime behavior
Segment behavior by:

- trending vs sideways periods
- high vs low volatility
- drawdown periods

Determine:

- does the model only work in one regime?
- does it fail during volatility spikes?
- does it collapse during reversals?

---

### 5. Detect pathological behavior
Look for:

- always long
- always flat
- always short
- action oscillation (buy/sell flipping)
- no-trade avoidance
- reward exploitation patterns

---

### 6. Cross-check with metrics
Compare behavior against:

- actionable accuracy
- trade win rate
- cumulative return
- alpha vs QQQ

Flag contradictions:

- good accuracy, bad returns
- good returns, unstable behavior
- high win rate, negative edge

---

### 7. Map behavior → cause
Link observed behavior to likely causes:

- reward design
- exploration (entropy)
- feature quality
- news noise
- environment constraints
- execution assumptions

Clearly separate:
- evidence
- hypothesis
- unknowns

---

### 8. Recommend next actions
Propose:

- reward changes (→ reward-architect)
- experiment changes (→ quant-experiment-strategist)
- environment fixes (→ environment-realism-auditor)
- feature/news changes (→ news-ticker-analyst)

---

## Required Output Format

1. **Behavior summary**
2. **Trade quality analysis**
3. **Timing analysis**
4. **Regime behavior**
5. **Pathological patterns (if any)**
6. **Metric contradictions**
7. **Most likely causes**
8. **Recommended next actions**
9. **Leaderboard comparability impact (REQUIRED)**

---

## Leaderboard Comparability Rule (MANDATORY)

Every recommendation must include:

- Impact level: Low / Medium / High
- Reason:
  - behavior interpretation only?
  - reward changes implied?
  - feature changes implied?
  - execution assumptions affected?

---

## Decision Logic

- If high accuracy + negative returns → reward misalignment
- If high turnover → likely action bonus or no turnover penalty
- If hold-heavy → reward discourages trading
- If unstable across regimes → feature or reward fragility
- If signals lag price → insufficient predictive features
- If signals too reactive → overfitting or noise sensitivity

---

## Constraints

- Do not rely only on aggregate metrics
- Do not assume behavior without evidence
- Do not propose large system changes without justification
- Keep recommendations actionable

---

## Quality Checks Before Finalizing

- Behavior claims backed by observable metrics or logs
- Trade quality analysis includes distribution, not just averages
- Regime claims clearly labeled if inferred
- Contradictions explicitly identified
- Next actions routed to correct specialist skill
- Comparability impact included

---

## Example Invocations

- `/signal-analytics-interpreter Analyze NVDA model signals and explain why returns are negative despite decent accuracy`
- `/signal-analytics-interpreter Diagnose overtrading behavior in latest experiment run`
- `/signal-analytics-interpreter Compare behavior between AAPL and NVDA runs`
- `/signal-analytics-interpreter Explain why win rate is high but cumulative return is negative

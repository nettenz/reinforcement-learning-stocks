---
name: signal-analytics-interpreter
description: 'Interpret model behavior, trade behavior, and signal quality to explain what the system is actually doing and why. Use when metrics alone are not enough and you need behavior-level diagnosis before deciding on reward, experiment, or environment changes.'
argument-hint: 'What run, signal dataset, ticker, or trade behavior should be interpreted?'
user-invocable: true
---

# Signal Analytics Interpreter

Explain what the model is actually doing.

## Objective
Interpret behavior rather than just summarize metrics.

This skill is used when the core question is:
- how is the model behaving?
- when is it acting?
- what pattern is it following?
- does that behavior make economic sense?
- do the metrics and the behavior agree?

This skill does not judge final promotion readiness and does not design full experiment batches.  
It explains observed behavior so the next specialist can act on it.

## Primary mindset
Metrics can look acceptable while behavior is still weak, fragile, unrealistic, or non-deployable.

The goal is to move from:
- “the row looks good”
to
- “the system is behaving like this, for these likely reasons”

## Use this skill when
- results look good but you do not trust the behavior
- results look bad and you want to know why
- you suspect overtrading, hold bias, directional bias, or action collapse
- you want to inspect timing quality or regime dependence
- trade quality and aggregate metrics appear contradictory
- you need behavior-level evidence before handing off to reward, experiment, or realism work

## Do not use this skill when
- the main question is whether the result is robust enough to promote
- the main task is to design the next experiment batch
- the primary issue is code-level realism or leakage auditing
- the question is mainly about whether predictive signal exists at all in Stage 1

## Default Focus Files
- `src/signal_analytics.py`
- `src/analytics_dashboard.py`
- signal dataframes
- trade logs
- equity curves
- leaderboard rows
- experiment summaries
- per-ticker or per-run analytics artifacts

## Core Procedure

### 1. Summarize behavior
Extract:
- trade frequency
- hold / buy / sell distribution
- holding time
- turnover
- long / short / neutral bias
- action concentration or collapse

Classify behavior where supported:
- trend-following
- mean-reversion
- hold-heavy
- churn / overtrading
- inactive / flat-biased
- asymmetric long/short behavior

### 2. Analyze trade quality
Evaluate:
- win rate
- average trade edge
- distribution of trade returns
- dependence on a few large winners
- long vs short asymmetry
- whether realized behavior matches the apparent signal

Flag patterns such as:
- high win rate with weak returns
- low win rate with positive returns
- frequent small losses with occasional outsized gains
- good directional calls with poor execution timing

### 3. Analyze timing quality
Check:
- entry timing relative to price movement
- exit timing relative to reversals
- reaction to volatility spikes
- reaction to trend transitions

Detect:
- late entries
- premature exits
- lagging behavior
- overreaction
- unstable re-entry patterns

### 4. Analyze regime behavior
Segment where possible by:
- trending vs sideways
- high vs low volatility
- drawdown periods
- reversal-heavy periods

Determine whether behavior:
- only works in one regime
- degrades during reversals
- collapses under volatility
- becomes too passive or too reactive in specific conditions

### 5. Detect pathological patterns
Look for:
- always long
- always short
- always flat
- buy/sell oscillation
- no-trade avoidance
- churn without edge
- reward-exploitation-like patterns
- behavior that looks statistically active but economically weak

### 6. Cross-check behavior against metrics
Compare behavior with:
- actionable accuracy
- trade win rate
- cumulative return
- alpha vs benchmark context
- drawdown
- turnover

Explicitly flag contradictions:
- good accuracy, weak returns
- good returns, fragile or implausible behavior
- high win rate, poor edge
- low turnover but weak participation
- strong behavior on one ticker or regime only

### 7. Map behavior to likely causes
Link observed behavior to likely causes:

- reward design
- entropy / exploration settings
- feature quality
- noisy news inputs
- environment constraints
- execution assumptions

Separate clearly:
- evidence-backed observations
- plausible hypotheses
- unknowns requiring follow-up

### 8. Recommend the next specialist action
Route to the correct next skill:

- `reward-architect` when incentives appear misaligned
- `quant-experiment-strategist` when the next step is a controlled follow-up batch
- `environment-realism-auditor` when behavior depends on unrealistic execution assumptions
- `news-ticker-analyst` or signal-focused work when features appear noisy or unhelpful
- `strategy-refinement-analyst` when the broader question becomes batch-level judgment

## Decision Logic

- If accuracy is decent but returns are weak: suspect reward or execution misalignment.
- If turnover is high without clear edge: suspect churn incentives or noisy policy behavior.
- If the policy is hold-heavy: suspect over-penalized trading or weak signal confidence.
- If behavior breaks across regimes: suspect feature fragility or unstable incentives.
- If timing lags price action: suspect weak predictive quality or delayed response structure.
- If signals are hyper-reactive: suspect noise sensitivity or overfit behavior.
- If observed behavior looks unrealistic under realistic fills: hand off to environment realism audit.

## Required Output Format

Always return sections in this exact order:

1. **Behavior summary**
2. **Trade quality analysis**
3. **Timing analysis**
4. **Regime behavior**
5. **Pathological patterns (if any)**
6. **Metric contradictions**
7. **Most likely causes**
8. **Recommended next actions**
9. **Next proposed experiments or runs (if requested or justified)**
10. **Leaderboard comparability impact (REQUIRED)**
11. **Pipeline Decision**

## Output Requirements

### Behavior summary
Summarize what the model is doing in plain behavioral terms.

### Trade quality analysis
Focus on edge quality, distribution shape, and asymmetry.

### Timing analysis
Explain whether the model is early, late, too reactive, or too passive.

### Regime behavior
Only claim regime dependence when evidence supports it.
If evidence is incomplete, say so clearly.

### Pathological patterns
Only include patterns supported by observable behavior.

### Metric contradictions
Make contradictions explicit rather than implied.

### Most likely causes
Separate:
- evidence
- hypothesis
- unknown

### Recommended next actions
Route to the correct skill and explain why.

### Next proposed experiments or runs
Only include when justified.
For each proposed run include:
- environment activation command
- runner command
- full relative script path when not in repo root
- key args
- expected output artifact path(s)

### Leaderboard comparability impact (REQUIRED)
Include:
- impact level: Low / Medium / High
- whether this is behavior interpretation only or implies semantic changes
- whether reward, feature, or execution assumptions would change if recommendations are followed
- whether conclusions are exploratory or confirmatory

## Constraints
- Do not rely only on aggregate metrics
- Do not assume behavior without evidence
- Do not act as final promotion judge
- Do not propose large system rewrites without justification
- Keep recommendations tied to observed behavior
- Do not omit comparability impact

## Quality Checks Before Finalizing
- behavior claims are tied to observable logs or analytics
- trade quality includes distribution, not just averages
- timing claims are evidence-backed or clearly labeled as hypothesis
- contradictions are explicit
- next actions are routed to the correct specialist
- comparability impact is included
- output order is followed exactly
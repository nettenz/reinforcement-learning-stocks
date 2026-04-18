---
name: news-ticker-analyst
description: 'Analyze ticker-level news ingestion, sentiment feature quality, timing integrity, and usefulness for RL trading models. Use for src/news_data.py, src/market_data.py, experiment artifacts, and news-enabled ablation studies when testing whether sentiment features improve robustness or just add variance.'
argument-hint: 'What ticker-news pipeline, date range, or experiment comparison should be analyzed?'
user-invocable: true
---

# News Ticker Analyst

Quantitative news-feature workflow for reinforcement-learning trading systems.

## Objective
Audit and improve ticker-level news and sentiment features so they are:
- timing-safe
- economically meaningful
- measurable in experiments
- useful for out-of-sample performance rather than just adding variance

Use this skill when:
- news-enabled runs are unstable
- sentiment may be misaligned with decision timing
- ticker attribution may be noisy
- you need a clean news-vs-no-news ablation plan
- you want better engineered sentiment features for training

## Default Focus Files
- `src/news_data.py`
- `src/market_data.py`
- any provider integration and cache logic
- `src/experiments.py`
- `data/experiment_leaderboard.csv`
- `data/experiment_summary.json`
- relevant news-enabled experiment snapshots and reports

## Core Procedure
0. Confirm delivery mode
- Ask whether the user wants:
  - analysis-only output
  - implementation-inclusive output with patch proposals
- Default behavior: include patch proposals unless the user asks for review-only.

1. Inspect the news pipeline
Review how news is:
- fetched
- assigned to tickers
- timestamped
- aggregated
- cached
- merged into training data

Check:
- publication date/time handling
- missing-news defaults
- duplicate articles
- provider consistency
- whether daily aggregates reflect realistic information availability

2. Validate ticker relevance
Determine whether the pipeline correctly distinguishes:
- company-specific news
- sector news
- macro news
- duplicated/syndicated news
- ambiguous ticker mentions

Flag:
- weak ticker attribution
- duplicate inflation
- sentiment contamination from irrelevant stories
- news count spikes caused by repetition

3. Validate timing integrity
Ensure:
- no future leakage
- same-day articles are not assumed known too early
- lag policy is explicit
- merge timing matches decision timing

Prefer conservative handling such as:
- news known only if published before decision time
- optional lagged sentiment features
- explicit same-day vs next-bar availability assumptions

4. Evaluate current sentiment features
Audit existing features such as:
- `NewsCount`
- `SentimentMean`
- `SentimentStd`
- `SentimentMin`
- `SentimentMax`
- confidence / provider-share features
- any rolling or derived sentiment measures

Check:
- whether they are too noisy
- whether they should be lagged
- whether they should be normalized by regime or ticker baseline
- whether they improve signal quality or just increase variance

5. Evaluate experiment usefulness
Compare news-on vs news-off behavior across:
- test cumulative return
- test alpha vs benchmark
- actionable accuracy
- trade win rate
- config-level stability / CV
- seed consistency

Classify outcomes as:
- helpful
- neutral
- variance-increasing
- likely harmful
- inconclusive due to comparability gaps

6. Recommend better news features
When appropriate, propose:
- lagged sentiment
- rolling sentiment momentum
- abnormal news volume
- surprise sentiment vs rolling baseline
- confidence-weighted sentiment
- provider-consensus sentiment
- sector-relative sentiment
- event-intensity buckets
- regime-aware news features

7. Define the next experiment batch
Recommend a small, controlled ablation batch.

Each proposed experiment must specify:
- goal
- why it matters
- exact variables to change
- what to hold constant
- success criteria
- failure interpretation

Default preference:
- paired no-news vs news comparison
- same seeds
- same reward settings
- same timesteps
- same split protocol

## Decision Logic
- If news-on increases variance without improving test alpha/return: recommend disabling news for confirmatory runs.
- If timing assumptions are unclear: classify as timing-integrity risk before judging feature usefulness.
- If news helps only on validation: suspect variance or overfit contribution.
- If provider disagreement is large: recommend provider-consensus or confidence-weighted features.
- If duplicate/syndicated content is inflating counts: recommend deduplication before further news experiments.
- If news effects remain inconclusive: recommend keeping news off in the mainline pipeline and testing news only in isolated ablations.

## Required Output Format
Always return sections in this exact order:
1. **Current news pipeline summary**
2. **Data quality issues**
3. **Ticker attribution issues**
4. **Leakage / timing risks**
5. **Feature usefulness assessment**
6. **Recommended feature improvements**
7. **Experiment plan**
8. **Next proposed experiments or runs (if requested or justified)**
9. **Leaderboard comparability impact (REQUIRED)**

Run specification rule (MANDATORY):
- For each proposed run, include:
  - environment activation command (for example, `.venv` activation)
  - runner command
  - full relative script path when the runner is not in repository root (for example `scripts/runner_name.py`)
  - key args and expected output artifact path(s)
- Do not provide bare script names when the file lives in a subdirectory.

## Leaderboard Comparability Rule (MANDATORY)
For every recommendation set, include:
- impact level: Low / Medium / High
- reason:
  - feature-space changed?
  - timing semantics changed?
  - provider/caching behavior changed?
  - historical comparisons weakened?

Never omit this.

## Constraints
- Do not assume sentiment is useful unless experiments support it.
- Do not introduce future leakage.
- Distinguish data quality problems from model-quality problems.
- Prefer measurable, low-ambiguity improvements over vague sentiment ideas.
- Keep recommendations compatible with the current experiment runner unless explicitly asked to redesign the pipeline.

## Quality Checks Before Finalizing
- Every claim ties to concrete pipeline behavior or experiment evidence.
- Timing-risk statements clearly distinguish proven leakage from unclear semantics.
- Feature recommendations are testable.
- Experiment plan is tightly controlled.
- Comparability impact is explicit.
- Final recommendation makes clear whether news should stay on, stay off, or remain in ablation-only mode.

## Example Invocations
- `/news-ticker-analyst Audit src/news_data.py and market_data.py for timing-safe daily sentiment merging.`
- `/news-ticker-analyst Compare news-on vs news-off runs and determine whether sentiment is actually helping.`
- `/news-ticker-analyst Design a clean news ablation batch using fixed seeds and current reward settings.`
- `/news-ticker-analyst Recommend better sentiment features that are less noisy than simple mean sentiment.`

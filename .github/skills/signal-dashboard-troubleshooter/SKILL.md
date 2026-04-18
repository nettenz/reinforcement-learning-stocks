---
name: signal-dashboard-troubleshooter
description: 'Troubleshoot and adapt the signal analytics dashboard when new experiment data, schema changes, ticker fields, metrics, or leaderboard columns are introduced. Use for src/analytics_dashboard.py, src/signal_analytics.py, src/experiments.py, Stage 1 pivot artifacts, and experiment outputs when dashboard views break, drift, or become inconsistent with current data.'
argument-hint: 'What new data, schema change, or dashboard issue should be investigated?'
user-invocable: true
---

# Signal Dashboard Troubleshooter

Schema-evolution and dashboard-integration workflow for reinforcement-learning trading analytics dashboards.

## Objective
Keep the signal analytics dashboard correct, stable, and useful as experiment outputs evolve.

Use this skill to diagnose and fix dashboard issues caused by:
- new columns added to experiment outputs
- new ticker fields
- changed leaderboard schemas
- changed reward metrics
- new feature flags
- changed model output formats
- new signal/trade analytics fields
- Stage 1 signal-first pivot outputs and gate reports

This skill is focused on **dashboard correctness and compatibility**, not strategy interpretation.

## Use This Skill When
- `src/analytics_dashboard.py` breaks after adding new data fields
- charts disappear or render incorrect values
- filters/selectors do not recognize new schema fields
- generated commands omit new CLI parameters
- leaderboard rows no longer align with dashboard expectations
- ticker-aware or feature-aware updates cause silent mismatches
- the dashboard still runs but shows stale or misleading logic

## Default Focus Files
- `src/analytics_dashboard.py`
- `src/experiments.py`
- `src/signal_analytics.py`
- `src/market_data.py`
- `scripts/stage1_gate.py`
- `scripts/evaluate_stage1_trading.py`
- `run_stage1_step4_mixed_threshold_gate.ps1`
- current leaderboard and summary artifacts:
  - `data/experiment_leaderboard.csv`
  - `data/experiment_reward_leaderboard.csv`
  - `data/experiment_summary.json`
  - `data/experiment_snapshots/`
- Stage 1 pivot artifacts when relevant:
  - `results/stage1/`
  - `results/stage1_confirmation_3seed/`
  - `logs/stage1_gate_report*.json`
  - `logs/stage1_trading_eval*.json`

## Core Procedure

0. Confirm scope
- Ask whether the issue is:
  - runtime error
  - schema drift
  - silent wrong output
  - missing dashboard controls
  - incorrect chart/metric behavior
- Ask whether output should be:
  - diagnosis only
  - diagnosis + patch proposal

0.5. Identify artifact family
- Determine whether the issue is in the RL dashboard path, the Stage 1 pivot path, or both.
- Do not assume Stage 1 outputs should appear in existing RL dashboard views unless the code explicitly routes them there.

Default: include patch proposal unless review-only is requested.

1. Detect schema changes
Compare dashboard assumptions against current artifacts.

Check for newly introduced or changed fields such as:
- ticker
- reward fields
- trade support fields
- stationary feature flags
- benchmark metrics
- promotion fields
- signal coverage fields

Identify:
- fields expected by dashboard but missing in data
- fields present in data but ignored by dashboard
- renamed fields
- type mismatches
- optional fields that need safe fallbacks
- Stage 1-specific fields that need separate treatment from RL leaderboard fields, such as baseline gate verdicts and trading gate summaries.

2. Trace dashboard data flow
Map:
- file load
- parsing
- filtering
- derived metrics
- chart input
- command generation
- page rendering

Identify exactly where new data stops being handled correctly.

3. Validate dashboard assumptions
Inspect whether dashboard code assumes:
- one ticker only
- fixed leaderboard schema
- fixed reward metric set
- fixed experiment config fields
- fixed model path conventions
- fixed signal analytics output shape
- fixed artifact family (RL leaderboard only) when Stage 1 pivot artifacts may coexist in the workspace

Flag hardcoded assumptions that will break when the experiment pipeline evolves.

4. Troubleshoot render logic
Check:
- sidebar selectors
- filtering by ticker / reward mode / feature mode
- chart grouping and aggregation
- command generation helpers
- table columns
- summary cards
- fallback logic for missing fields

Identify:
- stale headers
- broken grouping
- incorrect defaults
- unsafe direct column access
- silently dropped new fields

5. Recommend compatibility fixes
Prefer minimal, safe changes such as:
- schema-detection helpers
- optional-column guards
- explicit fallback defaults
- centralized field maps
- version-aware loaders
- additive UI controls
- safer command-generation functions
- separate loaders or view tabs for Stage 1 gate/trading outputs when they should not be merged into RL leaderboard summaries

6. Define regression checks
For every fix, propose validation steps such as:
- dashboard load with old leaderboard
- dashboard load with new leaderboard
- ticker-aware filtering
- command generation includes new CLI args
- charts render with and without optional columns
- no silent cross-schema mixing

## Decision Logic
- If dashboard crashes on missing column: add optional-column handling or schema detection.
- If new data exists but is not visible: extend filter/render pipeline without changing historical behavior.
- If a new field affects grouping semantics: update grouping logic and mark comparability implications.
- If new CLI arguments are introduced in `src/experiments.py`: ensure dashboard command builders include them.
- If ticker-awareness was added: ensure every dashboard page and helper respects ticker filtering.
- If old artifacts and new artifacts coexist: prefer backward-compatible parsing over forced migration.
- If Stage 1 pivot artifacts coexist with RL outputs: keep parsing backward-compatible, but avoid silently merging their semantics into one chart/table.

## Required Output Format
Always return sections in this exact order:
1. **Issue summary**
2. **Schema or data-flow mismatch**
3. **Broken assumptions found**
4. **Exact file/function locations**
5. **Recommended patch plan**
6. **Regression checks**
7. **Leaderboard comparability impact (REQUIRED)**

## Stage 1 Pivot Rule
When Stage 1 pivot artifacts are involved, explicitly state whether the dashboard should:
- ignore them
- display them in a separate view
- or merge them with RL leaderboard artifacts

Default: separate view or explicit exclusion, never silent merge.

## Leaderboard Comparability Rule (MANDATORY)
For every recommendation set, include:
- impact level: Low / Medium / High
- reason:
  - dashboard-only change?
  - grouping semantics changed?
  - filter semantics changed?
  - old vs new artifacts may display differently?
- if Stage 1 pivot data is introduced, say whether RL and Stage 1 views remain comparable or must remain separate

Never omit this.

## Constraints
- Do not silently change dashboard semantics.
- Prefer backward-compatible parsing where possible.
- Do not assume all historical artifacts share the latest schema.
- Keep fixes incremental and testable.
- Be explicit when UI behavior changes interpretation of historical results.

## Quality Checks Before Finalizing
- Every issue maps to a concrete code location.
- Every recommended fix identifies exact functions/helpers to change.
- Backward compatibility is considered.
- Regression checks cover both old and new artifacts.
- Comparability impact is explicit.
- Diagnosis distinguishes runtime breakage from semantic drift.

## Example Invocations
- `/signal-dashboard-troubleshooter Fix analytics_dashboard.py after adding ticker to experiment rows.`
- `/signal-dashboard-troubleshooter Update dashboard filters and charts for new reward metrics and support columns.`
- `/signal-dashboard-troubleshooter Diagnose why new leaderboard columns are ignored in the dashboard.`
- `/signal-dashboard-troubleshooter Make command generation include newly added CLI parameters without breaking old behavior.`
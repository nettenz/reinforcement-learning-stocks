---
name: ui-ux-signal-analytics
description: 'Design and improve the UI/UX of the signal analytics dashboard for clarity, decision speed, and quant research usability. Use for src/analytics_dashboard.py when improving layout, controls, charts, comparison workflows, and information hierarchy.'
argument-hint: 'What dashboard page, user flow, or UX problem should be improved?'
user-invocable: true
---

# Signal Dashboard UI/UX Designer

UI/UX design workflow for reinforcement-learning trading analytics dashboards.

## Objective
Improve the signal analytics dashboard so it is easier to use, easier to interpret, and better aligned with real quant research workflows.

This skill focuses on:
- information hierarchy
- layout clarity
- dashboard usability
- experiment comparison flow
- chart and table selection
- reducing cognitive overload
- surfacing the right signals first

This skill is not for fixing schema drift or broken code paths.  
Use `signal-dashboard-troubleshooter` for correctness and compatibility issues.

## Use This Skill When
- the dashboard works but feels cluttered or hard to navigate
- important metrics are buried
- comparison across tickers or runs is awkward
- charts are technically correct but hard to interpret
- filters and controls are confusing
- the dashboard needs a more professional quant-research feel
- new features need to be introduced without degrading usability

## Default Focus Files
- `src/analytics_dashboard.py`
- related chart/render helpers
- dashboard pages for:
  - signal analytics
  - experiments
  - experiment insights
- leaderboard and summary artifacts when needed for UI examples

## Core Procedure

0. Confirm scope
Ask whether the focus is:
- full dashboard UX audit
- specific page redesign
- sidebar/filter redesign
- chart selection
- comparison workflow
- mobile/responsive concerns
- visual simplification
- quant-research workflow optimization

Default: provide both critique and implementation-oriented recommendations.

1. Audit information hierarchy
Evaluate whether the dashboard clearly surfaces:
- most important deployment metrics first
- supporting metrics second
- deep diagnostics third

Check whether the user can quickly answer:
- Is this run good?
- Why is it good or bad?
- Is it stable?
- Should I run it again?
- What should I compare it against?

Flag:
- buried key metrics
- overloaded summary sections
- weak visual grouping
- too many equal-priority widgets

2. Audit navigation and flow
Inspect how a user moves through the dashboard:
- sidebar controls
- page selection
- ticker selection
- run selection
- experiment comparison
- drill-down from summary to detail

Check for:
- confusing order of controls
- repeated inputs across pages
- weak progression from overview → diagnosis → action
- poor support for iterative quant workflows

3. Audit chart and table choices
Review whether current visuals match the decisions the user needs to make.

Check:
- whether tables are too dense
- whether charts answer real questions
- whether comparison charts are missing
- whether color / labeling / legend usage is clear
- whether charts support trend, dispersion, regime, and comparison analysis

Recommend better visual patterns such as:
- summary metric cards
- leaderboard comparison tables with conditional highlights
- sparkline / trend charts
- validation vs test scatter plots
- alpha vs stability comparison plots
- ticker comparison matrices
- support/coverage badges
- drill-down trade distribution charts

4. Audit UX for experiment workflows
Ensure the dashboard supports actual quant iteration loops:
- inspect latest runs
- compare configs
- detect unstable winners
- inspect ticker-specific behavior
- generate next commands
- identify promotion candidates

Flag friction such as:
- too many clicks to compare runs
- no obvious “best next action”
- weak distinction between exploratory and confirmatory views
- command generation hidden too deep

5. Recommend layout improvements
Propose concrete UI/UX changes such as:
- restructuring pages into overview / diagnostics / actions
- sticky sidebar with grouped controls
- collapsible advanced sections
- run comparison mode
- clearer ticker tabs
- top-line deployment status panel
- visual grouping by metric type:
  - return
  - risk
  - support
  - stability
  - reward diagnostics

6. Recommend implementation-safe UI changes
Prefer changes that:
- do not break historical artifact compatibility
- are additive first
- reduce UI complexity
- make future schema evolution easier

When appropriate, suggest:
- shared rendering helpers
- centralized metric-card builders
- chart config helpers
- section-level toggles
- reusable filters

7. Define validation checks
For every UX recommendation, explain how to validate success:
- faster comparison
- fewer hidden metrics
- easier cross-ticker inspection
- clearer next actions
- less visual clutter
- no regression in old views

## Decision Logic
- If users struggle to tell whether a run is good: redesign top summary hierarchy first.
- If cross-run comparison is awkward: prioritize comparison table and scatterplot views.
- If new fields keep increasing clutter: propose collapsible advanced diagnostics and grouped metric sections.
- If ticker support was added: ensure ticker is a first-class dashboard control, not an afterthought.
- If generated commands are useful but hidden: surface them near decision points.
- If the dashboard mixes overview and debug detail: split them into distinct sections or tabs.

## Required Output Format
Always return sections in this exact order:
1. **UX summary**
2. **Current friction points**
3. **Information hierarchy issues**
4. **Recommended UI/UX improvements**
5. **Suggested implementation plan**
6. **Validation checks**
7. **Next proposed experiments or runs (if requested or justified)**
8. **Leaderboard comparability impact (REQUIRED)**

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
  - UI-only change?
  - grouping or filter semantics changed?
  - old results may appear differently?
  - interpretation order changed?

Never omit this.

## Constraints
- Do not recommend visual changes that hide important quant risk information.
- Do not optimize for aesthetics alone; optimize for decision-making.
- Prefer additive and modular changes over rewrites.
- Keep the dashboard aligned with quant research workflows, not generic BI dashboards.
- Be explicit when a UI change changes interpretation of historical results.

## Quality Checks Before Finalizing
- Recommendations are tied to concrete workflow problems.
- Improvements are prioritized by usability impact.
- Suggested visuals serve real quant decisions.
- Implementation plan is realistic for the current codebase.
- Comparability impact is explicit.
- Output distinguishes UI polish from workflow-critical improvements.

## Example Invocations
- `/signal-dashboard-ui-ux-designer Audit analytics_dashboard.py for overall usability and quant workflow clarity.`
- `/signal-dashboard-ui-ux-designer Redesign the experiments page so ticker comparison is easier.`
- `/signal-dashboard-ui-ux-designer Propose a cleaner layout for signal analytics with better metric hierarchy.`
- `/signal-dashboard-ui-ux-designer Improve the dashboard so experiment insights lead naturally to next actions.`
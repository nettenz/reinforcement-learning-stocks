# Pivot Handoff: Strategy Options and Execution Checklist

Date: 2026-05-02

Purpose: provide a concise, decision-ready handoff describing the valid pivot options, falsifiable gates, required artifacts, and runbook steps so the next team can execute or close the project cleanly.

1. Executive summary
- Current authoritative state: NVDA and AMD are promoted and staged; AAPL/GOOGL were dropped after leakage/regime failures; ALAB flagged for re-screening mid-2027. See PROJECT_STATE.md for details.
- Goal of this doc: present the limited set of defensible pivots, the evidence gates that would justify each, and the exact artifacts/run commands to run a pivot experiment.

2. When to pivot (decision contract)
- Only run a pivot if you can specify an a priori falsifier (exact metric, window, and threshold) and the required data/artifacts are available.
- Never run broad reward-only sweeps without a Stage 3 supervised hypothesis passing G1–G5.

3. Recommended pivots (short descriptions + falsifiers)
- Pivot 1 — Intraday microstructure (5-minute NVDA)
  - Why: highest evidence-to-cost; data exists; mechanistic prior for sub-daily structure.
  - Falsifier: directional accuracy ≥ 52% on 30–60min targets across 3 walk-forward windows after 10bp costs.
  - Minimal run: `scripts/run_intraday_pivot.sh --ticker NVDA --tf 5m --run-label pivot_intraday_5m`

- Pivot 2 — Universe expansion (cross-asset / diverse tickers)
  - Why: reduce dominant-ticker risk; test whether signal generalizes beyond NVDA/AMD.
  - Falsifier: rank IC > 0.05 with dominant-ticker share < 30% across validation windows.
  - Minimal run: targeted supervised Stage 3 tests on 10 tickers (see artifacts list).

- Pivot 3 — Target reformulation (regime/vol/drawdown-aware objective)
  - Why: current episodic reward may be misaligned; alternative target may be learnable.
  - Falsifier: vol-prediction R² > 0.10 AND risk-managed strategy beats buy-hold in recent window.
  - Minimal run: supervised/regime classifier + conditional ensemble backtest.

- Pivot 4 — Regime-conditional ensemble
  - Why: holds promise if signals are regime-specific; ensemble switches per detected regime.
  - Falsifier: regime-conditional ensemble net Sharpe ≥ 30% improvement vs unconditional baseline across two windows.

- Pivot 5 — Reward architecture rebuild (sparse episodic redesign)
  - Why: last-resort if Option 1 shows some activity but poor Sharpe; larger engineering effort.
  - Falsifier: test_actionable_accuracy ≥ 0.53 AND clean CV < 1.0 across promoted seeds.

- Pivot 6 — Honest project exit / research template
  - Why: if all pivots fail or cost outweighs likely return; preserve infra as a research template.
  - Falsifier: no pivot produces its falsifier result within the planned budget.

4. Required artifacts (what to include in the handoff)
- Data: `data/exp_1_nvda_10seed_foundation_*`, `data/exp_3_amd_10seed_foundation_*`, relevant parquet files used for training.
- Model artifacts: `staging/models/` (ensemble zips) and `staging/models/ensemble_config.json`.
- Gate & evaluation: `scripts/evaluate_sweep.py`, `src/experiments.py`, gate definitions in `docs/implementation_plan.md` and `PROJECT_STATE.md`.
- Audit docs: `docs/AAPL_LEAKAGE_AUDIT.md`, `docs/archive/PROJECT_PIVOT_ASSESSMENT_2026_04_29.md`.

5. Runbook templates (per-pivot quick steps)
- Intraday (Pivot 1)
  1. Confirm intraday candles exist in `data/` (5m parquet). 2. Run the intraday data prep: `python src/data_prep.py --tf 5m --ticker NVDA`. 3. Execute the sweep: `python src/experiments.py --ticker NVDA --tf 5m --run-label pivot_intraday_5m --append`. 4. Evaluate with `python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label pivot_intraday_5m`.

- Universe expansion (Pivot 2)
  1. Select candidate tickers (list in `docs/archive/PATH_B_ENSEMBLE_PIPELINE_2026_04_29.md`). 2. Run supervised Stage 3 baselines per ticker. 3. If baselines pass, run targeted RL sweeps with `--run-label pivot_universe_X`.

- Regime / Reward pivots (Pivots 3–5)
  - Follow `docs/implementation_plan.md` Phase B–D. Use the same base config as NVDA v2 champion unless testing a deliberate deviation. Always set `--append` and a clear `--run-label`.

6. Handoff checklist (what this deliverable must include)
- Evidence pack: leaderboards, gate reports (JSON), top model snapshots, `PROJECT_STATE.md` snapshot.
- Run commands and `--run-label` used, plus exact `sweep_label` filters.
- A short decision note: chosen pivot, budget (hours/days), owner, and falsifier metric/threshold.

7. Owners, timeline, and budget guidance
- Owner: name the engineer/researcher responsible (example placeholder: Research Lead).
- Timeline guidance: Intraday (1 week), Universe expansion (2–3 weeks), Regime/reward pivots (2–8 weeks depending on scope).

8. Post-pivot integration steps
- If a pivot produces promotable configs, follow the Promotion Pipeline: `scripts/evaluate_sweep.py` → `scripts/generate_ensemble_config.py` (verify manually) → copy top zips to `staging/models/` and update `staging/models/ensemble_config.json` and `PROJECT_STATE.md`.

9. Contact & review
- Add reviewers and include a final sign-off in `sessions/` or `docs/` once the chosen pivot's falsifier has been evaluated.

-- end

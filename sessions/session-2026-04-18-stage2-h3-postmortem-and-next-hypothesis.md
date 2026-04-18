# Session Summary: Stage 2 H3 Post-Mortem and Next Hypothesis

Date: 2026-04-18  
Project: reinforcement-learning-stocks  
Scope: Final diagnostic summary after H3 completion

## 1) New Findings (Evidence-Backed)

Primary artifact reviewed: logs/stage2_h3_results_ledger.json

- H3 completed successfully but failed gate contract: final_decision = EXIT_STAGE_2.
- All variants were killed:
  - linear_rank: mean_net_benchmark_gap = -0.2921, recent_gap = -1.2852, rank_ic = +0.0253
  - tree_rank: mean_net_benchmark_gap = -0.3082, recent_gap = -0.6075, rank_ic = -0.0010
  - momentum_rank: mean_net_benchmark_gap = -0.0530, recent_gap = -0.8572, rank_ic = -0.0058
- Concentration risk was severe:
  - linear_rank largest_ticker_contribution_share = 0.8540
  - tree_rank largest_ticker_contribution_share = 0.7342
- Recent-window failure occurred across all variants.
- Ranking quality was near-random on average (low/near-zero rank IC).

Conclusion from findings: observed edge is not broad, not stable, and not promotion-ready.

## 2) Regime/Concentration Post-Mortem

Evidence-backed observations:

- The only positive-looking window behavior did not generalize to recent windows.
- Contribution concentration indicates single-name dependence rather than durable cross-sectional signal.
- Benchmark superiority fails under the same contract used for prior Stage 2 checks.

Plausible hypotheses:

- H3 signal captured transient single-name momentum/regime effects.
- Relative-ranking signal quality is too weak for this universe/feature setup.

Unknowns:

- Whether any residual edge remains after explicitly limiting concentration.

## 3) Proposed New Hypothesis (Exploratory Diagnostic Only)

Hypothesis ID: H4 (diagnostic)

Title: Concentration-Capped Residual Ranking

Goal:

- Test whether any H3 edge survives after removing single-ticker dependence.

Why it matters:

- Distinguishes true cross-sectional signal from concentration artifact.

Exact variables to change:

- Portfolio construction only:
  - Keep universe fixed: AAPL, AMD, NVDA, QQQ, SPY.
  - Keep rebalance frequency fixed: monthly.
  - Keep model scoring logic fixed per variant.
  - Add concentration controls:
    - max position weight per ticker (for long-only top-k) capped at 0.40
    - concentration-kill monitor at contribution share > 0.60

What to hold constant:

- Data source and feature set.
- Rolling-window scheme.
- Cost assumptions.
- Benchmark set and gate contract.

Success criteria:

- At least 2/3 windows beat both equal-weight and buy-hold.
- Recent window net benchmark gap >= 0.
- Largest ticker contribution share <= 0.60.
- Mean rank metric materially above near-random threshold.

Failure interpretation:

- If edge disappears under concentration cap, prior H3 gains were concentration artifacts.
- If recent window remains negative, no durable deployable edge is present.

## 4) Research Discipline Notes

- This H4 is exploratory, not confirmatory.
- Do not treat any single positive window as promotion evidence.
- If H4 fails, close this branch and do not continue tuning this hypothesis family.

## 5) Priority Recommendation

1. Treat current Stage 2 status as killed (no promotion).
2. Run H4 only if one final diagnostic is explicitly desired.
3. If H4 fails, archive findings and pivot to a different hypothesis family.

## 6) Leaderboard Comparability Impact

- Medium.
- H4 changes portfolio construction constraints (concentration caps), so direct score magnitude comparisons against prior H3 are limited.
- H4 remains comparable for go/no-go diagnostics on robustness and concentration risk.

## 7) Promotion Readiness

- Not ready.
- Current evidence does not support progression; H4 is a final falsification check only.

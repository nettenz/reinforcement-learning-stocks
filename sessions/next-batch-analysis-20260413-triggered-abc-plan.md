# Intraday 5m Triggered Strategy Plan (A/B/C)

Date: 2026-04-13
Scope: NVDA intraday 5m, triggered realism family
Sources: data/experiment_summary_intraday_5m_triggered.json, data/experiment_leaderboard_intraday_5m_triggered.csv, baseline intraday 5m counterparts

## 1. Research summary

Triggered intraday 5m improved config-level robustness metrics but degraded out-of-sample returns versus baseline.

- Triggered config statistics: test return mean approx -0.112, std approx 0.096, CV approx 0.862.
- Baseline config statistics: test return mean approx -0.069, std approx 0.146, CV approx 2.12.
- Triggered removed the most obvious leaderboard artifact behavior, but multiple seeds still collapse to no-action/no-trade states.

## 2. What improved

- Lower config-level dispersion and lower fragility risk at the family level.
- Better realism discipline under next-bar execution and explicit spread/slippage.
- Reduced dependence on near-zero-trade leaderboard winners.

## 3. What degraded or remains weak

- Mean test return and test alpha remain negative.
- Several top rows show very high trade rates (potential churn).
- Several seeds collapse with actionable support = 0.

## 4. Most likely explanations

Evidence-backed:

- Realism/trigger changes reduced ranking artifacts but exposed weak net edge.

Plausible hypotheses:

- Current threshold/horizon pair is miscalibrated for 5m noise.
- Turnover/drawdown penalties are not balancing churn vs opportunity.

Unknowns:

- Whether failures are mostly trigger calibration, reward scaling, or exploration-budget effects.

## 5. Confidence level for current conclusions

Medium confidence.

- High confidence: robustness proxy improved, returns worsened.
- Medium confidence: mechanism split among trigger/reward/exploration components.

## 6. Recommended next experiment batch

A) Trigger calibration under fixed realism

- Sweep threshold in {0.001, 0.0015, 0.002} and horizon in {3, 5}.
- Hold execution realism and reward settings fixed to triggered family defaults.

B) Turnover/drawdown/trade-penalty rebalance

- Sweep turnover penalty in {0.10, 0.15, 0.20}, drawdown penalty in {0.12, 0.16}, trade penalty in {0.08, 0.10}.
- Hold trigger pair fixed to best pair from A.

C) Confirmatory stability check

- Compare timesteps {20000, 40000} x ent_coef {0.07, 0.05}.
- Hold all other settings fixed to best config from A/B.

## 7. Priority order

1) A (highest information gain, lowest comparability disruption)
2) B (targets churn and downside under fixed realism)
3) C (confirmatory only after best candidate is identified)

## 8. Success/failure interpretation plan

- A success: trade rate moves into practical band with fewer collapse seeds and improved mean test return.
- B success: trade rate decreases without actionable collapse, with improved alpha/returns.
- C success: higher timesteps or lower entropy improves mean test return without increasing CV or collapse frequency.

## 9. Leaderboard comparability impact (required)

- Baseline vs triggered is medium comparability due to changed execution and reward-cost semantics.
- Keep an internal triggered control arm in every batch for within-family comparability.
- Interpret cross-family conclusions with explicit caveats.

## 10. Promotion readiness assessment

Not promotion-ready.

- Out-of-sample return and alpha are still weak under realistic execution.
- Promote only if A/B/C produce a stable, multi-seed, non-collapse candidate with improved mean test return and acceptable CV.

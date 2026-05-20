# Refinement TODO — Elliott-Style Exit Discipline

**Goal:** Improve the Binary PPO trading stack so it behaves more like a disciplined wave-aware system: enter with conviction, exit with structure, and preserve positive expectancy after costs.

**Current diagnosis:**
- The current policy is too buy-skewed and does not express enough exit intent.
- `output.png` suggests strong long bias, weak entropy, and limited wave-like alternation.
- The fix is not just more reward tuning; it needs wave-aware state features, cleaner exit logic, and better telemetry.
- Target is not guaranteed positive PnL; target is a robust positive expectancy profile with lower drawdown and fewer dead-long regimes.

## Phase 1 — Measure the Failure Mode
- [ ] Add telemetry for raw actor logits before masking.
- [ ] Log policy entropy `H(π)` per bar and per ticker.
- [ ] Log critic value `V(s)` and value error against realized returns.
- [ ] Capture advantage traces `\hat{A}_t` around cooldown windows.
- [ ] Measure how often the policy is forced to remain long by `min_hold_bars`.
- [ ] Save per-run summaries for NVDA, AMD, and MU in a consistent audit folder.

## Phase 2 — Add Wave-Aware Inputs
- [ ] Define a small Elliott-inspired feature set.
- [ ] Add swing-high / swing-low structure features.
- [ ] Add pivot depth, retracement ratio, and impulse length features.
- [ ] Add regime context: trend strength, volatility expansion, and pullback pressure.
- [ ] Verify these features are computed without look-ahead.
- [ ] Keep raw and stationary feature pipelines aligned with training conventions.

## Phase 3 — Separate Entry From Exit
- [ ] Keep PPO focused on directional bias and regime selection.
- [ ] Move exit responsibility into `ExitManager` rules.
- [ ] Prototype exit rules for trailing stop, profit take, and wave-break invalidation.
- [ ] Add a soft exit confidence threshold instead of hard overfitting to one rule.
- [ ] Compare `no_exit` vs rule-based exit behavior on the same split.
- [ ] Prefer exits that protect capital without killing trend capture.

## Phase 4 — Remove Reward Distortion
- [ ] Zero out any action bonus that rewards trading for its own sake.
- [ ] Ensure transaction costs are always on during realism checks.
- [ ] Keep hold penalties small and interpretable.
- [ ] Avoid shaping that teaches the policy to fight constraints instead of learning signal.
- [ ] Recheck whether cooldown masking is sufficient before adding more penalties.

## Phase 5 — Retrain With Constraint Awareness
- [ ] Use `MaskablePPO` where action masking is available.
- [ ] Enable `use_cooldown_obs` so the model sees constraint state.
- [ ] Tune `min_hold_bars` per ticker rather than forcing one universal value.
- [ ] Run a low-friction AMD recovery sweep first.
- [ ] Re-run MU for entropy stability.
- [ ] Keep NVDA as the control baseline with `min_hold_bars=1`.

## Phase 6 — Validate Robustness
- [ ] Compare walk-forward and test results on the same ticker.
- [ ] Check trade rate, win rate, Sharpe, max drawdown, and turnover together.
- [ ] Confirm exit rules improve drawdown without creating cash collapse.
- [ ] Confirm the model does not become always-long or always-flat.
- [ ] Validate that behavior stays stable across nearby seeds.
- [ ] Reject any configuration that only looks good on one split.

## Phase 7 — Dashboard and Reporting
- [ ] Add plots for entropy, logits, and exit triggers.
- [ ] Show wave-aware signals alongside price and position state.
- [ ] Highlight periods where exits were forced by constraints.
- [ ] Keep experiment labels stable so results stay comparable.
- [ ] Export a concise experiment summary for promotion review.

## Acceptance Criteria
- [ ] Policy shows meaningful long/flat alternation instead of static buy bias.
- [ ] Exit behavior is explainable and rule-consistent.
- [ ] Performance remains positive after fees on the validation/test path.
- [ ] Drawdown improves without destroying trend capture.
- [ ] The system is robust enough to justify another promotion review.

## Recommended Run Order
1. NVDA control replay.
2. AMD low-friction recovery.
3. MU entropy stability check.
4. Wave-aware exit rule ablation.
5. Full walk-forward validation.

## Notes
- Elliott Wave should be treated as a soft structural guide, not a hard oracle.
- If wave features add noise, reduce them before increasing model complexity.
- If the critic is unstable, fix telemetry and reward clarity before adding more architecture.
- The safest improvement path is: measure -> simplify -> retrain -> validate.

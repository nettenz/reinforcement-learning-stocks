# Exit Signal — TODO Plan
**Created:** 2026-04-30  
**Updated:** 2026-05-05 (Post-Audit)  
**Status:** Phase 1 ready to start (diagnostic complete)  
**Approach:** Rule-based ExitManager layer on top of existing buy/hold ensemble agents

---

## AUDIT FINDINGS (May 5, 2026)

**Exit Signal Audit Results:**
- **NVDA:** 0% exit signals (427 bars analyzed) — stuck in unanimous buy (confidence 1.0000)
- **AMD:** 7.03% exit signals (30 exits, 427 bars) — healthy diversity (confidence 0.9578)
- **Performance gap:** AMD outperforms NVDA by 64% cumulative return (44.7% vs 27.3%), 9.2% Sharpe (1.995 vs 1.828)

**Root Cause Analysis (Reward Architect Diagnostic):**
- ✅ **Structural cap verified:** Both tickers have `max_weight_delta_per_step=0.1` (no overtrade bug)
- ✅ **Direction term clean:** Uses only bar T prices, no look-ahead leakage
- ✅ **Reward configs identical:** Both use `hold_penalty_scale=0.01`, `direction_scale=0.35`, `return_scale=1.0`
- ❌ **NOT a reward problem:** Exit divergence is learned behavior, not config issue
- **Root cause:** Market regime difference
  - NVDA test period (2024-08-15 to 2026-04-30): Bullish trend, few reversals → all seeds converged on "stay invested"
  - AMD test period (2024-08-16 to 2026-05-01): More churn/pullbacks → models learned exits naturally
  - Ensemble voting suppresses NVDA exits (unanimous) but captures AMD diversity

**Implication:** ExitManager is not a reward tuning exercise — it's a **risk management layer** to provide downside protection that the bull-market-trained ensemble lacks.

**Output files:**
- `data/audit/exit_signal_sweep/nvda_exit_audit.csv` — per-bar signal analysis (427 rows)
- `data/audit/exit_signal_sweep/amd_exit_audit.csv` — per-bar signal analysis (427 rows)
- `data/audit/exit_signal_summary.csv` — seed-level aggregates
- `scripts/analyze_reward_divergence.py` — full diagnostic logic
- `scripts/reward_divergence_diagnostic.py` — human-readable report

---

## Integration Assumption

- This TODO spans **two code surfaces**:
  1. RL model repo (this repo): `src/`, `scripts/`, `tests/`
  2. Separate web app repo: `backend/`, `frontend/`, Alpaca live feed integration
- Phase 1-2 are implemented in this repo first, then Phase 3-4 are wired in the web app.

---

## TODO LIST

### PHASE 1 — Core ExitManager (Week 1)

**Context:** NVDA ensemble is unanimous (0% exits), AMD is diverse (7% exits). ExitManager provides principled exit signals.

- [ ] **Create `src/exit_manager.py`**
  - `ExitManager` class with `rule`, `params`, `reset()`, `should_exit()` interface
  - Implement rule: `confidence` — exit when ensemble avg_confidence < threshold for N bars
    - For NVDA: leverage ensemble disagreement (NVDA vote_share=1.0 now, but adding diversity later could trigger)
    - For AMD: additional safety layer on top of existing 7% exits
  - Implement rule: `trailing_stop` — exit when unrealized P&L drops X% from peak
    - Addresses bull-market regime blindness (NVDA risk)
  - Implement rule: `time` — exit after holding MAX_HOLD_BARS regardless of P&L
    - Prevents "forever hold" in trending markets
  - Implement rule: `profit_take` — exit when unrealized P&L > threshold (e.g., 3-5%)
    - Locks in gains in bull markets (NVDA scenario)
  - **Recommended defaults for NVDA:**
    - Primary: `profit_take(threshold=0.03)` — exit at 3% gain (handles bull market)
    - Secondary: `trailing_stop(stop_pct=0.05)` — protect against reversals
  - **Recommended defaults for AMD:**
    - Optional enhancement: `profit_take(threshold=0.05)` — lock in larger gains
    - Already has natural 7% exits, so lower priority

- [ ] **Wire ExitManager into `src/ensemble.py` (SparseEnsemble) or create `src/trading_agent.py`**
  - Pattern: `EnsembleAgent.step(obs, position_state)` returns `(action, confidence, exit_fired, debug_info)`
  - Add `ExitManager` as optional parameter to ensemble inference wrapper
  - Flow:
    1. Get ensemble action and confidence
    2. Call `exit_manager.should_exit(position_state, confidence)` if in position
    3. If True, override action to 0 (exit signal)
    4. Return `(action, confidence, exit_fired, {'exit_rule': 'profit_take', ...})`
  - Keep return signature backward-compatible; expose `exit_fired` and `exit_rule` in debug info
  - **Compatibility:** Must work with both `SparseEnsemble` (voting) and future single-model variants

- [ ] **Write unit tests for ExitManager**
  - Test each rule fires correctly at boundary conditions
  - Test `reset()` clears state correctly between positions
  - Test that exit overrides hold but not a new buy signal

---

### PHASE 2 — Backtesting (Week 2)

- [ ] **Create `scripts/backtest_exit_rules.py`**
  - Load NVDA test split from `data/tech_training_data_nvda.parquet`
  - Load NVDA ensemble from `staging/models/ensemble_config.json` (seeds 13, 21, 42, 7)
  - Run three configs: no exit, confidence exit, trailing stop exit, time exit
  - Output metrics table per config:

  | Config | Sharpe | Alpha | Max DD | Avg Hold | Win Rate | Trades |
  |--------|--------|-------|--------|----------|----------|--------|
  | No exit (baseline) | | | | | | |
  | Confidence exit | | | | | | |
  | Trailing stop exit | | | | | | |
  | Time exit | | | | | | |

- [ ] **Tune exit parameters on NVDA val split only**
  - Confidence threshold: test [0.50, 0.60, 0.67, 0.75]
    - **Baseline NVDA confidence:** 1.0000 (unanimous) — may not fire until model diversity improves
    - **For now:** will be superseded by profit_take rule
  - Trailing stop: test [0.03, 0.05, 0.08, 0.10]
    - **Recommended start:** 0.05 (5% stop-loss)
  - Profit take: test [0.02, 0.03, 0.05, 0.08]
    - **Recommended start:** 0.03 (3% profit target for NVDA bull regime)
  - Time-based: test [10, 20, 30, 45] bars
    - **Recommended start:** 20 bars (typical reversion window)
  - **Evaluation metric:** Val Sharpe improvement, Max Drawdown reduction, Avg Hold time (target: 10-30 bars)
  - Pick best config per rule based on val metrics
  - Evaluate best params on test split (one shot — no re-tuning on test)
  - **Expected outcome:** NVDA test Sharpe ≥ 1.83 (baseline) with reduced max drawdown

- [ ] **Repeat on AMD once NVDA is validated**
  - Use AMD ensemble (seeds 7, 13, 42, 33, 5) from `sweep_amd_baseline_v5`
  - Same three rules, same parameter grid
  - Cross-ticker consistency check: do the same params work on AMD?

---

### PHASE 3 — Dashboard Integration (Week 3)

- [ ] **Define cross-repo signal contract before coding**
  - Canonical payload: `{date, action, confidence, exit_fired, exit_rule}`
  - Ensure this contract is produced in RL repo and consumed unchanged in web app
  - Explicitly map binary action semantics (buy/hold + exit flag) in API docs/comments

- [ ] **Create `backend/signals/agent.py`**
  - Load `EnsembleAgent` from `staging/models/ensemble_config.json`
  - Load `ExitManager` with best rule from Phase 2
  - `get_signals(symbol, bars_df)` → returns signal array per bar: `{action, confidence, exit_fired, position_state}`
  - Feature pipeline must match training: NVDA uses raw parquet, AMD uses stationary features

- [ ] **Wire into `backend/app.py`**
  - Add `/api/signals/:symbol` endpoint
  - Returns `signals[]` array alongside existing `candles[]` and `indicators[]`
  - Each signal: `{date, action, confidence, exit_fired}`

- [ ] **Frontend: Add signal overlay to `TradingChart.jsx`**
  - Buy markers: green triangle up on candle where `action=1`
  - Exit markers: red triangle down on candle where `exit_fired=true`
  - Confidence band: semi-transparent overlay showing confidence level per bar

- [ ] **Frontend: Add `ExitControls.jsx` component**
  - Dropdown: exit rule selector (None / Confidence / Trailing Stop / Time)
  - Sliders per rule: confidence threshold, stop %, max bars
  - Toggle: show/hide signal overlay
  - Wire to `/api/signals` with params in query string

---

### PHASE 4 — Alpaca Live Feed (Week 4)

- [ ] **Verify `.env` has correct keys**
  - Check `.env` file for `DATA_PROVIDER`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`

- [ ] **Verify `backend/data/source.py` Alpaca provider works**
  ```bash
  curl http://localhost:5000/api/health
  # Should return: { "status": "ok", "provider": "alpaca" }
  ```

- [ ] **Verify `/api/chart/NVDA` returns data via Alpaca**
  ```bash
  curl "http://localhost:5000/api/chart/NVDA?tf=1Day&limit=50"
  ```

- [ ] **Wire agent signals to live Alpaca bars**
  - `backend/signals/agent.py` `get_signals()` must accept bars from Alpaca format
  - Handle missing bars (market closed, no data) gracefully
  - Ensure feature computation has enough lookback (at least 252 bars for rolling features)

- [ ] **WebSocket tick → signal update**
  - When `ws/stream.py` emits a new tick, recompute latest signal
  - Push updated signal to frontend via `socketio.emit("signal_update")`
  - Frontend `useWebSocket.js` subscribes to `signal_update` and updates chart overlay

---

### CRITICAL CONSTRAINTS (do not violate)

- **NO reward tuning:** Exit divergence is environment fit, not reward miscalibration. Do not change `reward_*` params.
  - Direction term is clean (no look-ahead). Structural cap is set. Configs are identical.
  - ExitManager is a risk management layer, not a reward fix.
- Feature pipeline at inference must be **identical** to training
  - NVDA: raw parquet features, `use_stationary_features=False`
  - AMD: stationary features, `use_stationary_features=True`
  - Verify via `data/audit/exit_signal_sweep/nvda_exit_audit.csv` metadata
- Lookback window must have enough history before first signal (no cold-start signals)
- Exit rule parameters must be set from Phase 2 backtest, not tuned on live data
- Never retrain models based on live signal performance — that's a separate experiment
- Keep cross-repo payload contract stable once Phase 3 starts (avoid breaking frontend overlays)
- **NVDA priority:** Implement profit-taking + trailing stop (profit_take primary for bull regime)
- **AMD priority:** Optional enhancement (already has 7% exits); profit-taking for consistency

---

### SUCCESS CRITERIA

- [ ] **Backtest Performance (Phase 2):**
  - NVDA test Sharpe ≥ 1.83 (baseline with no exits, from audit: 1.828)
  - NVDA max drawdown reduces from -5.69% to ≤ -4.5% (downside protection)
  - NVDA average hold duration: 10–30 bars (vs currently infinite)
  - Exit signal rate: 5–10% on test split (vs current 0%)
  - AMD performance stable or improved with optional exit layer

- [ ] **Integration (Phase 3-4):**
  - ExitManager fires correctly in backtests and live feed
  - Buy and exit markers visible and correctly timed on dashboard
  - Live Alpaca feed producing signals in real time on NVDA and AMD
  - Feature pipeline matches training (e.g., NVDA uses raw features, not stationary)

- [ ] **Robustness:**
  - Exit rules don't interfere with buy signal generation
  - Position state tracking accurate (shares_held, entry_price, unrealized_pnl)
  - Exit manager resets correctly between positions

---

### PARKING LOT (future, not current scope)

- Option B: full long/short retraining with `long_only=False`
- Dollar-neutral portfolio across NVDA + AMD
- AAPL exit rules (blocked until leakage audit + promotion)
- BTC/crypto integration (separate reward/scoring system question unresolved)
- AI Sector Pipeline Phase 1 (FinBERT upgrade) — start after AAPL promoted

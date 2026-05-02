# Exit Signal — TODO Plan
**Created:** 2026-04-30  
**Status:** Ready to start after AAPL audit  
**Approach:** Rule-based ExitManager layer on top of existing buy/hold ensemble agents

---

## Integration Assumption

- This TODO spans **two code surfaces**:
  1. RL model repo (this repo): `src/`, `scripts/`, `tests/`
  2. Separate web app repo: `backend/`, `frontend/`, Alpaca live feed integration
- Phase 1-2 are implemented in this repo first, then Phase 3-4 are wired in the web app.

---

## TODO LIST

### PHASE 1 — Core ExitManager (Week 1)

- [ ] **Create `src/exit_manager.py`**
  - `ExitManager` class with `rule`, `params`, `reset()`, `should_exit()` interface
  - Implement rule: `confidence` — exit when ensemble avg_confidence < threshold for N bars
  - Implement rule: `trailing_stop` — exit when unrealized P&L drops X% from peak
  - Implement rule: `time` — exit after holding MAX_HOLD_BARS regardless of P&L
  - Default params: `confidence(threshold=0.60, n_bars=3)`, `trailing_stop(stop_pct=0.05)`, `time(max_bars=20)`

- [ ] **Wire ExitManager into `src/trading_agent.py`**
  - `EnsembleAgent.step()` currently returns `(action, confidence, debug_info)`
  - Add `ExitManager` as optional parameter to `EnsembleAgent.__init__`
  - In `step()`: if in position and `exit_manager.should_exit(position_state, confidence)` → override action to 0 (exit)
  - Keep return signature backward-compatible; expose `exit_fired` in debug info

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
  - Trailing stop: test [0.03, 0.05, 0.08, 0.10]
  - Time-based: test [10, 20, 30, 45] bars
  - Pick best per rule based on val Sharpe improvement
  - Evaluate best params on test split (one shot — no re-tuning on test)

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

- Feature pipeline at inference must be **identical** to training
  - NVDA: raw parquet features, `use_stationary_features=False`
  - AMD: stationary features, `use_stationary_features=True`
- Lookback window must have enough history before first signal (no cold-start signals)
- Exit rule parameters must be set from Phase 2 backtest, not tuned on live data
- Never retrain models based on live signal performance — that's a separate experiment
- Keep cross-repo payload contract stable once Phase 3 starts (avoid breaking frontend overlays)

---

### SUCCESS CRITERIA

- [ ] Sharpe on NVDA test with exit layer ≥ baseline Sharpe (1.64)
- [ ] Max drawdown reduces vs baseline
- [ ] Average hold duration 10–30 bars (vs effectively infinite currently)
- [ ] Buy and exit markers visible and correctly timed on dashboard
- [ ] Live Alpaca feed producing signals in real time on NVDA and AMD

---

### PARKING LOT (future, not current scope)

- Option B: full long/short retraining with `long_only=False`
- Dollar-neutral portfolio across NVDA + AMD
- AAPL exit rules (blocked until leakage audit + promotion)
- BTC/crypto integration (separate reward/scoring system question unresolved)
- AI Sector Pipeline Phase 1 (FinBERT upgrade) — start after AAPL promoted

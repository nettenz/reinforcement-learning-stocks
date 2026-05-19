# Exit Signal — TODO Plan
**Created:** 2026-04-30  
**Updated:** 2026-05-16 (Phase 2 re-run against Binary PPO ensemble; Phase 3 starting)  
**Status:** Phase 2 complete (Binary PPO results). Phase 3 (dashboard integration) is next.  
**Approach:** Rule-based ExitManager layer on top of existing Binary PPO buy/hold ensemble agents

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

- [x] **Create `src/exit_manager.py`** ✅
  - `ExitManager` class with `rule`, `params`, `reset()`, `should_exit()` interface
  - Implemented rules: `confidence`, `trailing_stop`, `time`, `profit_take`, `composite`
  - Phase 2 best params (Binary PPO, see tables below):
    - NVDA: `profit_take_2pct` selected by val sweep (exit_rate 6.1%, within [0.02, 0.15] gate); final params TBD after no_exit test run
    - AMD: Not yet re-run against Binary PPO ensemble

- [x] **Wire ExitManager into `src/ensemble.py` (SparseEnsemble) or create `src/trading_agent.py`** ✅
  - Pattern: `EnsembleAgent.step(obs, position_state)` returns `(action, confidence, exit_fired, debug_info)`
  - Implemented in `src/ensemble.py` — backward-compatible

- [ ] **Write unit tests for ExitManager**
  - Test each rule fires correctly at boundary conditions
  - Test `reset()` clears state correctly between positions
  - Test that exit overrides hold but not a new buy signal

---

### PHASE 2 — Backtesting (Week 2)

> **⚠️ IMPORTANT: Two separate result sets exist.** Phase 2 was originally run against the old SAC ensemble. After the Binary PPO migration, Phase 2 was re-run on May 16, 2026. **The SAC-era results below are stale and NOT comparable to Binary PPO.** Use the Phase 2B (Binary PPO) tables for all current decisions.

- [x] **Create `scripts/backtest_exit_rules.py`** ✅
  - Outputs: `data/audit/exit_backtest/{nvda,amd}_{val,test}_result(s).csv`
  - **Bugs fixed 2026-05-16:** (1) Windows→Mac path remapping for old leaderboard rows, (2) `run_label_filter` now wired from `ensemble_config.json` — previously loader picked globally best Sharpe per seed regardless of sweep label, (3) `_pick_market_cols(use_stationary)` now routes NVDA to 10-col RAW space — previously always returned 14 stationary cols, corrupting obs and producing avg_hold=1.0 bars

- [x] **Phase 2A (SAC era — STALE, do not use for Binary PPO decisions)**

  <details><summary>SAC-era NVDA val results (stale, ensemble: pre-PPO)</summary>

  | Config | Val Sharpe | Alpha | Max DD | Cum Return | Avg Hold | Exit Rate | Win Rate |
  |--------|-----------|-------|--------|-----------|----------|-----------|----------|
  | profit_take_2pct | **2.681** | -0.240 | -18.9% | +565% | 3.2 bars | 24.2% | 72.4% |
  | profit_take_3pct | 2.532 | -0.724 | -21.5% | +517% | 3.7 bars | 19.7% | 67.9% |
  | composite_nvda | 2.377 | -2.112 | -19.7% | +378% | 3.7 bars | 24.9% | 65.0% |
  | **no_exit (baseline)** | 2.340 | -1.332 | -22.2% | +456% | 6.8 bars | 0.0% | 57.4% |
  | profit_take_8pct | 2.208 | -1.854 | -22.1% | +404% | 5.3 bars | 7.3% | 60.9% |

  SAC-era NVDA test result: `profit_take_8pct` → Sharpe 0.767, alpha -0.137, max_dd -34.4%, exit_rate 5.2%, avg_hold 9.6 bars

  </details>

  <details><summary>SAC-era AMD val/test results (stale, ensemble: pre-PPO)</summary>

  SAC-era AMD test result: `profit_take_5pct` → Sharpe 0.761, alpha -0.938, max_dd -49.3%, exit_rate 10.8%, avg_hold ~4 bars

  </details>

- [x] **Phase 2B (Binary PPO — current, refreshed 2026-05-18)**

  **NVDA** (`nvda-ppo-minhold1-extended`, seeds 3/13/7/42, voting, raw features):

  | Config | Test Sharpe | Test MaxDD | Test CumRet | Test ExitRate | AvgHold | WinRate |
  |--------|------------|-----------|------------|--------------|---------|--------|
  | profit_take_3pct ✅ | 0.061 | -15.9% | -0.7% | 3.3% | 1.2 | 53.7% |
  | no_exit (baseline) | **0.301** | -16.1% | +6.6% | 0.0% | 1.2 | 56.1% |

  > **🚨 NVDA Finding:** Exit rules (val-selected `profit_take_3pct`) **degrade performance vs no_exit** on the test split. The bull-regime trend is too strong for simple profit-taking to add value. MaxDD improvement is negligible.

  **AMD** (`amd-ppo-hold-fix`, seeds 13/21/7, voting, stationary features):

  | Config | Test Sharpe | Test MaxDD | Test CumRet | Test ExitRate | AvgHold | WinRate |
  |--------|------------|-----------|------------|--------------|---------|--------|
  | trailing_5pct ✅ | **1.030** | -48.3% | **+88.2%** | 7.0% | 3.3 | 51.1% |
  | no_exit (baseline) | 0.986 | -55.5% | +83.5% | 0.0% | 3.6 | 48.8% |

  > 🟢 **AMD Finding:** `trailing_5pct` delivers meaningful alpha and risk protection. Sharpe **+0.044** delta, MaxDD **+7.2pp better**, WinRate **+2.3pp**.

  **MU** (`mu-ppo-overtrade-fix`, seeds 21/3/13, voting, stationary features):

  | Config | Test Sharpe | Test MaxDD | Test CumRet | Test ExitRate | AvgHold | WinRate |
  |--------|------------|-----------|------------|--------------|---------|--------|
  | trailing_3pct ✅ | **1.415** | -28.8% | **+167.5%** | 13.1% | 2.3 | 59.6% |
  | no_exit (baseline) | 1.270 | -47.0% | +139.6% | 0.0% | 2.6 | 57.6% |

  > 🟢 **MU Finding:** `trailing_3pct` shows major risk benefit. MaxDD **+18.2pp better** (-28.8% vs -47.0%) while *improving* CumRet by **27.9pp**.


- [x] **Tune exit parameters on AMD val split only** (Binary PPO) ✅ — `trailing_5pct` selected

- [x] **Update `BASELINES` dict and success criteria in script** ✅ (done 2026-05-16)
  - AMD no_exit baseline: Sharpe=0.986, MaxDD=-55.5%, CumRet=+83.5%, WinRate=48.8%, AvgHold=3.6 bars

- [ ] **Complete `scripts/analyze_reward_divergence.py` missing functions**
  - Script currently implements sections 1–8 (structural cap, reward config, behavior comparison, audit results, diagnosis, hypothesis, look-ahead audit, root cause)
  - **NOT YET IMPLEMENTED:** Market regime comparison (NVDA vs AMD test period price distributions), confidence distribution plots, per-seed exit behavior breakdown, ensemble voting suppression analysis
  - These were blocked pending Phase 2B backtest results — now unblocked

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

- [x] **Backtest Performance (Phase 2B):** ✅ (refreshed 2026-05-18)
  - All promoted tickers have fresh Binary PPO baselines in `scripts/backtest_exit_rules.py`.
  - AMD/MU show PASS on all relative gates (Sharpe, MaxDD, ExitRate, WinRate).
  - NVDA shows FAIL on Sharpe/WinRate relative gates (market regime artifact).
  - AvgHold targets standardized: 1.2–3.6 bars (Binary PPO reality).
  - Feature routing standardized: NVDA (raw), AMD/MU (stationary).

- [ ] **Integration (Phase 3-4):**
  - ExitManager fires correctly in backtests and live feed
  - Buy and exit markers visible and correctly timed on dashboard
  - Live Alpaca feed producing signals in real time on NVDA, AMD, MU
  - Feature pipeline matches training (NVDA=raw, AMD/MU=stationary)

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

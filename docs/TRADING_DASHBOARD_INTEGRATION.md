# Trading Dashboard Integration — Signal Contract & Wiring

This document describes the minimal API contract and wiring steps to connect the RL repo (Flask backend + model ensemble) to the React/Vite frontend dashboard (TradingChart). It includes a small Flask blueprint stub and a React `ExitControls` component you can drop into the dashboard.

## Goals
- Provide a stable JSON signal contract consumed by the frontend.
- Show a minimal Flask endpoint that loads the staging ensemble config and returns signals for a symbol.
- Provide a small React/Vite component to call the endpoint and surface exit controls.

## Signal API Contract

Endpoint: `GET /api/signals/:symbol`

Query params (optional):
- `start` — ISO date string (inclusive)
- `end` — ISO date string (inclusive)
- `rule` — exit rule name (e.g. `confidence`, `trailing_stop`, `time`) — used to compute exit flags
- `use_config` — `true|false` (whether to use `staging/models/ensemble_config.json`)

Response (200):

{
  "symbol": "NVDA",
  "start": "2024-08-14",
  "end": "2026-04-29",
  "signals": [
    {
      "date": "2024-08-14",
      "action": 1,            # 0 Hold, 1 Buy, 2 Sell
      "confidence": 0.92,     # ensemble confidence 0.0-1.0
      "exit_fired": false,    # whether exit rule fired on this bar
      "exit_rule": "confidence",
      "position_state": {"shares_held": 1, "current_weight": 1.0}
    },
    ...
  ]
}

Date fields are ISO strings. All numeric fields are plain JSON numbers.

## Backend responsibilities
- Load ensemble configuration from `staging/models/ensemble_config.json` to select seeds.
- Use the same feature pipeline (`use_stationary_features`, `include_news`) as the model training for the requested symbol.
- Construct an `EnsembleAgent` (or equivalent) with the ensemble and run it over the requested bars to produce `action` and `confidence` per bar.
- Run `ExitManager` (or simple heuristics) to set `exit_fired` when rule conditions apply.
- Return the JSON above.

## Minimal Flask stub
- See `backend/signals/agent.py` for an example blueprint you can mount into your Flask app.

## Frontend contract and sample component
- The provided `ExitControls.jsx` (React + Vite) demonstrates fetching `/api/signals/:symbol` and wiring a simple UI with rule selector and parameter sliders.

## Security and production notes
- Add auth/ACL to the endpoint for production (Bearer tokens or session-based auth).
- Cache signals for common queries to avoid reloading models on every request.
- Restart backend when `staging/models/ensemble_config.json` changes so the agent picks up the new seeds.

## Next steps
1. Drop `backend/signals/agent.py` into your Flask app and register the blueprint.
2. Add `ExitControls.jsx` into the React dashboard and import it in `TradingChart.jsx`.
3. Restart the backend and check `/api/signals/NVDA` via `curl` or the browser.

---
Created: May 03, 2026

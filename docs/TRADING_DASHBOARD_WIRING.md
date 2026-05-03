# Trading Dashboard Wiring Guide (Comprehensive)

Purpose: a single, reviewable plan that shows exactly how to wire the RL ensemble signals into your trading-dashboard before you edit any files in that repo. It presents two safe integration approaches (recommended order), exact file edits, runtime commands, test commands, and production notes.

## Overview

- **Approach A (fast, low-risk)**: Export signals from the RL repo as cached JSON files or a tiny HTTP service, and let the trading-dashboard fetch them. No deep imports; minimal backend changes.
- **Approach B (integrated)**: Install / import the RL code into the trading-dashboard backend (or package it) and call `EnsembleAgent` directly. More powerful but requires dependency alignment and tests.

## Prerequisites (both approaches)

- Ensure both repos are on the same machine or the RL repo is reachable via network.
- Python environment: use the RL repo's `.venv` for running export/test scripts. Document exact Python and package versions in `requirements.txt` for compatibility.
- Confirm `staging/models/ensemble_config.json` is the canonical pinned file and is up-to-date.

## Approach A — Exported signals (recommended first step)

**Rationale:** minimal changes to the trading-dashboard; you can iterate on the endpoint contract while preserving current dashboard stability.

1) From RL repo: add an export script that writes signals JSON per symbol.

Suggested path (in RL repo): `scripts/export_signals_for_dashboard.py`

Example script (sketch — adapt your `EnsembleAgent` call):

```python
from pathlib import Path
import json
from src.ensemble import SparseEnsemble  # or your EnsembleAgent factory

OUT = Path('data/dashboard_signals')
OUT.mkdir(exist_ok=True)

def export_symbol(symbol, start=None, end=None, rule='confidence'):
    ensemble = SparseEnsemble.from_config('staging/models/ensemble_config.json', symbol)
    # run inference over desired bars, returning list[dict]
    signals = ensemble.run_over_history(symbol, start=start, end=end, exit_rule=rule)
    p = OUT / f"{symbol.lower()}_signals.json"
    p.write_text(json.dumps({"symbol":symbol,"signals":signals}, indent=2))

if __name__ == '__main__':
    # export the promoted symbols
    for s in ['NVDA','AMD']:
        export_symbol(s)
```

2) Place exports in a shared location the trading-dashboard can read. Two options:

- File share: the trading-dashboard reads `../reinforcement-learning-stocks/data/dashboard_signals/*.json`.
- HTTP: run a tiny static file server (or use the RL Flask stub `/api/signals/:symbol`) on port 5100 and let the dashboard proxy it.

3) Trading-dashboard backend change (very small): add an adapter route that loads JSON and forwards it at `/api/signals/:symbol`.

Edit file: `backend/app.py`

Add import and route (example patch):

```python
from flask import send_file, jsonify
from pathlib import Path

@app.route('/api/signals/<symbol>')
def signals_adapter(symbol):
    p = Path(__file__).resolve().parents[1] / '..' / 'reinforcement-learning-stocks' / 'data' / 'dashboard_signals' / f"{symbol.lower()}_signals.json"
    p = p.resolve()
    if not p.exists():
        return jsonify({"error": "signals not found"}), 404
    return send_file(str(p), mimetype='application/json')
```

**Notes:**

- No model imports in trading-dashboard.
- Ensure the file path is correct relative to the dashboard service, or make the path configurable via `BACKEND_SIGNALS_DIR` env var.

4) Frontend: call `/api/signals/:symbol` from `ExitControls.jsx` or `TradingChart.jsx` the same way as other REST calls (use existing `useChartData` pattern). No CORS changes needed if the dashboard hosts both frontend and backend.

## Approach B — Integrated EnsembleAgent (deeper integration)

**Rationale:** direct inference, fresh signals on-demand, customizable parameters. Requires dependency alignment and tests.

1) Decide packaging strategy:

- **Option B1:** Install RL repo into Python environment of trading-dashboard with `pip install -e /path/to/reinforcement-learning-stocks` and import `src.ensemble` and friends.
- **Option B2:** Copy a small dedicated agent module from RL repo into trading-dashboard `backend/agents/ensemble_agent.py` (vendor specific code). Keep it minimal to avoid heavy deps.

2) Backend changes (if using Option B1):

Edit `backend/app.py` — add a new blueprint mount (example):

```python
from rl_integration import signals_bp  # rl_integration is a tiny package that wraps RL repo calls
app.register_blueprint(signals_bp)

# where rl_integration/signals.py exposes `signals_bp` that uses EnsembleAgent
```

Example of `rl_integration/signals.py` (in trading-dashboard repo):

```python
from flask import Blueprint, request, jsonify
from reinforcement_learning_stocks.src.ensemble import SparseEnsemble

bp = Blueprint('rl_signals', __name__)

@bp.route('/api/signals/<symbol>')
def get_signals(symbol):
    cfg_path = '/opt/reinforcement-learning-stocks/staging/models/ensemble_config.json'
    ens = SparseEnsemble.from_config(cfg_path, symbol)
    start = request.args.get('start')
    end = request.args.get('end')
    # run the ensemble over data using the dashboard's DataSource.get_bars()
    bars = get_bars_for_symbol(symbol, start, end)
    signals = ens.run_on_bars(bars)
    return jsonify({"symbol":symbol, "signals":signals})
```

3) Dependency and operational issues:

- The RL repo may require `torch`, `stable-baselines3`, `pandas` versions that differ from the dashboard. Prefer Option B2 if you want to avoid causing a dependency conflict in production.
- If you choose B1, vendor the RL environment into a separate virtualenv and run the signals endpoint as a distinct process (e.g., `gunicorn`/Flask) and proxy from the trading-dashboard (this is similar to Approach A HTTP variant).

## Testing and verification (recommended)

- **Approach A test (file mode):**
  - Export signals: `python -m scripts.export_signals_for_dashboard`
  - From trading-dashboard backend container or local env: `curl http://localhost:5000/api/signals/NVDA` should return JSON.

- **Approach B test (integrated):**
  - Unit test: add `tests/test_signals.py` that imports your endpoint and calls the Flask test client.
  - Integration test: run dashboard and query the endpoint.

## Commands (examples)

```bash
# Export (RL repo)
.venv\Scripts\python.exe scripts\export_signals_for_dashboard.py

# Start trading-dashboard backend (Windows)
# in trading-dashboard/backend
.venv\Scripts\activate
python app.py

# Quick curl test
curl http://localhost:5000/api/signals/NVDA
```

## Caching, performance, and deployment

- If you run inference on-demand (Approach B), cache results per symbol+date range for e.g. 5–15 minutes.
- Precompute and serve compressed JSON for historical ranges; only run live inference for near-real-time windows.
- Use a simple LRU or Redis cache to avoid reloading large models per request.

## Security

- Protect `/api/signals` endpoints with internal ACL or a bearer token when the dashboard is user-facing.
- If the RL service is on a different host, secure with HTTPS and restrict network access to the dashboard host.

## Suggested minimal file edits to review (trading-dashboard repo)

- `backend/app.py`: add `register_blueprint()` lines and an env var `BACKEND_SIGNALS_DIR` fallback.
- `frontend/src/components/ExitControls.jsx`: import `ExitControls` component (or copy the one from this repo) and place it in `TradingChart.jsx` near the `IndicatorPanel` or toolbar.

Example lines to insert into `frontend/src/components/TradingChart.jsx`:

```jsx
import ExitControls from './ExitControls'
...
<div className="chart-sidebar">
  <ExitControls symbol={symbol} />
</div>
```

## Checklist before making changes in trading-dashboard

- Pick Approach A or B.
- Run exports and confirm JSON shape matches `docs/TRADING_DASHBOARD_INTEGRATION.md` contract.
- Add only the small adapter route or a blueprint registration; run manual curl tests.
- Add frontend import and render; test locally.

## What's next I can do for you

- Produce exact diff/patch for the trading-dashboard `backend/app.py` and `frontend/src/components/TradingChart.jsx` to implement Approach A adapter (file-based) so you can review before applying.
- Or produce a minimal `rl_export` script in this repo that writes the JSON exports (I can create and run it here using your existing `Ensemble` utilities).

If you want a patch for the trading-dashboard repo, tell me whether you prefer Approach A (file/http adapter) or Approach B (integrated). I will produce the exact diffs for `backend/app.py` and `frontend` files for your review.

Created: May 03, 2026

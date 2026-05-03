# Walkthrough - RL Signal Integration

We have successfully integrated reinforcement learning signals from the `reinforcement-learning-stocks` repository into the `trading-dashboard`. This enables real-time (or historical) visualization of AI-driven trading decisions directly on the chart.

## Changes Made

### 1. RL Repository: Signal Export Pipeline
- **Script**: [export_signals_for_dashboard.py](file:///d:/code/agentic-development/reinforcement-learning-stocks/scripts/export_signals_for_dashboard.py)
- **Logic**:
    - Automatically detects the observation space required by the top-performing models in the leaderboard.
    - Matches environment features (stationary vs raw) to the model's training configuration.
    - Performs deterministic inference using a `SparseEnsemble` (Top 5 models).
    - Exports signals to JSON with Unix timestamps for frontend compatibility.
- **Artifacts Generated**: `nvda_signals.json` and `amd_signals.json`.

### 2. Dashboard Backend: Signal Adapter
- **File**: [app.py](file:///d:/code/web-development/trading-dashboard/backend/app.py)
- **New Route**: `/api/signals/<symbol>`
    - Ingests the exported JSON files from the RL repository.
    - Handles path mapping between the two decoupled repositories.

### 3. Dashboard Frontend: UI & Visualization
- **New Component**: [ExitControls.jsx](file:///d:/code/web-development/trading-dashboard/frontend/src/components/ExitControls.jsx)
    - Provides a toggle button to enable/disable the "RL AI" layer.
    - Fetches signals on demand when enabled.
- **Integration**:
    - [Toolbar.jsx](file:///d:/code/web-development/trading-dashboard/frontend/src/components/Toolbar.jsx) now includes the RL toggle.
    - [TradingChart.jsx](file:///d:/code/web-development/trading-dashboard/frontend/src/components/TradingChart.jsx) renders the signals as markers (arrowUp/arrowDown) with confidence percentages.

## Verification Results

### Backend Export
The export script was hardened to handle diverse model configurations (10 vs 18 vs 27 features) and successfully generated valid JSON for NVDA and AMD.

### Marker Rendering
Signals are merged with existing technical indicators (like TMA crossovers) and sorted by time, ensuring a smooth historical overlay.

> [!TIP]
> To update signals for new symbols, simply run the export script in the RL repository:
> `.venv\Scripts\python.exe scripts\export_signals_for_dashboard.py`

## Next Steps
- Implement **Approach B** (Direct Python Bridge) if real-time sub-minute inference becomes a requirement.
- Add "Confidence Heatmap" to the volume pane for a more nuanced view of the ensemble's agreement.

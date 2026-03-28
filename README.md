# Reinforcement Learning - Trading Bot Project

This project focuses on building an RL-powered trading bot using **Gymnasium** and **Stable Baselines3**.

## Quick Start

| OS | Create venv | Activate venv | Install deps | Run smoke test |
|---|---|---|---|---|
| Windows (PowerShell) | `py -m venv .venv` | `.venv\Scripts\Activate.ps1` | `python -m pip install -r requirements.txt` | `python tests/test_script.py` |
| macOS / Linux (Bash/Zsh) | `python3 -m venv .venv` | `source .venv/bin/activate` | `python -m pip install -r requirements.txt` | `python tests/test_script.py` |

## Project Structure
- `src/`: core Python modules (`market_data.py`, `news_data.py`, `signal_analytics.py`, `trading_env.py`, `train_bot.py`)
- `data/`: datasets and cached training frames
- `models/`: trained model artifacts
- `tests/`: smoke/integration scripts
- `notebooks/`: exploratory notebooks
- `docs/`: strategy and execution docs

## Current Features:
- **Custom Environment:** `src/trading_env.py` (simulates a basic trading desk).
- **Training Pipeline:** `src/train_bot.py` (uses PPO algorithm + Yahoo Finance tech-stock data).
- **Market Data Pipeline:** `src/market_data.py` (fetch, parse, normalize, and cache OHLCV data).
- **Mock Data (fallback/reference):** `data/mock_data.csv` (synthetic OHLCV data).

## How to Run:
### Windows (PowerShell)
1.  **Create Virtual Env:** `py -m venv .venv`
2.  **Activate Virtual Env:** `.venv\Scripts\Activate.ps1`
3.  **Install Dependencies:** `python -m pip install -r requirements.txt`
4.  **Run Training:** `python src/train_bot.py`
5.  **Run Smoke Test:** `python tests/test_script.py`
6.  **Run Streamlit Integration (Signal Analytics):** `python -m streamlit run src/analytics_dashboard.py`
7.  **Explore Basics:** Open `notebooks/getting-started.ipynb` in Jupyter.

### Signal Analytics Dashboard (Streamlit)
Use this dashboard to tune buy/sell signal accuracy against forward returns.

1. Install dependencies (includes Streamlit): `python -m pip install -r requirements.txt`
2. Run dashboard: `python -m streamlit run src/analytics_dashboard.py`
3. In the sidebar:
   - Set data path (`data/tech_training_data.csv` or `data/mock_data.csv`)
   - Set model path (`models/ppo_trading_bot` or `.zip`)
   - Tune movement threshold and prediction horizon
4. Click **Run analytics** to view:
    - overall/actionable accuracy
    - buy/sell precision + recall
    - confusion matrix and signal log
    - action distribution and recent buy/sell points

Dashboard sections:
- `Signal Analytics`: evaluate a specific model's buy/sell quality.
- `Experiments`: run aggressive multi-seed sweeps and inspect leaderboard results.

PowerShell launcher (Windows):
- Start: `.\run_dashboard.ps1 -Action start`
- Status: `.\run_dashboard.ps1 -Action status`
- Stop: `.\run_dashboard.ps1 -Action stop`
- Custom port: `.\run_dashboard.ps1 -Action start -Port 8502`

Bash launcher (macOS/Linux):
- Start: `./run_dashboard.sh start 8501`
- Status: `./run_dashboard.sh status 8501`
- Stop: `./run_dashboard.sh stop 8501`

### News Sentiment Data Pipeline
Build daily ticker-level news sentiment features to feed future model training/tuning.

Example (PowerShell):
`python -c "from src.news_data import get_tech_news_features; df = get_tech_news_features(refresh=True); print(df.tail())"`

Cached output:
- `data/tech_news_sentiment_data.csv`

Output columns:
- `Ticker`, `Date`, `NewsCount`
- `SentimentMean`, `SentimentStd`, `SentimentMin`, `SentimentMax`

### Sentiment Integration in Training
The training frame now merges daily news sentiment into market features.

- `get_tech_training_data(include_news=True)` merges `tech_news_sentiment_data.csv` into the date-level basket.
- Missing news days are filled with neutral defaults (`0.0` values).
- `TradingEnv` automatically includes available sentiment columns in observations.
- `train_bot.py` uses the merged frame by default.

Reference:
- `docs/SENTIMENT_INTEGRATION.md`

### Aggressive Experiment Runner
Run multi-seed PPO sweeps with walk-forward validation and leaderboard ranking.

Example (fast smoke):
`python src/experiments.py --include-news --seeds 7,13 --timesteps 2000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.0 --max-runs 2`

Default outputs:
- `data/experiment_leaderboard.csv`
- `data/experiment_summary.json`

### macOS / Linux (Bash/Zsh)
1.  **Create Virtual Env:** `python3 -m venv .venv`
2.  **Activate Virtual Env:** `source .venv/bin/activate`
3.  **Install Dependencies:** `python -m pip install -r requirements.txt`
4.  **Run Training:** `python src/train_bot.py`
5.  **Run Smoke Test:** `python tests/test_script.py`
6.  **Run Streamlit Integration (Signal Analytics):** `python -m streamlit run src/analytics_dashboard.py`
7.  **Run Dashboard Launcher (optional):** `chmod +x run_dashboard.sh && ./run_dashboard.sh start 8501`
8.  **Run Experiments (example):** `python src/experiments.py --include-news --seeds 7,13 --timesteps 2000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.0 --max-runs 2`
9.  **Explore Basics:** Open `notebooks/getting-started.ipynb` in Jupyter.

## Development Strategy:
The long-term goal is to implement a robust **Shorting Strategy** (see `docs/PLAN.md`).

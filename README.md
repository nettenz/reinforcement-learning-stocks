# Reinforcement Learning - Trading Bot Project

This project focuses on building an RL-powered trading bot using **Gymnasium** and **Stable Baselines3**.

## Project Structure
- `src/`: core Python modules (`market_data.py`, `trading_env.py`, `train_bot.py`)
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
1.  **Activate Virtual Env:** `cd reinforcement-learning && source venv_darwin/bin/activate`
2.  **Install Dependencies:** `pip install -r requirements.txt`
3.  **Run Training:** `python src/train_bot.py`
4.  **Run Smoke Test:** `python tests/test_script.py`
5.  **Explore Basics:** Open `notebooks/getting-started.ipynb` in Jupyter.

## Development Strategy:
The long-term goal is to implement a robust **Shorting Strategy** (see `docs/PLAN.md`).

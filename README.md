# Reinforcement Learning - Trading Bot Project

This project focuses on building an RL-powered trading bot using **Gymnasium** and **Stable Baselines3**.

## Current Features:
- **Custom Environment:** `trading_env.py` (simulates a basic trading desk).
- **Training Pipeline:** `train_bot.py` (uses PPO algorithm + Yahoo Finance tech-stock data).
- **Market Data Pipeline:** `market_data.py` (fetch, parse, normalize, and cache OHLCV data).
- **Mock Data (fallback/reference):** `mock_data.csv` (synthetic OHLCV data).

## How to Run:
1.  **Activate Virtual Env:** `cd reinforcement-learning; .\venv\Scripts\activate`
2.  **Install Dependencies:** `pip install -r requirements.txt`
3.  **Run Training:** `python train_bot.py`
4.  **Explore Basics:** Open `getting-started.ipynb` in Jupyter.

## Development Strategy:
The long-term goal is to implement a robust **Shorting Strategy** (see `PLAN.md`).

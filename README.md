# Reinforcement Learning - Trading Bot Project

This project focuses on building an RL-powered trading bot using **Gymnasium** and **Stable Baselines3**.

## Quick Start

| OS | Create venv | Activate venv | Install deps | Run smoke test |
|---|---|---|---|---|
| Windows (PowerShell) | `py -m venv .venv` | `.venv\Scripts\Activate.ps1` | `python -m pip install -r requirements.txt` | `python tests/test_script.py` |
| macOS / Linux (Bash/Zsh) | `python3 -m venv .venv` | `source .venv/bin/activate` | `python -m pip install -r requirements.txt` | `python tests/test_script.py` |

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
### Windows (PowerShell)
1.  **Create Virtual Env:** `py -m venv .venv`
2.  **Activate Virtual Env:** `.venv\Scripts\Activate.ps1`
3.  **Install Dependencies:** `python -m pip install -r requirements.txt`
4.  **Run Training:** `python src/train_bot.py`
5.  **Run Smoke Test:** `python tests/test_script.py`
6.  **Explore Basics:** Open `notebooks/getting-started.ipynb` in Jupyter.

### macOS / Linux (Bash/Zsh)
1.  **Create Virtual Env:** `python3 -m venv .venv`
2.  **Activate Virtual Env:** `source .venv/bin/activate`
3.  **Install Dependencies:** `python -m pip install -r requirements.txt`
4.  **Run Training:** `python src/train_bot.py`
5.  **Run Smoke Test:** `python tests/test_script.py`
6.  **Explore Basics:** Open `notebooks/getting-started.ipynb` in Jupyter.

## Development Strategy:
The long-term goal is to implement a robust **Shorting Strategy** (see `docs/PLAN.md`).

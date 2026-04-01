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
- **Custom Environment:** `src/trading_env.py` (simulates a basic trading desk with OOP position management).
- **Training Pipeline:** `src/train_bot.py` (SAC algorithm + automated feature engineering).
- **Advanced Indicators:** RSI, MACD, ATR, Bollinger Bands, and SMA 20/50 Trend Crosses integrated into the observation space.
- **Stationary Features:** `--use-stationary-features` mode to reduce price-level memorization and improve generalization.
- **Multi-Seed Sweeps:** `src/experiments.py` for massive parallelized hyperparameter optimization.
- **AI Strategic Analyst:** Automated LLM-driven interpretation of quant results using Gemini 2.0.

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
- `Experiment Insights`: aggregate snapshot history, visualize val/test actionable-accuracy trends, and generate next-run commands.

### Accuracy Improvement Workflow

Follow this loop to iteratively improve actionable accuracy:

1. **Experiment Insights** — run recommended commands (stability, accuracy, generalization)
2. **Experiment Insights** — check updated trend; did collapse rate drop? did accuracy improve?
3. **Signal Analytics** — if a run looks promising, inspect that model's buy/sell behavior in detail
4. **Experiments** — optionally tweak knobs manually and re-run
5. Repeat from step 1 until val/test actionable accuracy consistently hits target (default 0.55)

**Key metrics to watch:**
- Collapse rate (seeds with 0% actionable accuracy)
- Val/test actionable accuracy gap (overfit risk)
- Trade win rate stability across seeds

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
- **Technical Indicators**: `RelATR`, `BB_Width`, `SMA_Trend`, `RSI_Centered`, `RelMACD`

### Environment Configuration (.env)
Create a `.env` file in the root to manage API keys and provider settings:
```env
GEMINI_API_KEY=your_key_here
NEWS_SENTIMENT_PROVIDER=hybrid
OLLAMA_URL=http://127.0.0.1:11434/api/generate
```

### Sentiment Integration in Training
The training frame now merges daily news sentiment into market features.

- `get_tech_training_data(include_news=True)` merges `tech_news_sentiment_data.csv` into the date-level basket.
- Missing news days are filled with neutral defaults (`0.0` values).
- `TradingEnv` automatically includes available sentiment columns in observations.
- `train_bot.py` uses the merged frame by default.

Reference:
- `docs/SENTIMENT_INTEGRATION.md`

### Aggressive Experiment Runner
Run multi-seed SAC sweeps with walk-forward validation and leaderboard ranking.

Example (fast smoke):
`python src/experiments.py --seeds 7,13 --timesteps 2000 --reward-mode sharpe --max-runs 2`

**Reward Strategy Knobs:**
- `--reward-mode`: Choose between `legacy` (directional), `sharpe` (risk-adjusted), or `sortino` (downside-adjusted).
- `--rolling-reward-window`: Window size (default: 100) for calculating rolling Sharpe/Sortino metrics.
- `--reward-epsilon`: Numerical stability constant (default: 1e-6).
- `--reward-return-scale`: weight on portfolio return term.
- `--reward-direction-scale`: weight on directional alignment with next-step movement.
- `--reward-hold-penalty-scale`: penalty for Hold during high-movement steps.
- `--reward-drawdown-penalty-scale`: penalty proportional to drawdown from reward-portfolio peak.
- `--reward-clip`: symmetric reward clipping bound.
- `--reward-ignore-transaction-cost` / `--no-reward-ignore-transaction-cost`: include or exclude fee/penalty effects in reward shaping.

**Environment Improvements:**
- **OOP Position Management:** Uses `src/trading_env.py`'s `PositionManager` for corrected, high-fidelity P&L and Net Worth tracking.
- **Stationary Features:** Option to use `--use-stationary-features` for log returns and normalized technical indicators.

Default outputs:
- `data/experiment_leaderboard.csv`
- `data/experiment_reward_leaderboard.csv`
- `data/experiment_summary.json`
- `sessions/quant-report-YYYY-MM-DD.md` (AI-Augmented Interpretation)
- `data/experiment_summary.json`
- Timestamped snapshots in `data/experiment_snapshots/` (enabled by default)

Snapshot controls:
- `--snapshot-dir`: set a custom snapshot directory
- `--disable-snapshots`: keep overwrite-only behavior for this run
- `--run-label`: append a readable suffix to snapshot filenames

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

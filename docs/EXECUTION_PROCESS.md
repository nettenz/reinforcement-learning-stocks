# Yahoo Finance Tech-Stock Training Data Execution Process

## 1) Goal
Build a repeatable pipeline that pulls Yahoo Finance OHLCV data for tech stocks, parses and normalizes it, then feeds it into PPO training.

## 2) Core Components
- `src/market_data.py`
  - `fetch_yahoo_ohlcv(...)`: pulls raw OHLCV data per ticker from Yahoo Finance.
  - `parse_and_normalize_ohlcv(...)`: validates columns and normalizes features.
  - `build_training_frame(...)`: aggregates multiple tickers into one date-indexed basket.
  - `get_tech_training_data(...)`: caches/reuses `data/tech_training_data.csv`.
- `src/train_bot.py`
  - Loads cached/fresh tech-stock training data via `get_tech_training_data()`.
  - Trains PPO with `TradingEnv`.
- `src/trading_env.py`
  - Uses normalized OHLCV values (`Open`, `High`, `Low`, `Close`, `Volume`) for observations.
  - Uses `RawClose` for trading execution price when available.

## 3) Data Flow
1. Pull daily OHLCV data for default tech tickers:
   - `AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA`
2. Parse into a clean schema:
   - `Date, Ticker, Open, High, Low, Close, Volume`
3. Normalize features:
   - `OpenNorm = Open / prev_close - 1`
   - `HighNorm = High / Close - 1`
   - `LowNorm = Low / Close - 1`
   - `CloseNorm = pct_change(Close)`
   - `VolumeNorm = diff(log1p(Volume))`
4. Aggregate cross-ticker basket by date (mean values).
5. Save output to `data/tech_training_data.csv`.
6. Train PPO on the resulting dataset.

## 4) Commands
Use the project virtual environment and run the pipeline/training commands below.

### 4.1 Create + activate environment

Windows (PowerShell):

```powershell
cd D:\code\reinforcement-learning-stocks
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linux (Bash/Zsh):

```bash
cd /path/to/reinforcement-learning-stocks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Refresh and inspect Yahoo Finance tech-stock training data:

Windows (PowerShell):

```powershell
cd D:\code\reinforcement-learning-stocks
python -c "from src.market_data import get_tech_training_data; df = get_tech_training_data(cache_path='data/tech_training_data.csv', refresh=True); print('rows:', len(df)); print('columns:', df.columns.tolist()); print(df.head(3).to_string(index=False))"
```

macOS / Linux (Bash/Zsh):

```bash
cd /path/to/reinforcement-learning-stocks
python - <<'PY'
from src.market_data import get_tech_training_data

df = get_tech_training_data(cache_path="data/tech_training_data.csv", refresh=True)
print("rows:", len(df))
print("columns:", df.columns.tolist())
print(df.head(3).to_string(index=False))
PY
```

Run training:

Windows (PowerShell):

```powershell
cd D:\code\reinforcement-learning-stocks
python src/train_bot.py
```

macOS / Linux (Bash/Zsh):

```bash
cd /path/to/reinforcement-learning-stocks
python src/train_bot.py
```

Run smoke test:

Windows (PowerShell):

```powershell
cd D:\code\reinforcement-learning-stocks
python tests/test_script.py
```

macOS / Linux (Bash/Zsh):

```bash
cd /path/to/reinforcement-learning-stocks
python tests/test_script.py
```

## 5) Key Concepts
- **Parsing**: convert raw provider output into consistent column types/shape.
- **Normalization**: transform features to percentage/log-delta style values so training is less scale-sensitive.
- **Basket aggregation**: combine multiple tech tickers into a single market signal series.
- **Caching**: avoid unnecessary repeated network pulls with `data/tech_training_data.csv`.
- **Raw execution price**: keep `RawClose` for realistic buy/sell accounting while learning from normalized signals.

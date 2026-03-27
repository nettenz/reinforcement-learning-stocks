# Sentiment Feature Integration

## Goal
Integrate daily news sentiment into the RL training data and environment observations so the policy can condition decisions on both market behavior and recent news tone.

## Data Flow
1. `src/news_data.py` fetches Yahoo ticker news and computes article-level sentiment scores from title + summary.
2. It aggregates to daily ticker features:
   - `NewsCount`
   - `SentimentMean`
   - `SentimentStd`
   - `SentimentMin`
   - `SentimentMax`
3. `src/market_data.py` builds the date-level market basket from normalized OHLCV.
4. `merge_news_features(...)` collapses ticker-level sentiment to daily basket features and left-joins on `Date`.
5. Missing sentiment rows are filled with neutral defaults (`0.0`) to keep training deterministic.

## Environment Integration
`src/trading_env.py` now builds observations dynamically:
- Base market features: `Open`, `High`, `Low`, `Close`, `Volume`
- Optional sentiment features if present in the dataframe
- Portfolio state: `balance`, `shares_held`

Observation size is derived from active columns, so old datasets still run while enriched datasets add new input dimensions.

## Training Usage
`src/train_bot.py` calls:

`get_tech_training_data(cache_path=DATA_PATH, include_news=True)`

This makes sentiment-enabled training the default path.

## Verification Steps
1. Generate or load cached news features:
   - `python -c "from src.news_data import get_tech_news_features; print(get_tech_news_features().tail())"`
2. Build merged training data:
   - `python -c "from src.market_data import get_tech_training_data; df=get_tech_training_data(include_news=True, refresh=True); print(df.columns)"`
3. Run smoke test:
   - `python tests/test_script.py`

## Current Limits
- Sentiment scoring is lexicon-based (fast, deterministic, lightweight).
- Aggregation is daily; no intraday alignment yet.
- No indicator features yet; these are planned after sentiment integration.

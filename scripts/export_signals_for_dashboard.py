import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Standardize path handling
def get_abs_path(rel_path):
    return (ROOT_DIR / rel_path).resolve()

try:
    from src.ensemble import SparseEnsemble
    from src.market_data import get_tech_training_data
    from src.trading_env import TradingEnv
except ImportError as e:
    print(f"Error importing project modules: {e}")
    sys.exit(1)

def calculate_simulated_pnl(signals_list, initial_balance=1000.0):
    """
    Calculate cumulative P&L from signal actions and prices.
    Assumes: action=1 is long, action=0 is flat/exit.
    """
    if not signals_list:
        return 0.0, 0.0, 0.0, 0
    
    balance = initial_balance
    shares_held = 0
    entry_price = 0.0
    trade_count = 0
    peak_balance = initial_balance
    
    for i, sig in enumerate(signals_list):
        price = sig["price"]
        action = sig["action"]
        
        if action == 1 and shares_held == 0:
            # Enter long position
            shares_held = int(balance * 0.8 / price)  # Use 80% of balance
            entry_price = price
            trade_count += 1
        elif action == 0 and shares_held > 0:
            # Exit position
            exit_value = shares_held * price
            balance = balance - (shares_held * entry_price) + exit_value
            shares_held = 0
            trade_count += 1
        
        # Update unrealized value
        if shares_held > 0:
            current_value = balance + (shares_held * price)
        else:
            current_value = balance
        
        peak_balance = max(peak_balance, current_value)
    
    # Close any remaining position
    if shares_held > 0:
        final_price = signals_list[-1]["price"]
        balance = balance - (shares_held * entry_price) + (shares_held * final_price)
    
    total_return_pct = (balance - initial_balance) / initial_balance * 100
    max_dd_pct = (peak_balance - balance) / peak_balance * 100 if peak_balance > 0 else 0.0
    
    return total_return_pct, max_dd_pct, balance, trade_count

def get_leaderboard_metrics(symbol: str, leaderboard_path):
    """Extract aggregate metrics for a symbol from leaderboard."""
    leaderboard = pd.read_csv(leaderboard_path)
    symbol_data = leaderboard[leaderboard["ticker"].str.upper() == symbol.upper()]
    
    if len(symbol_data) == 0:
        return {}
    
    metrics = {
        "model_count": len(symbol_data),
        "avg_sharpe": float(symbol_data["test_sharpe_ratio"].mean()),
        "max_sharpe": float(symbol_data["test_sharpe_ratio"].max()),
    }
    
    # Conditionally add metrics if columns exist
    if "test_actionable_rate" in symbol_data.columns:
        metrics["avg_test_accuracy"] = float(symbol_data["test_actionable_rate"].mean())
    elif "test_accuracy" in symbol_data.columns:
        metrics["avg_test_accuracy"] = float(symbol_data["test_accuracy"].mean())
    
    if "test_win_rate" in symbol_data.columns:
        metrics["avg_win_rate"] = float(symbol_data["test_win_rate"].mean())
    
    if "test_total_return_pct" in symbol_data.columns:
        metrics["avg_return"] = float(symbol_data["test_total_return_pct"].mean())
    
    return metrics

def export_signals(symbol: str, interval: str = "1d", top_n: int = 5):
    print(f"--- Exporting signals for {symbol} ({interval}) ---")
    
    # 1. Initialize Ensemble
    leaderboard_path = get_abs_path("data/experiment_leaderboard.csv")
    if not leaderboard_path.exists():
        print(f"Leaderboard not found at {leaderboard_path}")
        return

    ensemble = SparseEnsemble(str(leaderboard_path))
    
    # Filter for the symbol (ticker) in the leaderboard
    ensemble.active_seeds_df = ensemble.active_seeds_df[ensemble.active_seeds_df["ticker"].str.upper() == symbol.upper()]
    
    if len(ensemble.active_seeds_df) == 0:
        print(f"No models found for {symbol} in leaderboard.")
        return
        
    # Pick the best model's configuration to ensure compatibility
    best_config = ensemble.active_seeds_df.iloc[0]
    target_include_news = int(best_config.get("include_news", 0))
    target_stationary = int(best_config.get("use_stationary_features", 0))
    
    print(f"Target Config for {symbol}: include_news={target_include_news}, stationary={target_stationary}")
    
    # Filter for compatible seeds
    ensemble.active_seeds_df = ensemble.active_seeds_df[
        (ensemble.active_seeds_df["include_news"] == target_include_news) &
        (ensemble.active_seeds_df["use_stationary_features"] == target_stationary)
    ]
    
    print(f"Found {len(ensemble.active_seeds_df)} compatible seeds for {symbol}.")
    num_loaded = ensemble.load_top_n_models(n=top_n)
    
    if num_loaded == 0:
        print(f"Failed to load any models for {symbol}")
        return

    # 2. Probe all models for observation shapes (they may differ!)
    obs_shapes = []
    for seed, model in ensemble.models.items():
        obs_shapes.append(model.observation_space.shape[0])
    
    if not obs_shapes:
        print(f"No models loaded for {symbol}")
        return
    
    # Use the maximum observed shape - all observations will be padded/trimmed to this
    expected_obs_shape = max(obs_shapes)
    print(f"Ensemble models expect obs shapes: {obs_shapes}, using max: {expected_obs_shape}")

    # 3. Fetch Data
    # Match the model's training configuration
    # Force stationary features if model expects a large observation space
    need_stationary = bool(target_stationary) or (expected_obs_shape > 10)
    
    df = get_tech_training_data(
        ticker_preset=symbol.lower(),
        interval=interval,
        include_news=bool(target_include_news),
        use_stationary_features=need_stationary,
        refresh=False
    )
    
    # 4. Initialize Env and find matching feature set
    # State components: balance (1) + shares_held (1) + [current_weight, unrealized_pnl, time_in_position] (3)
    state_count = 5  # with include_position_in_observation=True
    market_plus_news_count = expected_obs_shape - state_count
    print(f"Targeting {market_plus_news_count} market+news features.")

    # Determine potential market features
    potential_market_cols = [
        "LogReturn", "VolLogDiff", "RelRange", "RelOpen", "RelMACD", "RSI_Centered",
        "RelATR", "BB_Width", "BB_Upper_Dist", "BB_Lower_Dist", "SMA_Trend",
        "RelVWAP", "MACD_Signal_Rel", "MACD_Hist_Rel"
    ]
    
    # Fallback to OHLCV if stationary columns not found
    if not any(c in df.columns for c in potential_market_cols):
        potential_market_cols = ["Open", "High", "Low", "Close", "Volume"]

    available_market_cols = [col for col in potential_market_cols if col in df.columns]
    
    # Determine news features
    potential_news_cols = [
        "NewsCount", "SentimentMean", "SentimentStd", "SentimentMin", "SentimentMax",
        "SentimentConfidenceMean", "SentimentGeminiShare", "SentimentOllamaShare"
    ]
    available_news_cols = [col for col in potential_news_cols if col in df.columns]
    
    # Calculate total available features
    total_available = len(available_market_cols) + len(available_news_cols)
    
    if total_available < market_plus_news_count:
        print(f"WARNING: Only {total_available} features available, but need {market_plus_news_count}. Padding with zeros.")
        # Use what we have and pad with zeros during inference
        selected_market_cols = available_market_cols
        selected_news_cols = available_news_cols
    else:
        # Select enough features to match expected shape
        # Prefer market columns first, then add news if needed
        selected_market_cols = available_market_cols[:min(len(available_market_cols), market_plus_news_count)]
        remaining = market_plus_news_count - len(selected_market_cols)
        selected_news_cols = available_news_cols[:remaining] if remaining > 0 else []
    
    print(f"Using {len(selected_market_cols)} market + {len(selected_news_cols)} news features")

    # Initialize env with correct feature columns
    env = TradingEnv(
        df,
        execution_mode="next_bar",
        include_position_in_observation=True,
        market_feature_columns=selected_market_cols,
    )
    
    current_obs_shape = env.observation_space.shape[0]
    if current_obs_shape != expected_obs_shape:
        print(f"Shape mismatch: Env has {current_obs_shape}, Model wants {expected_obs_shape}")
        print(f"Forcing observation space to {expected_obs_shape}")
        # Force the observation space to match model expectation
        env.observation_space = type(env.observation_space)(
            low=-np.inf, high=np.inf, shape=(expected_obs_shape,), dtype=np.float32
        )
    else:
        print(f"Observation shape matches: {current_obs_shape}")

    obs, _ = env.reset()
    
    # Pad observation if needed to match model expectation
    if obs.shape[0] < expected_obs_shape:
        padding = np.zeros(expected_obs_shape - obs.shape[0], dtype=np.float32)
        obs = np.concatenate([obs, padding])
    elif obs.shape[0] > expected_obs_shape:
        obs = obs[:expected_obs_shape]
    
    signals = []
    
    # 4. Run Inference
    print(f"Running inference over {len(df)} bars...")
    for i in range(len(df)):
        # method="voting" is standard ensemble approach
        action, confidence = ensemble.ensemble_predict(obs, method="voting")
        
        # Record signal
        current_date = df.loc[i, "Date"]
        
        signals.append({
            "date": int(current_date.timestamp()) if isinstance(current_date, pd.Timestamp) else int(pd.to_datetime(current_date).timestamp()),
            "price": float(df.loc[i, "RawClose"]) if "RawClose" in df.columns else float(df.loc[i, "Close"]),
            "action": int(action),
            "confidence": float(confidence)
        })
        
        # Step env to maintain state (position, time in position, etc.)
        step_obs, _, terminated, truncated, _ = env.step(action)
        
        # Apply same padding/truncation to step observation
        if step_obs.shape[0] < expected_obs_shape:
            padding = np.zeros(expected_obs_shape - step_obs.shape[0], dtype=np.float32)
            obs = np.concatenate([step_obs, padding])
        elif step_obs.shape[0] > expected_obs_shape:
            obs = step_obs[:expected_obs_shape]
        else:
            obs = step_obs
        
        if terminated or truncated:
            break
            
    # 5. Calculate P&L and fetch leaderboard metrics
    simulated_return, max_dd, final_balance, trade_count = calculate_simulated_pnl(signals)
    leaderboard_metrics = get_leaderboard_metrics(symbol, str(leaderboard_path))
    
    # 6. Save to JSON
    out_dir = get_abs_path("data/dashboard_signals")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = out_dir / f"{symbol.lower()}_signals.json"
    
    payload = {
        "symbol": symbol.upper(),
        "interval": interval,
        "last_updated_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_count": num_loaded,
        "ensemble_metrics": {
            "simulated_return_pct": round(simulated_return, 2),
            "simulated_max_dd_pct": round(max_dd, 2),
            "simulated_final_balance": round(final_balance, 2),
            "simulated_trade_count": int(trade_count),
        },
        "leaderboard_aggregate": leaderboard_metrics,
        "signals": signals
    }
    
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
        
    print(f"SUCCESS: Exported {len(signals)} signals to {out_path}")
    print(f"  Simulated P&L: {simulated_return:+.2f}% | Max DD: {max_dd:.2f}% | Trades: {trade_count}")
    print(f"  Leaderboard: {leaderboard_metrics.get('model_count', 0)} models, Avg Sharpe: {leaderboard_metrics.get('avg_sharpe', 0):.2f}")

if __name__ == "__main__":
    # target symbols
    target_symbols = ["NVDA", "AMD"]
    for sym in target_symbols:
        try:
            export_signals(sym)
        except Exception as e:
            print(f"CRITICAL ERROR exporting {sym}: {e}")
            import traceback
            traceback.print_exc()

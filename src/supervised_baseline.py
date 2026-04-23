"""
Stage 1 Supervised Baseline Training

Prove signal exists without RL by training supervised models to predict next-step returns
and converting predictions to simple trading policies.

Usage:
    python src/supervised_baseline.py --ticker AAPL --horizon 1 --model-type rf --output-dir results/

This will:
1. Load data for specified ticker
2. Split into walk-forward train/val/test
3. Train supervised model on train set
4. Evaluate on val and test sets
5. Log results to leaderboard
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market_data import get_tech_training_data
from src.baseline_agents import (
    SupervisedRegressionPolicy,
    SupervisedClassificationPolicy,
    RandomPolicy,
    BuyHoldPolicy,
    FlatPolicy
)


def train_supervised_baseline(
    ticker: str,
    horizon: int = 1,
    model_type: str = 'linear',
    use_stationary: bool = True,
    use_news: bool = False,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    output_dir: str = 'results/',
    seed: int = 42,
    output_name: str | None = None,
    target_mode: str = 'raw',
) -> Dict:
    """
    Train and evaluate a supervised baseline for Stage 1.
    
    Args:
        ticker: Stock ticker (e.g., 'AAPL')
        horizon: Prediction horizon in days
        model_type: 'linear', 'rf', 'xgb', 'mlp'
        use_stationary: Use stationary features
        use_news: Include news sentiment features
        train_ratio: Fraction of data for training
        val_ratio: Fraction of data for validation
        output_dir: Directory to save results
        seed: Random seed
        target_mode: 'raw', 'vol_norm', or 'vol_norm_clipped'
    
    Returns:
        Results dictionary with metrics and model info
    """
    np.random.seed(seed)
    
    print(f"\n{'='*70}")
    print(f"Stage 1 Supervised Baseline: {ticker}")
    print(f"{'='*70}")
    print(f"Horizon: {horizon} days")
    print(f"Model: {model_type}")
    print(f"Target mode: {target_mode}")
    print(f"Features: stationary={use_stationary}, news={use_news}")
    print(f"Train/Val/Test: {train_ratio:.0%} / {val_ratio:.0%} / {1-train_ratio-val_ratio:.0%}")

    if train_ratio <= 0 or val_ratio <= 0 or (train_ratio + val_ratio) >= 1.0:
        raise ValueError(f"Invalid split ratios: train_ratio={train_ratio}, val_ratio={val_ratio}. Require train>0, val>0, train+val<1.")
    
    # Step 1: Load data (includes stationary features if use_stationary=True)
    print(f"\n[1/6] Loading data for {ticker}...")
    df_full = get_tech_training_data(
        tickers=[ticker],
        include_news=use_news,
        use_stationary_features=use_stationary
    )
    
    if df_full.empty:
        raise ValueError(f"No data loaded for {ticker}")
    
    print(f"  Loaded {len(df_full)} bars")
    print(f"  Available columns: {list(df_full.columns)}")

    # Use the raw price series for target construction.
    if 'RawClose' in df_full.columns:
        price_series = pd.to_numeric(df_full['RawClose'], errors='coerce')
        price_col = 'RawClose'
    elif 'Close' in df_full.columns:
        price_series = pd.to_numeric(df_full['Close'], errors='coerce')
        price_col = 'Close'
    else:
        raise ValueError(f"No RawClose or Close column found. Available: {list(df_full.columns)}")

    print(f"  Using '{price_col}' for pricing (range: {np.nanmin(price_series):.2f} to {np.nanmax(price_series):.2f})")
    
    # Step 2: Extract features
    print(f"\n[2/6] Extracting features...")
    
    # Identify feature columns (exclude Date, OHLCV, news, RawClose)
    exclude_cols = {'Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'RawClose',
                    'OrigOpen', 'OrigHigh', 'OrigLow', 'OrigClose', 'OrigVolume'}
    
    # Extract feature columns
    feature_cols = [col for col in df_full.columns if col not in exclude_cols]
    
    # Remove news columns if not requested
    if not use_news:
        news_cols = {'NewsCount', 'SentimentMean', 'SentimentStd', 'SentimentMin', 
                     'SentimentMax', 'SentimentConfidenceMean', 'SentimentGeminiShare', 
                     'SentimentOllamaShare'}
        feature_cols = [col for col in feature_cols if col not in news_cols]
    
    X = df_full[feature_cols].values
    
    print(f"  Using {len(feature_cols)} features: {feature_cols[:8]}{'...' if len(feature_cols) > 8 else ''}")
    print(f"  Feature matrix shape: {X.shape}")
    
    # Step 3: Create supervised targets
    print(f"\n[3/6] Creating supervised targets...")

    if price_series.isna().all():
        raise ValueError("No valid price data found in the chosen price column")

    # Predict the forward log return over the requested horizon.
    # For horizon=1 this is log(P[t+1] / P[t]).
    future_prices = price_series.shift(-horizon)
    raw_targets = np.log(future_prices / price_series).replace([np.inf, -np.inf], np.nan)

    if target_mode == 'raw':
        targets = raw_targets
    else:
        rolling_vol = raw_targets.rolling(20, min_periods=20).std().shift(1)
        targets = raw_targets / (rolling_vol + 1e-8)
        if target_mode == 'vol_norm_clipped':
            targets = targets.clip(-3.0, 3.0)
        targets = targets.replace([np.inf, -np.inf], np.nan)

    valid_price_mask = price_series.notna() & (price_series > 0)
    valid_future_mask = future_prices.notna() & (future_prices > 0)
    valid_targets_mask = valid_price_mask & valid_future_mask & targets.notna()

    n_valid = int(valid_targets_mask.sum())

    print(f"  Valid price samples: {int(valid_price_mask.sum())} / {len(df_full)}")
    print(f"  Valid target samples: {n_valid} / {len(df_full)}")

    if n_valid < len(df_full) * 0.05:
        print(f"  WARNING: Very few valid targets ({n_valid}), may indicate data quality issues")

    if n_valid > 0:
        print(f"  Target mean: {targets.mean(skipna=True):.8f}, std: {targets.std(skipna=True):.8f}")
    
    # Step 4: Split data (walk-forward preserving date order)
    print(f"\n[4/6] Splitting data (walk-forward)...")
    
    # df_full is already sorted by Date (from get_tech_training_data)
    n = len(df_full)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)
    
    # Create masks for train/val/test split
    train_mask = np.arange(n) < train_end
    val_mask = (np.arange(n) >= train_end) & (np.arange(n) < val_end)
    test_mask = np.arange(n) >= val_end
    
    target_values = targets.to_numpy()
    X_train, y_train = X[train_mask], target_values[train_mask]
    X_val, y_val = X[val_mask], target_values[val_mask]
    X_test, y_test = X[test_mask], target_values[test_mask]
    
    # Remove NaN targets and NaN features
    train_feature_valid = np.all(np.isfinite(X_train), axis=1)
    train_target_valid = np.isfinite(y_train)
    train_valid = train_feature_valid & train_target_valid
    
    val_feature_valid = np.all(np.isfinite(X_val), axis=1)
    val_target_valid = np.isfinite(y_val)
    val_valid = val_feature_valid & val_target_valid
    
    test_feature_valid = np.all(np.isfinite(X_test), axis=1)
    test_target_valid = np.isfinite(y_test)
    test_valid = test_feature_valid & test_target_valid
    
    X_train, y_train = X_train[train_valid], y_train[train_valid]
    X_val, y_val = X_val[val_valid], y_val[val_valid]
    X_test, y_test = X_test[test_valid], y_test[test_valid]
    
    print(f"  Train: {len(X_train)} samples")
    print(f"  Val: {len(X_val)} samples")
    print(f"  Test: {len(X_test)} samples")
    
    # Step 5: Train model
    print(f"\n[5/6] Training {model_type} model...")
    model = SupervisedRegressionPolicy(model_class=model_type, random_state=seed)
    model.train(X_train, y_train)
    print(f"  Model trained and ready for inference")
    
    # Step 6: Evaluate on val and test
    print(f"\n[6/6] Evaluating on validation and test sets...")
    
    results = {
        'ticker': ticker,
        'horizon': horizon,
        'model_type': model_type,
        'target_mode': target_mode,
        'use_stationary': use_stationary,
        'use_news': use_news,
        'n_features': X.shape[1],
        'feature_names': feature_cols,
        'train_ratio': float(train_ratio),
        'val_ratio': float(val_ratio),
        'test_ratio': float(1 - train_ratio - val_ratio),
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'test_samples': len(X_test),
        'seed': seed,
        'timestamp': datetime.now().isoformat(),
    }
    
    # Compute regression metrics for val
    y_val_pred = model.model.predict(X_val)
    val_mse = np.mean((y_val - y_val_pred) ** 2)
    val_mae = np.mean(np.abs(y_val - y_val_pred))
    val_r2 = 1 - np.sum((y_val - y_val_pred) ** 2) / np.sum((y_val - np.mean(y_val)) ** 2)
    
    results['val_mse'] = float(val_mse)
    results['val_mae'] = float(val_mae)
    results['val_r2'] = float(val_r2)
    
    print(f"  Val MSE: {val_mse:.6f}")
    print(f"  Val MAE: {val_mae:.6f}")
    print(f"  Val R²: {val_r2:.6f}")
    
    # Compute regression metrics for test
    y_test_pred = model.model.predict(X_test)
    test_mse = np.mean((y_test - y_test_pred) ** 2)
    test_mae = np.mean(np.abs(y_test - y_test_pred))
    test_r2 = 1 - np.sum((y_test - y_test_pred) ** 2) / np.sum((y_test - np.mean(y_test)) ** 2)
    
    results['test_mse'] = float(test_mse)
    results['test_mae'] = float(test_mae)
    results['test_r2'] = float(test_r2)
    
    print(f"  Test MSE: {test_mse:.6f}")
    print(f"  Test MAE: {test_mae:.6f}")
    print(f"  Test R²: {test_r2:.6f}")
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    
    if output_name:
        results_file = os.path.join(output_dir, output_name)
    else:
        results_file = os.path.join(output_dir, f'stage1_baseline_{ticker}_{model_type}_{horizon}h.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {results_file}")
    print(f"{'='*70}\n")
    
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Stage 1 Supervised Baseline Training'
    )
    parser.add_argument('--ticker', type=str, default='AAPL',
                       help='Stock ticker (default: AAPL)')
    parser.add_argument('--horizon', type=int, default=1,
                       help='Prediction horizon in days (default: 1)')
    parser.add_argument('--model-type', type=str, default='linear',
                       choices=['linear', 'rf', 'xgb', 'mlp'],
                       help='Model type (default: linear)')
    parser.add_argument('--use-news', action='store_true',
                       help='Include news sentiment features')
    parser.add_argument('--train-ratio', type=float, default=0.70,
                       help='Train split ratio (default: 0.70)')
    parser.add_argument('--val-ratio', type=float, default=0.15,
                       help='Validation split ratio (default: 0.15)')
    parser.add_argument('--output-dir', type=str, default='results/stage1/',
                       help='Output directory for results')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--target-mode', type=str, default='raw',
                       choices=['raw', 'vol_norm', 'vol_norm_clipped'],
                       help='Target construction mode (default: raw)')
    parser.add_argument('--output-name', type=str, default='',
                       help='Optional output filename override (e.g., stage1_baseline_AAPL_linear_1h_seed7.json)')
    
    args = parser.parse_args()
    
    results = train_supervised_baseline(
        ticker=args.ticker,
        horizon=args.horizon,
        model_type=args.model_type,
        use_news=args.use_news,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        output_dir=args.output_dir,
        seed=args.seed,
        output_name=(args.output_name.strip() or None),
        target_mode=args.target_mode,
    )
    
    print(f"Summary: {results}")

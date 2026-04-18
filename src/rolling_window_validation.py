"""
Rolling-window walk-forward validation for Stage 1 baseline signal robustness.

Tests whether supervised baselines produce consistent returns across multiple
market regimes by training on sliding windows and measuring stability.

This validates signal robustness before RL escalation.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

ROOT_DIR = Path(__file__).resolve().parents[1]


def create_rolling_windows(
    df: pd.DataFrame,
    window_config: Dict[str, int]
) -> List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]]:
    """
    Create rolling windows for walk-forward validation.
    
    Args:
        df: Full time-series data (sorted by date)
        window_config: Dict with keys:
            - train_size: fraction [0-1]
            - val_size: fraction [0-1]
            - test_size: fraction [0-1]
            - slide_pct: percentage of window to slide forward
    
    Returns:
        List of (train, val, test, metadata) tuples for each window
    """
    n = len(df)
    total_size = (window_config["train_size"] + 
                  window_config["val_size"] + 
                  window_config["test_size"])
    
    window_n = int(n * total_size)
    slide_n = int(window_n * window_config["slide_pct"])
    
    windows = []
    start_idx = 0
    window_num = 0
    
    while start_idx + window_n <= n:
        end_idx = start_idx + window_n
        
        # Split within window
        train_end = start_idx + int(window_n * window_config["train_size"])
        val_end = train_end + int(window_n * window_config["val_size"])
        
        train = df.iloc[start_idx:train_end].copy()
        val = df.iloc[train_end:val_end].copy()
        test = df.iloc[val_end:end_idx].copy()
        
        metadata = {
            "window_num": window_num,
            "train_start": train["Date"].min(),
            "train_end": train["Date"].max(),
            "val_start": val["Date"].min(),
            "val_end": val["Date"].max(),
            "test_start": test["Date"].min(),
            "test_end": test["Date"].max(),
            "train_size": len(train),
            "val_size": len(val),
            "test_size": len(test),
        }
        
        windows.append((train, val, test, metadata))
        
        start_idx += slide_n
        window_num += 1
    
    return windows


def train_baseline_on_window(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    model_type: str = "linear",
    seed: int = 42,
) -> Dict:
    """
    Train a supervised baseline on a single window.
    
    Returns:
        Dict with train/val/test metrics and predictions
    """
    np.random.seed(seed)
    
    # Prepare features
    feature_cols = [
        col for col in train.columns
        if col not in ["Date", "LogReturn", "Target", "OrigClose", "OrigOpen", "OrigHigh", "OrigLow"]
    ]
    
    # Remove NaN rows
    train_clean = train.dropna(subset=feature_cols + ["LogReturn"])
    val_clean = val.dropna(subset=feature_cols + ["LogReturn"])
    test_clean = test.dropna(subset=feature_cols + ["LogReturn"])
    
    X_train = train_clean[feature_cols].values
    y_train = train_clean["LogReturn"].shift(-1).dropna().values
    X_train = X_train[:-1]  # Align with shifted target
    
    X_val = val_clean[feature_cols].values
    y_val = val_clean["LogReturn"].shift(-1).dropna().values
    X_val = X_val[:-1]
    
    X_test = test_clean[feature_cols].values
    y_test = test_clean["LogReturn"].shift(-1).dropna().values
    X_test = X_test[:-1]
    
    # Train model
    if model_type == "linear":
        model = LinearRegression()
    elif model_type == "rf":
        model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=seed)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")
    
    model.fit(X_train, y_train)
    
    # Evaluate
    def compute_metrics(y_true, y_pred):
        mse = np.mean((y_true - y_pred) ** 2)
        mae = np.mean(np.abs(y_true - y_pred))
        
        # R²
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {"mse": mse, "mae": mae, "r2": r2}
    
    train_preds = model.predict(X_train)
    val_preds = model.predict(X_val)
    test_preds = model.predict(X_test)
    
    train_metrics = compute_metrics(y_train, train_preds)
    val_metrics = compute_metrics(y_val, val_preds)
    test_metrics = compute_metrics(y_test, test_preds)
    
    # Trading simulation
    def simulate_trading(y_pred, y_true):
        # Simple threshold-based policy
        threshold = np.median(y_pred)
        signals = (y_pred > threshold).astype(int) * 2 - 1  # -1, 0, 1
        
        returns = signals * y_true
        total_return = np.sum(returns)
        win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0
        
        return {
            "total_return": total_return,
            "win_rate": win_rate,
            "avg_return": np.mean(returns),
            "trade_count": np.sum(signals != 0),
        }
    
    train_trading = simulate_trading(train_preds, y_train)
    val_trading = simulate_trading(val_preds, y_val)
    test_trading = simulate_trading(test_preds, y_test)
    
    return {
        "model_type": model_type,
        "train": {**train_metrics, **train_trading},
        "val": {**val_metrics, **val_trading},
        "test": {**test_metrics, **test_trading},
        "sample_counts": {
            "train": len(y_train),
            "val": len(y_val),
            "test": len(y_test),
        }
    }


def run_rolling_window_validation(
    window_config: Dict[str, float] = None,
    model_types: List[str] = None,
    output_dir: Path = None,
) -> Dict:
    """
    Run complete rolling-window validation workflow.
    
    Args:
        window_config: Window configuration (train_size, val_size, test_size, slide_pct)
        model_types: List of model types to test
        output_dir: Directory for results
    
    Returns:
        Comprehensive results dict
    """
    if window_config is None:
        window_config = {
            "train_size": 0.20,  # 20% of full dataset per window
            "val_size": 0.20,    # Creates windows that are 60% total, allowing sliding
            "test_size": 0.20,
            "slide_pct": 0.33,   # Slide by 33% of window (creates 3 windows from 2070 rows)
        }
    
    if model_types is None:
        model_types = ["linear", "rf"]
    
    if output_dir is None:
        output_dir = ROOT_DIR / "results" / "stage1_rolling_window"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Loading data from stationary CSV...")
    # Load pre-computed stationary data
    data_path = ROOT_DIR / "data" / "tech_training_data_stationary.csv"
    df = pd.read_csv(data_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values("Date").reset_index(drop=True)
    
    logger.info(f"Data shape: {df.shape} | Date range: {df['Date'].min()} to {df['Date'].max()}")
    
    # Create windows
    logger.info(f"Creating rolling windows with config: {window_config}")
    windows = create_rolling_windows(df, window_config)
    logger.info(f"Created {len(windows)} windows")
    
    # Train models on each window
    all_results = {
        "generated_at": datetime.utcnow().isoformat() + "+00:00",
        "window_config": window_config,
        "num_windows": len(windows),
        "windows": []
    }
    
    for train, val, test, metadata in windows:
        logger.info(f"\nWindow {metadata['window_num']}: "
                   f"{metadata['test_start'].date()} - {metadata['test_end'].date()}")
        
        window_results = {
            "metadata": metadata,
            "models": {}
        }
        
        for model_type in model_types:
            logger.info(f"  Training {model_type}...")
            metrics = train_baseline_on_window(train, val, test, model_type=model_type)
            window_results["models"][model_type] = metrics
        
        all_results["windows"].append(window_results)
    
    # Aggregate statistics across windows
    logger.info("\nAggregating statistics...")
    aggregate = compute_aggregate_statistics(all_results)
    all_results["aggregate"] = aggregate
    
    # Save full results
    results_path = output_dir / f"rolling_window_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, "w", encoding="utf-8") as f:
        # Convert datetime objects for JSON serialization
        json_results = json.loads(json.dumps(all_results, default=str))
        json.dump(json_results, f, indent=2)
    
    logger.info(f"✓ Full results saved: {results_path}")
    
    # Save summary report
    report_path = output_dir / f"rolling_window_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    generate_report(all_results, report_path)
    logger.info(f"✓ Report saved: {report_path}")
    
    return all_results


def compute_aggregate_statistics(results: Dict) -> Dict:
    """
    Compute cross-window statistics for signal stability analysis.
    """
    windows = results["windows"]
    
    # Extract metrics across windows
    model_types = list(windows[0]["models"].keys())
    metrics_by_model = {model: {"test_r2": [], "test_return": [], "test_win_rate": []}
                       for model in model_types}
    
    for window in windows:
        for model_type in model_types:
            metrics = window["models"][model_type]
            metrics_by_model[model_type]["test_r2"].append(metrics["test"]["r2"])
            metrics_by_model[model_type]["test_return"].append(metrics["test"]["total_return"])
            metrics_by_model[model_type]["test_win_rate"].append(metrics["test"]["win_rate"])
    
    # Compute statistics
    aggregate = {}
    for model_type in model_types:
        r2_values = metrics_by_model[model_type]["test_r2"]
        return_values = metrics_by_model[model_type]["test_return"]
        win_rate_values = metrics_by_model[model_type]["test_win_rate"]
        
        aggregate[model_type] = {
            "test_r2": {
                "mean": float(np.mean(r2_values)),
                "std": float(np.std(r2_values)),
                "min": float(np.min(r2_values)),
                "max": float(np.max(r2_values)),
                "cv": float(np.std(r2_values) / abs(np.mean(r2_values))) if np.mean(r2_values) != 0 else float('inf'),
            },
            "test_return": {
                "mean": float(np.mean(return_values)),
                "std": float(np.std(return_values)),
                "min": float(np.min(return_values)),
                "max": float(np.max(return_values)),
                "cv": float(np.std(return_values) / abs(np.mean(return_values))) if np.mean(return_values) != 0 else float('inf'),
            },
            "test_win_rate": {
                "mean": float(np.mean(win_rate_values)),
                "std": float(np.std(win_rate_values)),
                "min": float(np.min(win_rate_values)),
                "max": float(np.max(win_rate_values)),
            }
        }
    
    return aggregate


def generate_report(results: Dict, report_path: Path):
    """
    Generate markdown report summarizing rolling-window validation.
    """
    windows = results["windows"]
    aggregate = results["aggregate"]
    
    report = f"""# Rolling-Window Validation Report

Generated at: {results['generated_at']}

## Configuration

- Train/Val/Test split: {results['window_config']['train_size']:.0%}/{results['window_config']['val_size']:.0%}/{results['window_config']['test_size']:.0%}
- Window slide: {results['window_config']['slide_pct']:.0%}
- Number of windows: {len(windows)}

---

## Results by Window

"""
    
    for window in windows:
        meta = window["metadata"]
        report += f"\n### Window {meta['window_num']} ({meta['test_start'].date()} - {meta['test_end'].date()})\n\n"
        
        report += "| Model | Test R² | Test Return | Win Rate |\n"
        report += "|-------|---------|-------------|----------|\n"
        
        for model_type, metrics in window["models"].items():
            test_r2 = metrics["test"]["r2"]
            test_ret = metrics["test"]["total_return"]
            win_rate = metrics["test"]["win_rate"]
            
            report += f"| {model_type} | {test_r2:+.4f} | {test_ret:+.4f} | {win_rate:.1%} |\n"
    
    report += "\n---\n\n## Aggregate Statistics\n\n"
    
    for model_type, stats in aggregate.items():
        report += f"### {model_type.upper()}\n\n"
        
        report += "**Test R² Stability**\n"
        report += f"- Mean: {stats['test_r2']['mean']:+.4f}\n"
        report += f"- Std: {stats['test_r2']['std']:.4f}\n"
        report += f"- CV: {stats['test_r2']['cv']:.3f}\n"
        report += f"- Range: [{stats['test_r2']['min']:+.4f}, {stats['test_r2']['max']:+.4f}]\n\n"
        
        report += "**Test Return Stability**\n"
        report += f"- Mean: {stats['test_return']['mean']:+.4f}\n"
        report += f"- Std: {stats['test_return']['std']:.4f}\n"
        report += f"- CV: {stats['test_return']['cv']:.3f}\n"
        report += f"- Range: [{stats['test_return']['min']:+.4f}, {stats['test_return']['max']:+.4f}]\n\n"
        
        report += "**Win Rate**\n"
        report += f"- Mean: {stats['test_win_rate']['mean']:.1%}\n"
        report += f"- Std: {stats['test_win_rate']['std']:.3%}\n\n"
    
    report += """
---

## Interpretation

**Stability Criteria**:
- **Good**: CV < 0.5 (consistent across windows)
- **Acceptable**: CV < 1.0 (moderate variation)
- **Poor**: CV > 1.0 or negative mean R² (unstable or no signal)

**Decision**:
- If R² mean > 0.01 AND CV < 1.0 → Signal robust, ready for RL escalation
- If R² mean ≤ 0.01 OR CV > 1.0 → Signal not regime-stable, need feature engineering
- If win_rate near 50% across windows → Trading success may be random luck
"""
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    import sys
    
    # Default config
    window_config = {
        "train_size": 0.60,
        "val_size": 0.20,
        "test_size": 0.20,
        "slide_pct": 0.25,
    }
    
    results = run_rolling_window_validation(
        window_config=window_config,
        model_types=["linear", "rf"],
        output_dir=ROOT_DIR / "results" / "stage1_rolling_window"
    )
    
    print("\n✓ Rolling-window validation complete")
    print(f"Aggregate stats: {json.dumps(results['aggregate'], indent=2)}")

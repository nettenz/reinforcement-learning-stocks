"""
Exp 9 — Walk-forward backtest validation for the SparseEnsemble.

For each ticker, runs the top-N seeds individually and as an ensemble over the fixed test split.
Compares ensemble accuracy against individual seed accuracy to confirm the ensemble does not degrade.

Gate criteria:
  G1. Ensemble actionable accuracy >= min(individual top-N seed accuracies) - 0.5% tolerance
  G2. Ensemble agreement rate >= 60%  (confidence >= 0.67 on >= 60% of steps)
  G3. High-confidence (1.0) actions >= 20% of total actions
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from stable_baselines3 import PPO, SAC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

warnings.filterwarnings("ignore")

from src.trading_env import TradingEnv
from src.ensemble import SparseEnsemble
from src.trading_agent import EnsembleAgent

# Default settings for well-known tickers
DEFAULT_TICKER_CONFIG = {
    "nvda": {
        "parquet":     ROOT / "data" / "tech_training_data_nvda_stationary.parquet",
        "use_stationary_features": True,
    },
    "amd": {
        "parquet":     ROOT / "data" / "tech_training_data_amd_stationary.parquet",
        "use_stationary_features": True,
    },
    "aapl": {
        "parquet":     ROOT / "data" / "tech_training_data_aapl_stationary.parquet",
        "use_stationary_features": True,
    },
}

STATIONARY_COLS = [
    'LogReturn', 'VolLogDiff', 'RelRange', 'RelOpen', 'RelMACD',
    'RSI_Centered', 'RelATR', 'BB_Width', 'BB_Upper_Dist', 'BB_Lower_Dist',
    'SMA_Trend', 'RelVWAP', 'MACD_Signal_Rel', 'MACD_Hist_Rel'
]

ENV_PARAMS = {
    "initial_balance":       1000.0,
    "transaction_cost_rate": 0.001,
    "trade_penalty":         0.05,
    "execution_mode":        "next_bar",
    "spread_bps":            1.0,
    "slippage_bps":          1.0,
    "reward_mode":           "sparse",
    "rolling_reward_window": 60,
    "binary_actions":        True,
    "long_only":             True,
    "include_position_in_observation": True,
    "max_episode_steps":     0,   # full test period, no episode boundaries
    "random_start":          False,
    "max_weight_delta_per_step": 0.10,
}

GATE_G2_AGREEMENT_RATE = 0.60
GATE_G3_HIGH_CONF_RATE = 0.20

def _test_split(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    # Default split matches training: 70/15/15
    val_end = int(n * (0.70 + 0.15))
    return df.iloc[val_end:].reset_index(drop=True)

def _run_single_seed(model, test_df: pd.DataFrame, env_params: dict) -> dict:
    """Run a single model over the full test split. Returns accuracy metrics."""
    env = TradingEnv(test_df.copy(), **env_params)
    obs, _ = env.reset()

    buy_correct = 0
    buy_total   = 0
    done        = False

    while not done:
        raw_action, _ = model.predict(obs, deterministic=True)
        
        # Algorithm-agnostic binary action conversion
        if isinstance(model, PPO):
            binary_action = int(raw_action.item() if isinstance(raw_action, np.ndarray) else raw_action)
        else:
            # SAC / Continuous
            binary_action = 1 if float(raw_action[0]) > 0.0 else 0

        # Note: we pass raw_action to step() as TradingEnv now handles both discrete and continuous
        next_obs, _, terminated, truncated, info = env.step(raw_action)
        done = terminated or truncated

        if binary_action == 1:
            realized = info.get("realized_return", 0.0)
            buy_total += 1
            if realized > 0:
                buy_correct += 1

        obs = next_obs

    accuracy = buy_correct / buy_total if buy_total > 0 else 0.0
    return {"buy_total": buy_total, "buy_correct": buy_correct, "accuracy": accuracy}

def _run_ensemble(ensemble: SparseEnsemble, agent: EnsembleAgent, test_df: pd.DataFrame, env_params: dict) -> dict:
    """Run ensemble over full test split. Returns accuracy + voting metrics."""
    env = TradingEnv(test_df.copy(), **env_params)

    market_cols = env.market_feature_columns
    news_cols   = env.active_news_columns

    obs_env, _ = env.reset()
    agent.reset()

    buy_correct = 0
    buy_total   = 0
    done        = False

    while not done:
        row = test_df.iloc[env.current_step]

        market_feat = row[market_cols].values.astype(np.float32)
        news_feat   = row[news_cols].values.astype(np.float32) if news_cols else np.array([], dtype=np.float32)

        pm = env.pm
        unrealized_pnl = 0.0
        if pm.entry_price > 0:
            cur_price = max(float(test_df.loc[env.current_step, env.price_column]), 1e-8)
            ratio = cur_price / pm.entry_price
            unrealized_pnl = ratio - 1.0 if pm.shares_held > 0 else 1.0 - ratio

        account_state = np.array([
            pm.balance, pm.shares_held,
            pm.current_weight, unrealized_pnl, float(pm.time_in_position),
        ], dtype=np.float32)

        action, confidence, _ = agent.step(market_feat, news_feat, account_state)

        # Convert discrete action back to environment-compatible value
        # If env is in binary_actions mode, it expects 0/1 or continuous weight
        # We pass 1.0 for buy, 0.0 for hold to be safe across both modes
        raw_for_env = 1.0 if action == 1 else 0.0
        _, _, terminated, truncated, info = env.step(raw_for_env)
        done = terminated or truncated

        if action == 1:
            realized = info.get("realized_return", 0.0)
            buy_total += 1
            if realized > 0:
                buy_correct += 1

    accuracy = buy_correct / buy_total if buy_total > 0 else 0.0
    metrics = agent.get_session_metrics()

    return {
        "buy_total":       buy_total,
        "buy_correct":     buy_correct,
        "accuracy":        accuracy,
        "agreement_rate":  metrics["agreement_rate"],
        "high_conf_rate":  metrics["high_conf_rate"],
        "avg_confidence":  metrics["avg_confidence"],
    }

def run_ticker(ticker: str, config_path: Path, leaderboard_path: Path) -> dict:
    ticker = ticker.lower()
    
    # Load config to get metadata
    with open(config_path) as f:
        full_config = json.load(f)
    
    if ticker not in full_config:
        print(f"  [ERROR] Ticker {ticker} not found in {config_path}")
        return {"ticker": ticker, "gate_pass": False, "error": "missing config"}
        
    ticker_cfg = full_config[ticker]
    top_seeds = ticker_cfg.get("active_seeds", [])
    run_label = ticker_cfg.get("run_label")
    if run_label == "N/A": run_label = None

    # Determine environment params
    ticker_env_params = ENV_PARAMS.copy()
    
    # Try to find parquet file
    parquet_path = ROOT / "data" / f"tech_training_data_{ticker}_stationary.parquet"
    if not parquet_path.exists():
        # Fallback to non-stationary if needed, or default mapping
        if ticker in DEFAULT_TICKER_CONFIG:
            parquet_path = DEFAULT_TICKER_CONFIG[ticker]["parquet"]
    
    if not parquet_path.exists():
        print(f"  [SKIP] No parquet found for {ticker.upper()}: {parquet_path}")
        return {"ticker": ticker, "gate_pass": False, "error": "missing parquet"}

    # Infer stationary columns usage
    if "stationary" in parquet_path.name:
        ticker_env_params["market_feature_columns"] = STATIONARY_COLS
    else:
        ticker_env_params["market_feature_columns"] = None

    print(f"\n{'='*60}")
    print(f"  {ticker.upper()}")
    print(f"{'='*60}")

    df_full = pd.read_parquet(parquet_path)
    test_df = _test_split(df_full)
    print(f"  Test rows: {len(test_df)}  ({test_df['Date'].iloc[0]} to {test_df['Date'].iloc[-1]})")

    # Load ensemble
    ensemble = SparseEnsemble(str(leaderboard_path))
    ensemble.filter_active_seeds(min_test_trades=20)
    ensemble.load_top_n_models(
        n=len(top_seeds),
        seed_filter=top_seeds,
        run_label_filter=run_label,
    )

    agent = EnsembleAgent(ensemble, str(config_path), ticker)

    print(f"  Expected obs shape: {agent.expected_obs_shape}")
    print(f"  Loaded seeds: {list(ensemble.models.keys())}")
    print()

    # Run each seed individually
    seed_results = {}
    for seed, model in ensemble.models.items():
        r = _run_single_seed(model, test_df, ticker_env_params)
        seed_results[seed] = r
        tag = "  CORRECT" if r["accuracy"] >= 0.50 else "  below 50%"
        print(f"  Seed {seed:>3}: buys={r['buy_total']:>4}  accuracy={r['accuracy']:.3f} {tag}")

    if not seed_results:
        print("  No seed results — skipping ensemble gate.")
        return {"ticker": ticker, "gate_pass": False}

    min_individual_acc = min(r["accuracy"] for r in seed_results.values())

    # Run ensemble
    ens_result = _run_ensemble(ensemble, agent, test_df, ticker_env_params)
    print()
    print(f"  Ensemble:   buys={ens_result['buy_total']:>4}  accuracy={ens_result['accuracy']:.3f}"
          f"  agreement={ens_result['agreement_rate']:.2f}  avg_conf={ens_result['avg_confidence']:.2f}")

    # Gate evaluation
    G1_TOLERANCE = 0.005
    g1 = ens_result["accuracy"] >= (min_individual_acc - G1_TOLERANCE)
    g2 = ens_result["agreement_rate"] >= GATE_G2_AGREEMENT_RATE
    g3 = ens_result["high_conf_rate"] >= GATE_G3_HIGH_CONF_RATE

    print()
    print(f"  G1 ensemble_acc >= min_seed_acc-0.5%  ({ens_result['accuracy']:.3f} >= {min_individual_acc - G1_TOLERANCE:.3f}): {'PASS' if g1 else 'FAIL'}")
    print(f"  G2 majority_agreement >= 60%          ({ens_result['agreement_rate']:.2f} >= {GATE_G2_AGREEMENT_RATE}): {'PASS' if g2 else 'FAIL'}")
    print(f"  G3 unanimous_rate >= 20%              ({ens_result['high_conf_rate']:.2f} >= {GATE_G3_HIGH_CONF_RATE}): {'PASS' if g3 else 'FAIL'}")

    gate_pass = g1 and g2 and g3
    print()
    print(f"  {'EXP 9 GATE: PASS' if gate_pass else 'EXP 9 GATE: FAIL'}  ({ticker.upper()})")

    return {
        "ticker":              ticker,
        "test_rows":           len(test_df),
        "seed_results":        seed_results,
        "ensemble_accuracy":   ens_result["accuracy"],
        "min_individual_acc":  min_individual_acc,
        "agreement_rate":      ens_result["agreement_rate"],
        "high_conf_rate":      ens_result["high_conf_rate"],
        "g1":                  g1,
        "g2":                  g2,
        "g3":                  g3,
        "gate_pass":           gate_pass,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Exp 9: Walk-forward ensemble validation")
    parser.add_argument(
        "--ticker", nargs="+",
        help="Tickers to validate (e.g. nvda mu). If not provided, validates all in config.",
    )
    parser.add_argument(
        "--config", type=str, 
        default=str(ROOT / "staging" / "models" / "ensemble_config.json"),
        help="Path to ensemble_config.json"
    )
    parser.add_argument(
        "--leaderboard", type=str,
        default=str(ROOT / "data" / "experiment_leaderboard.csv"),
        help="Path to leaderboard CSV (used for tickers not in foundation)"
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found at {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        cfg = json.load(f)

    tickers_to_run = args.ticker if args.ticker else list(cfg.keys())

    results = []
    for ticker in tickers_to_run:
        # Determine which leaderboard to use. 
        # Foundation tickers have their own leaderboards in the script logic, 
        # but we can try to find them in data/ too.
        lb_path = Path(args.leaderboard)
        # Exception for foundation tickers if they are NOT in the main leaderboard
        if ticker in ["nvda", "aapl", "amd"]:
            found_lb = list(ROOT.glob(f"data/*{ticker}*leaderboard.csv"))
            if found_lb:
                lb_path = found_lb[0]

        r = run_ticker(ticker, config_path, lb_path)
        results.append(r)

    print(f"\n{'='*60}")
    print("  EXP 9 SUMMARY")
    print(f"{'='*60}")
    all_pass = all(r.get("gate_pass", False) for r in results if "error" not in r)
    for r in results:
        if "error" in r:
            status = f"ERROR ({r['error']})"
        else:
            status = "PASS" if r.get("gate_pass") else "FAIL"
        print(f"  {r['ticker'].upper():<6}: {status}")
    print()
    print(f"  Overall: {'ALL PASS — Exp 9 complete, proceed to Exp 10' if all_pass else 'GATES FAILED — review results above'}")

if __name__ == "__main__":
    main()

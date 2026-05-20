import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Insert repository root
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv
from sb3_contrib import MaskablePPO

def main():
    # Load data
    df = get_tech_training_data(
        ticker_preset="amd",
        interval="1d",
        include_news=False,
        refresh=False,
        use_stationary_features=True,
    )
    
    # Split data (same as walk-forward split)
    from src.experiments import _split_walk_forward
    train_df, val_df, test_df = _split_walk_forward(df, train_ratio=0.70, val_ratio=0.15)
    
    print(f"Data split sizes - Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    
    # Env kwargs for amd-masked-ppo-v1-low-friction
    env_kwargs = {
        "transaction_cost_rate": 0.001,
        "trade_penalty": 0.05,
        "execution_mode": "same_bar",
        "spread_bps": 0.0,
        "slippage_bps": 0.0,
        "reward_clip": 1.0,
        "reward_ignore_transaction_cost": True,
        "reward_mode": "sharpe",
        "rolling_reward_window": 100,
        "reward_epsilon": 1e-6,
        "reward_pnl_scale": 0.0,
        "long_only": False,
        "binary_actions": True,
        "min_hold_bars": 3,
        "max_episode_steps": 0,
        "random_start": False,
        "use_cooldown_obs": True,
        "max_weight_delta_per_step": 0.0,
        "reward_return_scale": 1.0,
        "reward_direction_scale": 0.35,
        "reward_hold_penalty_scale": 0.01,
        "reward_drawdown_penalty_scale": 0.1,
        "reward_action_bonus_scale": 0.02,
        "reward_turnover_penalty_scale": 0.0,
    }
    
    # Path to model seed 13 (always search for the latest one in snapshots)
    snapshots_dir = ROOT_DIR / "data" / "experiment_snapshots"
    matches = sorted(list(snapshots_dir.glob("*low-friction_seed13.zip")))
    if matches:
        model_path = matches[-1]
        print(f"Found model file: {model_path}")
    else:
        print("ERROR: Low friction seed 13 model zip not found.")
        sys.exit(1)
    
    model = MaskablePPO.load(model_path)
    print(f"Loaded MaskablePPO model from {model_path}")
    print(f"Model observation space: {model.observation_space}")
    print(f"Model action space: {model.action_space}")
    
    # Initialize validation environment
    env = TradingEnv(val_df, **env_kwargs)
    obs, _ = env.reset()
    
    print("\n--- Starting Deterministic Simulation ---")
    trades_executed = 0
    for step in range(len(val_df) - 1):
        action_masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
        
        # Look at the probability distribution if possible
        obs_tensor, _ = model.policy.obs_to_tensor(obs)
        torch = import_torch()
        with torch.no_grad():
            # get action distribution
            features = model.policy.extract_features(obs_tensor)
            latent_pi, _ = model.policy.mlp_extractor(features)
            distribution = model.policy._get_action_dist_from_latent(latent_pi)
            probs = torch.softmax(distribution.distribution.logits, dim=-1).cpu().detach().numpy()[0]
            
        pre_pos = env.pm.current_weight
        obs, reward, terminated, truncated, info = env.step(action)
        post_pos = env.pm.current_weight
        
        if step < 20 or info["execution_notional"] > 0 or action != 0 or pre_pos != post_pos:
            print(f"Step {step:3d} | Action: {action} | Probs: {probs} | Mask: {action_masks} | PrePos: {pre_pos:.1f} -> PostPos: {post_pos:.1f} | NetWorth: {info['reward_net_worth']:.2f}")
            trades_executed += 1
            
        if terminated or truncated:
            break
            
    print(f"Simulation ended. Total trades printed: {trades_executed}")

def import_torch():
    import torch
    return torch

if __name__ == "__main__":
    main()

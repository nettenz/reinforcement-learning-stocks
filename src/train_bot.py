import argparse
from pathlib import Path
import platform
import sys

import numpy as np
from stable_baselines3 import SAC
from dotenv import load_dotenv

load_dotenv()
from stable_baselines3.common.vec_env import SubprocVecEnv
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv

DATA_PATH = ROOT_DIR / "data" / "tech_training_data.parquet"
MODEL_PATH = ROOT_DIR / "models" / "sac_trading_bot"

def main():
    parser = argparse.ArgumentParser(description="Train an SAC continuous trading bot.")
    parser.add_argument("--reward-mode", default="legacy", choices=["legacy", "sharpe", "sortino"], help="Reward calculation mode.")
    parser.add_argument("--rolling-reward-window", type=int, default=100, help="Window size for rolling rewards.")
    parser.add_argument("--reward-epsilon", type=float, default=1e-6, help="Epsilon for numerical stability in rewards.")
    parser.add_argument("--timesteps", type=int, default=20000, help="Total training timesteps.")
    parser.add_argument("--n-envs", type=int, default=8, help="Number of parallel environments.")
    parser.add_argument("--batch-size", type=int, default=1024, help="Batch size for VRAM allocation.")

    # Prefer CUDA (NVIDIA GPU) first, then MPS (Apple Silicon), then CPU fallback
    if torch.cuda.is_available():
        DEFAULT_DEVICE = "cuda"  # NVIDIA GPU (e.g. RTX 5070 Ti)
    elif torch.backends.mps.is_available():
        DEFAULT_DEVICE = "mps"  # Apple Silicon GPU acceleration
    else:
        DEFAULT_DEVICE = "cpu"  # CPU fallback

    parser.add_argument("--device", default=DEFAULT_DEVICE, help="SAC device (auto, cuda, cpu, mps).")
    args = parser.parse_args()

    # Load normalized Yahoo Finance tech basket data with merged daily news sentiment features
    df = get_tech_training_data(cache_path=DATA_PATH, include_news=True)

    # Create the environment
    env_kwargs = {
        "reward_mode": args.reward_mode,
        "rolling_reward_window": args.rolling_reward_window,
        "reward_epsilon": args.reward_epsilon,
    }
    
    def make_env(data, kwargs):
        def _init():
            return TradingEnv(data, **kwargs)
        return _init

    if args.n_envs > 1:
        env = SubprocVecEnv([make_env(df, env_kwargs) for _ in range(args.n_envs)])
    else:
        env = TradingEnv(df, **env_kwargs)

    # Initialize the RL model (SAC continuous)
    # ent_coef handles exploration mathematically in continuous spaces better than discrete PPO bounds
    model = SAC(
        "MlpPolicy", 
        env, 
        verbose=1, 
        device=args.device, 
        ent_coef="auto", 
        batch_size=args.batch_size,
        buffer_size=max(100000, args.timesteps)
    )

    # Train the model
    print(f"Training Continuous SAC agent (mode={args.reward_mode}, window={args.rolling_reward_window})...")
    model.learn(total_timesteps=args.timesteps)

    # Save the trained model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH.as_posix())
    print(f"Model saved as {MODEL_PATH.name}.zip")

    # Test the model
    # SB3 models expect the observation array directly for .predict()
    # If using VecEnv, .reset() returns just the observation array.
    # If using a regular Gym environment, .reset() returns (obs, info).
    reset_val = env.reset()
    if isinstance(reset_val, tuple) and len(reset_val) == 2:
        obs = reset_val[0]
    else:
        obs = reset_val
        
    for _ in range(10):
        action, _states = model.predict(obs, deterministic=True)
        # Action is returned as a 1D array from SAC [weight]
        
        step_result = env.step(action)
        if len(step_result) == 5:
            obs, reward, terminated, truncated, info = step_result
            done = terminated or truncated
        else:
            obs, reward, done, info = step_result
            
        # Handle VecEnv returning arrays for reward/done etc
        r = reward[0] if isinstance(reward, np.ndarray) else reward
        d = done[0] if isinstance(done, np.ndarray) else done
        
        # Access net_worth: VecEnv requires get_attr
        if hasattr(env, "get_attr"):
            nw = env.get_attr("net_worth")[0]
            # action is (n_envs, action_dim)
            act_val = action[0][0]
        else:
            nw = env.net_worth
            act_val = action[0]
            
        print(f"Action Wgt: {act_val:.2f}, Reward: {r:.2f}, Net Worth: {nw:.2f}")
        
        if np.any(d):
            break

if __name__ == "__main__":
    main()

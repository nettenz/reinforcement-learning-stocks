import argparse
from pathlib import Path
import platform
import sys

from stable_baselines3 import PPO
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv

DATA_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
MODEL_PATH = ROOT_DIR / "models" / "ppo_trading_bot"

def main():
    parser = argparse.ArgumentParser(description="Train a PPO trading bot.")
    parser.add_argument("--reward-mode", default="legacy", choices=["legacy", "sharpe", "sortino"], help="Reward calculation mode.")
    parser.add_argument("--rolling-reward-window", type=int, default=100, help="Window size for rolling rewards.")
    parser.add_argument("--reward-epsilon", type=float, default=1e-6, help="Epsilon for numerical stability in rewards.")
    parser.add_argument("--timesteps", type=int, default=20000, help="Total training timesteps.")
    args = parser.parse_args()

    # Use M4 GPU (MPS) if available for Mac, default to CPU on Windows for stability
    if torch.backends.mps.is_available():
        DEFAULT_PPO_DEVICE = "mps"  # Apple Silicon GPU acceleration
    elif platform.system() == "Windows":
        DEFAULT_PPO_DEVICE = "cpu"  # Force CPU on Windows for stability
    elif torch.cuda.is_available():
        DEFAULT_PPO_DEVICE = "cuda"  # NVIDIA GPU on Linux
    else:
        DEFAULT_PPO_DEVICE = "cpu"  # CPU fallback

    # Load normalized Yahoo Finance tech basket data with merged daily news sentiment features
    df = get_tech_training_data(cache_path=DATA_PATH, include_news=True)

    # Create the environment
    env_kwargs = {
        "reward_mode": args.reward_mode,
        "rolling_reward_window": args.rolling_reward_window,
        "reward_epsilon": args.reward_epsilon,
    }
    env = TradingEnv(df, **env_kwargs)

    # Initialize the RL model (PPO)
    model = PPO("MlpPolicy", env, verbose=1, device=DEFAULT_PPO_DEVICE)

    # Train the model
    print(f"Training the agent (mode={args.reward_mode}, window={args.rolling_reward_window})...")
    model.learn(total_timesteps=args.timesteps)

    # Save the trained model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH.as_posix())
    print(f"Model saved as {MODEL_PATH.name}.zip")

    # Test the model
    obs, _ = env.reset()
    for _ in range(10):
        action, _states = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        print(f"Action: {action}, Reward: {reward:.2f}, Net Worth: {env.net_worth:.2f}")
        if terminated or truncated:
            break

if __name__ == "__main__":
    main()

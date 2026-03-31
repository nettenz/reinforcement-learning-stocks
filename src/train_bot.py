import argparse
from pathlib import Path
import platform
import sys

from stable_baselines3 import SAC
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv

DATA_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
MODEL_PATH = ROOT_DIR / "models" / "sac_trading_bot"

def main():
    parser = argparse.ArgumentParser(description="Train an SAC continuous trading bot.")
    parser.add_argument("--reward-mode", default="legacy", choices=["legacy", "sharpe", "sortino"], help="Reward calculation mode.")
    parser.add_argument("--rolling-reward-window", type=int, default=100, help="Window size for rolling rewards.")
    parser.add_argument("--reward-epsilon", type=float, default=1e-6, help="Epsilon for numerical stability in rewards.")
    parser.add_argument("--timesteps", type=int, default=20000, help="Total training timesteps.")

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
    env = TradingEnv(df, **env_kwargs)

    # Initialize the RL model (SAC continuous)
    # ent_coef handles exploration mathematically in continuous spaces better than discrete PPO bounds
    model = SAC("MlpPolicy", env, verbose=1, device=args.device, ent_coef="auto")

    # Train the model
    print(f"Training Continuous SAC agent (mode={args.reward_mode}, window={args.rolling_reward_window})...")
    model.learn(total_timesteps=args.timesteps)

    # Save the trained model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH.as_posix())
    print(f"Model saved as {MODEL_PATH.name}.zip")

    # Test the model
    obs, _ = env.reset()
    for _ in range(10):
        action, _states = model.predict(obs, deterministic=True)
        # Action is returned as a 1D array from SAC [weight]
        obs, reward, terminated, truncated, info = env.step(action)
        print(f"Action Wgt: {action[0]:.2f}, Reward: {reward:.2f}, Net Worth: {env.net_worth:.2f}")
        if terminated or truncated:
            break

if __name__ == "__main__":
    main()

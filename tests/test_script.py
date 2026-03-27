import pandas as pd
from stable_baselines3 import PPO
from pathlib import Path
import os
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.trading_env import TradingEnv

MOCK_DATA_PATH = ROOT_DIR / "data" / "mock_data.csv"

# Load mock data
if not os.path.exists(MOCK_DATA_PATH):
    print("data/mock_data.csv not found!")
    exit(1)

df = pd.read_csv(MOCK_DATA_PATH)

# Create the environment
try:
    env = TradingEnv(df)
    print("Environment created successfully.")
except Exception as e:
    print(f"Failed to create environment: {e}")
    exit(1)

# Initialize the RL model (PPO)
try:
    model = PPO("MlpPolicy", env, verbose=0)
    print("Model initialized successfully.")
except Exception as e:
    print(f"Failed to initialize model: {e}")
    exit(1)

# Run a single step test
try:
    obs, _ = env.reset()
    action, _states = model.predict(obs, deterministic=True)
    obs, reward, terminated, truncated, info = env.step(action)
    print(f"Single step test successful. Action: {action}, Reward: {reward}")
except Exception as e:
    print(f"Failed during step test: {e}")
    exit(1)

print("All simple tests passed!")

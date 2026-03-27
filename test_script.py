import pandas as pd
from stable_baselines3 import PPO
from trading_env import TradingEnv
import os

# Load mock data
if not os.path.exists('mock_data.csv'):
    print("mock_data.csv not found!")
    exit(1)

df = pd.read_csv('mock_data.csv')

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

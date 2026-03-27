from pathlib import Path
import sys

from stable_baselines3 import PPO

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv

DATA_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
MODEL_PATH = ROOT_DIR / "models" / "ppo_trading_bot"

# Load normalized Yahoo Finance tech basket data (cached locally after first fetch)
df = get_tech_training_data(cache_path=DATA_PATH)

# Create the environment
env = TradingEnv(df)

# Initialize the RL model (PPO)
model = PPO("MlpPolicy", env, verbose=1)

# Train the model
print("Training the agent...")
model.learn(total_timesteps=20000)

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

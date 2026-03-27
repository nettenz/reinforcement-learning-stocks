from stable_baselines3 import PPO
from market_data import get_tech_training_data
from trading_env import TradingEnv

# Load normalized Yahoo Finance tech basket data (cached locally after first fetch)
df = get_tech_training_data()

# Create the environment
env = TradingEnv(df)

# Initialize the RL model (PPO)
model = PPO("MlpPolicy", env, verbose=1)

# Train the model
print("Training the agent...")
model.learn(total_timesteps=20000)

# Save the trained model
model.save("ppo_trading_bot")
print("Model saved as ppo_trading_bot.zip")

# Test the model
obs, _ = env.reset()
for _ in range(10):
    action, _states = model.predict(obs, deterministic=True)
    obs, reward, terminated, truncated, info = env.step(action)
    print(f"Action: {action}, Reward: {reward:.2f}, Net Worth: {env.net_worth:.2f}")
    if terminated or truncated:
        break

import gymnasium as gym
from gymnasium import spaces
import numpy as np

class TradingEnv(gym.Env):
    def __init__(self, df, initial_balance=1000):
        super(TradingEnv, self).__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.current_step = 0
        self.balance = initial_balance
        self.shares_held = 0
        self.net_worth = initial_balance
        
        # Action space: 0 = Hold, 1 = Buy, 2 = Sell
        self.action_space = spaces.Discrete(3)
        
        # Observation space: OHLCV + Balance + Shares Held
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float32)
        self.price_column = 'RawClose' if 'RawClose' in self.df.columns else 'Close'

    def _get_obs(self):
        obs = np.array([
            self.df.loc[self.current_step, 'Open'],
            self.df.loc[self.current_step, 'High'],
            self.df.loc[self.current_step, 'Low'],
            self.df.loc[self.current_step, 'Close'],
            self.df.loc[self.current_step, 'Volume'],
            self.balance,
            self.shares_held
        ], dtype=np.float32)
        return obs

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = self.initial_balance
        self.shares_held = 0
        self.net_worth = self.initial_balance
        return self._get_obs(), {}

    def step(self, action):
        current_price = max(float(self.df.loc[self.current_step, self.price_column]), 1e-8)
        
        # Execute action
        if action == 1: # Buy
            if self.balance > current_price:
                shares_to_buy = int(self.balance // current_price)
                self.shares_held += shares_to_buy
                self.balance -= shares_to_buy * current_price
        elif action == 2: # Sell
            self.balance += self.shares_held * current_price
            self.shares_held = 0

        # Update net worth
        new_net_worth = self.balance + (self.shares_held * current_price)
        reward = new_net_worth - self.net_worth
        self.net_worth = new_net_worth

        # Move to next step
        self.current_step += 1
        
        terminated = self.current_step >= len(self.df) - 1
        truncated = False
        
        return self._get_obs(), reward, terminated, truncated, {}

print("TradingEnv class defined.")

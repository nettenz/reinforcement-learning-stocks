import gymnasium as gym
from gymnasium import spaces
import numpy as np


class TradingEnv(gym.Env):
    def __init__(
        self,
        df,
        initial_balance=1000,
        transaction_cost_rate=0.0,
        trade_penalty=0.0,
    ):
        super(TradingEnv, self).__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.transaction_cost_rate = float(transaction_cost_rate)
        self.trade_penalty = float(trade_penalty)
        self.current_step = 0
        self.balance = initial_balance
        self.shares_held = 0
        self.net_worth = initial_balance
        
        # Action space: 0 = Hold, 1 = Buy, 2 = Sell
        self.action_space = spaces.Discrete(3)

        self.market_feature_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
        self.news_feature_columns = [
            "NewsCount",
            "SentimentMean",
            "SentimentStd",
            "SentimentMin",
            "SentimentMax",
        ]
        self.active_news_columns = [col for col in self.news_feature_columns if col in self.df.columns]

        # Observation space: market features + optional news features + balance + shares held
        observation_size = len(self.market_feature_columns) + len(self.active_news_columns) + 2
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(observation_size,), dtype=np.float32)
        self.price_column = 'RawClose' if 'RawClose' in self.df.columns else 'Close'

    def _get_obs(self):
        row = self.df.loc[self.current_step]
        market_values = [float(row[col]) for col in self.market_feature_columns]
        news_values = [float(row[col]) for col in self.active_news_columns]
        obs = np.array(market_values + news_values + [self.balance, self.shares_held], dtype=np.float32)
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
        trade_executed = False

        # Execute action
        if action == 1: # Buy
            if self.balance > current_price:
                shares_to_buy = int(self.balance // current_price)
                if shares_to_buy > 0:
                    gross_value = shares_to_buy * current_price
                    fee = gross_value * self.transaction_cost_rate
                    self.shares_held += shares_to_buy
                    self.balance -= gross_value + fee
                    trade_executed = True
        elif action == 2: # Sell
            if self.shares_held > 0:
                gross_value = self.shares_held * current_price
                fee = gross_value * self.transaction_cost_rate
                self.balance += gross_value - fee
                self.shares_held = 0
                trade_executed = True

        if trade_executed and self.trade_penalty > 0:
            self.balance -= self.trade_penalty

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

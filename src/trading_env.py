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
        reward_return_scale=1.0,
        reward_direction_scale=0.35,
        reward_hold_penalty_scale=0.05,
        reward_drawdown_penalty_scale=0.10,
        reward_action_bonus_scale=0.02,
        reward_clip=1.0,
        reward_ignore_transaction_cost=True,
    ):
        super(TradingEnv, self).__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.transaction_cost_rate = float(transaction_cost_rate)
        self.trade_penalty = float(trade_penalty)
        self.reward_return_scale = float(reward_return_scale)
        self.reward_direction_scale = float(reward_direction_scale)
        self.reward_hold_penalty_scale = float(reward_hold_penalty_scale)
        self.reward_drawdown_penalty_scale = float(reward_drawdown_penalty_scale)
        self.reward_action_bonus_scale = float(reward_action_bonus_scale)
        self.reward_clip = float(reward_clip)
        self.reward_ignore_transaction_cost = bool(reward_ignore_transaction_cost)
        self.current_step = 0
        self.balance = initial_balance
        self.shares_held = 0
        self.net_worth = initial_balance
        self.reward_balance = float(initial_balance)
        self.reward_shares_held = 0
        self.reward_net_worth = float(initial_balance)
        self.reward_peak_net_worth = float(initial_balance)
        
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
        self.reward_balance = float(self.initial_balance)
        self.reward_shares_held = 0
        self.reward_net_worth = float(self.initial_balance)
        self.reward_peak_net_worth = float(self.initial_balance)
        return self._get_obs(), {}

    def step(self, action):
        current_price = max(float(self.df.loc[self.current_step, self.price_column]), 1e-8)
        next_step = min(self.current_step + 1, len(self.df) - 1)
        next_price = max(float(self.df.loc[next_step, self.price_column]), 1e-8)
        raw_step_return = (next_price / current_price) - 1.0
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

        # Mirror portfolio transitions for reward shaping, optionally excluding fees and penalties.
        if action == 1:
            if self.reward_balance > current_price:
                shares_to_buy = int(self.reward_balance // current_price)
                if shares_to_buy > 0:
                    gross_value = shares_to_buy * current_price
                    fee = gross_value * self.transaction_cost_rate if not self.reward_ignore_transaction_cost else 0.0
                    self.reward_shares_held += shares_to_buy
                    self.reward_balance -= gross_value + fee
                    if not self.reward_ignore_transaction_cost and self.trade_penalty > 0:
                        self.reward_balance -= self.trade_penalty
        elif action == 2:
            if self.reward_shares_held > 0:
                gross_value = self.reward_shares_held * current_price
                fee = gross_value * self.transaction_cost_rate if not self.reward_ignore_transaction_cost else 0.0
                self.reward_balance += gross_value - fee
                self.reward_shares_held = 0
                if not self.reward_ignore_transaction_cost and self.trade_penalty > 0:
                    self.reward_balance -= self.trade_penalty

        # Update net worth
        new_net_worth = self.balance + (self.shares_held * current_price)
        self.net_worth = new_net_worth

        reward_prev_net_worth = max(self.reward_net_worth, 1e-8)
        reward_new_net_worth = self.reward_balance + (self.reward_shares_held * next_price)
        portfolio_return = (reward_new_net_worth / reward_prev_net_worth) - 1.0

        directional_reward = 0.0
        if action == 1:  # Buy should align with positive next return
            directional_reward = raw_step_return
        elif action == 2:  # Sell should align with negative next return
            directional_reward = -raw_step_return

        hold_penalty = -self.reward_hold_penalty_scale * abs(raw_step_return) if action == 0 else 0.0

        action_bonus = self.reward_action_bonus_scale if action in (1, 2) else 0.0

        reward_peak = max(self.reward_peak_net_worth, reward_new_net_worth)
        drawdown = (reward_peak - reward_new_net_worth) / max(reward_peak, 1e-8)
        drawdown_penalty = -self.reward_drawdown_penalty_scale * drawdown

        reward = (
            (self.reward_return_scale * portfolio_return)
            + (self.reward_direction_scale * directional_reward)
            + hold_penalty
            + action_bonus
            + drawdown_penalty
        )
        reward = float(np.clip(reward, -self.reward_clip, self.reward_clip))

        self.reward_net_worth = reward_new_net_worth
        self.reward_peak_net_worth = reward_peak

        # Move to next step
        self.current_step += 1
        
        terminated = self.current_step >= len(self.df) - 1
        truncated = False
        info = {
            "reward_total": reward,
            "reward_portfolio_return": float(self.reward_return_scale * portfolio_return),
            "reward_direction": float(self.reward_direction_scale * directional_reward),
            "reward_hold_penalty": float(hold_penalty),
            "reward_action_bonus": float(action_bonus),
            "reward_drawdown_penalty": float(drawdown_penalty),
            "raw_step_return": float(raw_step_return),
            "reward_drawdown": float(drawdown),
            "reward_net_worth": float(reward_new_net_worth),
        }

        return self._get_obs(), reward, terminated, truncated, info

print("TradingEnv class defined.")

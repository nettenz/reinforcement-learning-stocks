import gymnasium as gym
from gymnasium import spaces
import numpy as np


class TradingEnv(gym.Env):
    def __init__(
        self,
        df,
        initial_balance=1000,
        include_position_in_observation=True,
        transaction_cost_rate=0.0,
        trade_penalty=0.0,
        reward_return_scale=1.0,
        reward_direction_scale=0.35,
        reward_hold_penalty_scale=0.10,
        reward_drawdown_penalty_scale=0.10,
        reward_action_bonus_scale=0.02,
        reward_clip=1.0,
        reward_ignore_transaction_cost=True,
    ):
        super(TradingEnv, self).__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.include_position_in_observation = bool(include_position_in_observation)
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
        self.position = 0 # 0=Neutral, 1=Long, 2=Short (mapped to -1 internally)
        
        # Action space: 0 = Neutral, 1 = Long, 2 = Short
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

        # Observation space: market features + optional news features + balance + shares held (+ position for newer models)
        state_feature_count = 3 if self.include_position_in_observation else 2
        observation_size = len(self.market_feature_columns) + len(self.active_news_columns) + state_feature_count
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(observation_size,), dtype=np.float32)
        self.price_column = 'RawClose' if 'RawClose' in self.df.columns else 'Close'

    def _get_obs(self):
        row = self.df.loc[self.current_step]
        market_values = [float(row[col]) for col in self.market_feature_columns]
        news_values = [float(row[col]) for col in self.active_news_columns]
        account_state = [self.balance, self.shares_held]
        if self.include_position_in_observation:
            account_state.append(self.position)
        obs = np.array(market_values + news_values + account_state, dtype=np.float32)
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
        self.position = 0
        return self._get_obs(), {}

    def step(self, action):
        current_price = max(float(self.df.loc[self.current_step, self.price_column]), 1e-8)
        next_step = min(self.current_step + 1, len(self.df) - 1)
        next_price = max(float(self.df.loc[next_step, self.price_column]), 1e-8)
        raw_step_return = (next_price / current_price) - 1.0
        
        # Map action to position: 0=Neutral, 1=Long, 2=Short
        # position_mapping: 0 -> 0, 1 -> 1, 2 -> -1
        target_position_value = 0
        if action == 1:
            target_position_value = 1
        elif action == 2:
            target_position_value = -1
            
        trade_executed = False
        
        # Execute action based on target position
        if target_position_value != self.position:
            # 1. Close current position
            if self.position == 1: # Close Long
                gross_value = self.shares_held * current_price
                fee = gross_value * self.transaction_cost_rate
                self.balance += gross_value - fee
                self.shares_held = 0
                trade_executed = True
            elif self.position == -1: # Close Short
                # Covering short: cost = shares * price * (1 + fee)
                # For simplicity, we assume we always have enough balance to cover.
                gross_value = abs(self.shares_held) * current_price
                fee = gross_value * self.transaction_cost_rate
                self.balance -= gross_value + fee
                self.shares_held = 0
                trade_executed = True
                
            # 2. Open new position
            if target_position_value == 1: # Open Long
                shares_to_buy = int(self.balance // (current_price * (1 + self.transaction_cost_rate)))
                if shares_to_buy > 0:
                    gross_value = shares_to_buy * current_price
                    fee = gross_value * self.transaction_cost_rate
                    self.shares_held = shares_to_buy
                    self.balance -= gross_value + fee
                    trade_executed = True
            elif target_position_value == -1: # Open Short
                # Simple shorting: Sell-to-open. 
                # Limit short value to 50% of net worth for safety (or just use balance).
                # Using balance as margin/collateral for this simple model.
                shares_to_short = int(self.balance // (current_price * (1 + self.transaction_cost_rate)))
                if shares_to_short > 0:
                    gross_value = shares_to_short * current_price
                    fee = gross_value * self.transaction_cost_rate
                    self.shares_held = -shares_to_short
                    self.balance += gross_value - fee
                    trade_executed = True
                    
            self.position = target_position_value

        if trade_executed and self.trade_penalty > 0:
            self.balance -= self.trade_penalty

        # Mirror portfolio transitions for reward shaping, optionally excluding fees and penalties.
        # Position-based reward doesn't strictly need reward_shares_held if we use position * raw_return,
        # but let's keep it for portfolio_return calculation.
        if target_position_value != (self.reward_shares_held / abs(self.reward_shares_held) if self.reward_shares_held != 0 else 0):
            # Close reward position
            if self.reward_shares_held > 0: # Long
                self.reward_balance += self.reward_shares_held * current_price
                self.reward_shares_held = 0
            elif self.reward_shares_held < 0: # Short
                self.reward_balance -= abs(self.reward_shares_held) * current_price
                self.reward_shares_held = 0
            
            # Open reward position
            if target_position_value == 1:
                shares = int(self.reward_balance // current_price)
                if shares > 0:
                    self.reward_shares_held = shares
                    self.reward_balance -= shares * current_price
            elif target_position_value == -1:
                shares = int(self.reward_balance // current_price)
                if shares > 0:
                    self.reward_shares_held = -shares
                    self.reward_balance += shares * current_price

        # Update net worth
        new_net_worth = self.balance + (self.shares_held * current_price)
        self.net_worth = new_net_worth

        reward_prev_net_worth = max(self.reward_net_worth, 1e-8)
        reward_new_net_worth = self.reward_balance + (self.reward_shares_held * next_price)
        portfolio_return = (reward_new_net_worth / reward_prev_net_worth) - 1.0

        # Primary directional reward based on target position
        directional_reward = target_position_value * raw_step_return

        # Hold penalty: only applied when in Neutral (0) position and market is moving.
        hold_penalty = -self.reward_hold_penalty_scale * abs(raw_step_return) if target_position_value == 0 else 0.0

        # Only reward actionable trades that actually executed.
        action_bonus = self.reward_action_bonus_scale if trade_executed else 0.0

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

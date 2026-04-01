import gymnasium as gym
from gymnasium import spaces
import numpy as np
from collections import deque

class PositionManager:
    """Handles portfolio math, fractional/integer scaling, and transaction costs."""
    def __init__(self, initial_balance, transaction_cost_rate, trade_penalty):
        self.initial_balance = float(initial_balance)
        self.transaction_cost_rate = float(transaction_cost_rate)
        self.trade_penalty = float(trade_penalty)
        self.reset()
        
    def reset(self):
        self.balance = self.initial_balance
        self.shares_held = 0
        self.net_worth = self.initial_balance
        self.peak_net_worth = self.initial_balance
        self.current_weight = 0.0
        self.time_in_position = 0
        self.entry_price = 0.0
        
    def step(self, target_weight, current_price):
        target_weight = float(np.clip(target_weight, -1.0, 1.0))
        
        # Debounce: Do not incur fees for micro-adjustments smaller than 5% portfolio shift
        if abs(target_weight - self.current_weight) < 0.05:
            target_weight = self.current_weight
            
        target_value = target_weight * self.net_worth
        target_shares = int(target_value // current_price)
        delta_shares = target_shares - self.shares_held
        
        trade_executed = delta_shares != 0
        
        if trade_executed:
            gross_value = abs(delta_shares) * current_price
            fee = gross_value * self.transaction_cost_rate
            
            # Use current_price for the trade execution
            self.balance -= (delta_shares * current_price) + fee
            self.shares_held = target_shares
            
            if self.trade_penalty > 0:
                self.balance -= self.trade_penalty
                
            if target_weight != 0 and self.current_weight == 0:
                self.entry_price = current_price
                self.time_in_position = 0
                
        if self.shares_held == 0:
            self.current_weight = 0.0
            self.entry_price = 0.0
            self.time_in_position = 0
        else:
            # Update current_weight based on the actual target weight chosen
            self.current_weight = target_weight
            self.time_in_position += 1
            
        prev_net_worth = self.net_worth
        # Net worth is cash balance + market value of shares
        self.net_worth = self.balance + (self.shares_held * current_price)
        self.peak_net_worth = max(self.peak_net_worth, self.net_worth)
        
        portfolio_return = (self.net_worth / max(prev_net_worth, 1e-8)) - 1.0
        drawdown = (self.peak_net_worth - self.net_worth) / max(self.peak_net_worth, 1e-8)
        
        # unrealized_pnl_pct for the observation state
        unrealized_pnl_pct = 0.0
        if self.entry_price > 0:
            ratio = current_price / self.entry_price
            unrealized_pnl_pct = ratio - 1.0 if self.shares_held > 0 else 1.0 - ratio
            
        return trade_executed, portfolio_return, drawdown, unrealized_pnl_pct


class RewardEvaluator:
    """Strategy pattern for varying reward schemas (Legacy, Sharpe, Sortino)."""
    def __init__(self, mode, rolling_window, epsilon, return_scale, dir_scale, hold_scale, dd_scale, action_scale, clip):
        self.mode = mode.lower()
        self.epsilon = epsilon
        self.return_scale = return_scale
        self.dir_scale = dir_scale
        self.hold_scale = hold_scale
        self.dd_scale = dd_scale
        self.action_scale = action_scale
        self.clip = clip
        self.returns_buffer = deque(maxlen=rolling_window)

    def calculate(self, portfolio_return, realized_return, current_weight, trade_executed, drawdown):
        strategy_realized_return = current_weight * realized_return
        self.returns_buffer.append(strategy_realized_return)

        hold_penalty = -self.hold_scale * abs(realized_return) if abs(current_weight) < 0.1 else 0.0
        action_bonus = self.action_scale if trade_executed else 0.0
        dd_penalty = -self.dd_scale * drawdown
        
        directional_reward = strategy_realized_return

        base_reward = 0.0
        risk_metric = 0.0

        if self.mode == "sharpe":
            risk_metric = self._sharpe()
            base_reward = self.return_scale * risk_metric
        elif self.mode == "sortino":
            risk_metric = self._sortino()
            base_reward = self.return_scale * risk_metric
        else:
            base_reward = (self.return_scale * portfolio_return) + (self.dir_scale * directional_reward)

        total = base_reward + hold_penalty + action_bonus + dd_penalty
        return float(np.clip(total, -self.clip, self.clip)), risk_metric, strategy_realized_return, directional_reward, hold_penalty, action_bonus, dd_penalty

    def _sharpe(self):
        if len(self.returns_buffer) < 2: return 0.0
        rets = np.array(self.returns_buffer)
        std = np.std(rets)
        return np.mean(rets) / std if std > self.epsilon else 0.0

    def _sortino(self):
        if len(self.returns_buffer) < 2: return 0.0
        rets = np.array(self.returns_buffer)
        downside = rets[rets < 0]
        mean = np.mean(rets)
        if len(downside) < 1: return mean / self.epsilon if mean > 0 else 0.0
        d_std = np.std(downside)
        return mean / d_std if d_std > self.epsilon else (mean / self.epsilon if mean > 0 else 0.0)
    
    def reset(self):
        self.returns_buffer.clear()


class TradingEnv(gym.Env):
    """
    OOP Refactored Continuous Trading Environment.
    Supports fractional sizing (-1.0 to 1.0) and maintains independent state tracking.
    """
    def __init__(
        self,
        df,
        initial_balance=1000,
        include_position_in_observation=True,
        transaction_cost_rate=0.0,
        trade_penalty=0.0,
        reward_return_scale=1.0,
        reward_direction_scale=0.40,
        reward_hold_penalty_scale=0.10,
        reward_drawdown_penalty_scale=0.10,
        reward_action_bonus_scale=0.02,
        reward_clip=1.0,
        reward_ignore_transaction_cost=True,
        market_feature_columns=None,
        reward_mode="legacy",
        rolling_reward_window=100,
        reward_epsilon=1e-6,
    ):
        super(TradingEnv, self).__init__()
        self.df = df
        self.include_position = bool(include_position_in_observation)
        self.current_step = 0
        self.price_column = 'RawClose' if 'RawClose' in self.df.columns else 'Close'

        # OOP Subsystems
        self.pm = PositionManager(initial_balance, transaction_cost_rate, trade_penalty)
        self.re = RewardEvaluator(
            reward_mode, rolling_reward_window, reward_epsilon,
            reward_return_scale, reward_direction_scale, reward_hold_penalty_scale,
            reward_drawdown_penalty_scale, reward_action_bonus_scale, reward_clip
        )
        
        # Continuous Action Space: [-1.0 (Full Short), 1.0 (Full Long)]
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)

        # Observation Space Configuration
        if market_feature_columns is None:
            if all(col in self.df.columns for col in ["Open", "High", "Low", "Close", "Volume"]):
                self.market_feature_columns = ["Open", "High", "Low", "Close", "Volume"]
            else:
                potential_cols = [
                    "LogReturn", "VolLogDiff", "RelRange", "RelOpen", "RelMACD", "RSI_Centered",
                    "RelATR", "BB_Width", "BB_Upper_Dist", "BB_Lower_Dist", "SMA_Trend",
                    "RelVWAP", "MACD_Signal_Rel", "MACD_Hist_Rel"
                ]
                self.market_feature_columns = [col for col in potential_cols if col in self.df.columns]
        else:
            self.market_feature_columns = market_feature_columns

        self.news_feature_columns = [
            "NewsCount", "SentimentMean", "SentimentStd", "SentimentMin", "SentimentMax",
            "SentimentConfidenceMean", "SentimentGeminiShare", "SentimentOllamaShare"
        ]
        self.active_news_columns = [col for col in self.news_feature_columns if col in self.df.columns]

        # Base market + news + [balance, shares_held]
        state_count = 2
        
        # + [current_weight, unrealized_pnl, time_in_position]
        if self.include_position:
            state_count += 3 
            
        observation_size = len(self.market_feature_columns) + len(self.active_news_columns) + state_count
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(observation_size,), dtype=np.float32)

    def _get_obs(self, unrealized_pnl=0.0):
        row = self.df.loc[self.current_step]
        market_values = [float(row[col]) for col in self.market_feature_columns]
        news_values = [float(row[col]) for col in self.active_news_columns]
        
        account_state = [self.pm.balance, self.pm.shares_held]
        if self.include_position:
            account_state.extend([self.pm.current_weight, unrealized_pnl, self.pm.time_in_position])
            
        return np.array(market_values + news_values + account_state, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.pm.reset()
        self.re.reset()
        return self._get_obs(), {}
    
    @property
    def net_worth(self):
        # Expose net_worth for backwards compatibility scripts reading the env
        return self.pm.net_worth

    @property
    def position(self):
        # Translate continuous to discrete notation for backwards compatibility with downstream analytics
        if self.pm.current_weight > 0.1: return 1
        if self.pm.current_weight < -0.1: return 2
        return 0

    def step(self, action):
        # If wrapped by SB3, action is a 1D array. Unwrap single float.
        if isinstance(action, (np.ndarray, list)):
            target_weight = float(action[0])
        else:
            target_weight = float(action)
            
        current_price = max(float(self.df.loc[self.current_step, self.price_column]), 1e-8)
        
        prev_step = max(0, self.current_step - 1)
        prev_price = max(float(self.df.loc[prev_step, self.price_column]), 1e-8)
        realized_return = (current_price / prev_price) - 1.0 if self.current_step > 0 else 0.0
        
        # Execute trade via Position Manager
        trade_executed, portfolio_return, drawdown, unrealized_pnl = self.pm.step(target_weight, current_price)
        
        # Evaluate reward
        reward, risk_metric, strategy_realized_return, dir_rew, hold_pen, action_bon, dd_pen = self.re.calculate(
            portfolio_return, realized_return, self.pm.current_weight, trade_executed, drawdown
        )
        
        self.current_step += 1
        terminated = self.current_step >= len(self.df) - 1
        truncated = False
        
        info = {
            "reward_total": reward,
            "reward_portfolio_return": portfolio_return,
            "reward_direction": dir_rew,
            "reward_hold_penalty": hold_pen,
            "reward_action_bonus": action_bon,
            "reward_drawdown_penalty": dd_pen,
            "realized_return": realized_return,
            "reward_drawdown": drawdown,
            "reward_net_worth": self.pm.net_worth,
            "reward_mode": self.re.mode,
            "reward_risk_metric": risk_metric,
        }

        return self._get_obs(unrealized_pnl), reward, terminated, truncated, info


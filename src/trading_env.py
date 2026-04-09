import gymnasium as gym
from gymnasium import spaces
import numpy as np
from collections import deque


LEADERBOARD_VERSION = 2

class PositionManager:
    """Handles portfolio math, fractional/integer scaling, and transaction costs."""
    def __init__(self, initial_balance, transaction_cost_rate, trade_penalty, spread_bps=0.0, slippage_bps=0.0):
        self.initial_balance = float(initial_balance)
        self.transaction_cost_rate = float(transaction_cost_rate)
        self.trade_penalty = float(trade_penalty)
        self.spread_bps = max(float(spread_bps), 0.0)
        self.slippage_bps = max(float(slippage_bps), 0.0)
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
        fee = 0.0
        execution_price = current_price
        gross_value = 0.0
        
        trade_penalty_paid = 0.0

        if trade_executed:
            side = 1.0 if delta_shares > 0 else -1.0
            spread_component = (self.spread_bps * 1e-4) * 0.5
            slippage_component = self.slippage_bps * 1e-4
            impact = spread_component + slippage_component
            execution_price = max(current_price * (1.0 + (side * impact)), 1e-8)

            gross_value = abs(delta_shares) * execution_price
            fee = gross_value * self.transaction_cost_rate
            
            self.balance -= (delta_shares * execution_price) + fee
            self.shares_held = target_shares
            
            if self.trade_penalty > 0:
                trade_penalty_paid = float(self.trade_penalty)
                self.balance -= trade_penalty_paid
                
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
            
        return trade_executed, portfolio_return, drawdown, unrealized_pnl_pct, execution_price, fee, trade_penalty_paid, gross_value


class RewardEvaluator:
    """Strategy pattern for varying reward schemas (Legacy, Sharpe, Sortino, Hybrid)."""
    def __init__(
        self,
        mode,
        rolling_window,
        epsilon,
        return_scale,
        pnl_scale,
        dir_scale,
        hold_scale,
        dd_scale,
        action_scale,
        turnover_scale,
        clip,
        sharpe_scale=0.0,
    ):
        self.mode = mode.lower()
        self.epsilon = epsilon
        self.return_scale = return_scale
        self.pnl_scale = pnl_scale
        self.dir_scale = dir_scale
        self.hold_scale = hold_scale
        self.dd_scale = dd_scale
        self.action_scale = action_scale
        self.turnover_scale = turnover_scale
        self.clip = clip
        self.sharpe_scale = sharpe_scale  # NEW: Sharpe as secondary regularizer (Variant B)
        self.returns_buffer = deque(maxlen=rolling_window)

    def calculate(self, portfolio_return, realized_return, exposure_weight, weight_change, trade_executed, drawdown):
        strategy_realized_return = exposure_weight * realized_return
        self.returns_buffer.append(strategy_realized_return)

        pnl_reward = self._pnl_reward(portfolio_return)
        hold_penalty = -self.hold_scale * abs(realized_return) if abs(exposure_weight) < 0.1 else 0.0
        action_bonus = self.action_scale if trade_executed else 0.0
        turnover_penalty = -self.turnover_scale * abs(weight_change)
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
        else:  # legacy
            base_reward = self.return_scale * portfolio_return

        # Directional shaping and penalties apply across all reward modes
        # so hyperparameters behave consistently in legacy/sharpe/sortino experiments.
        total = base_reward + pnl_reward + (self.dir_scale * directional_reward) + hold_penalty + action_bonus + turnover_penalty + dd_penalty
        return (
            float(np.clip(total, -self.clip, self.clip)),
            risk_metric,
            strategy_realized_return,
            directional_reward,
            pnl_reward,
            hold_penalty,
            action_bonus,
            turnover_penalty,
            dd_penalty,
        )

    def _pnl_reward(self, portfolio_return):
        return self.pnl_scale * float(portfolio_return)

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
        reward_pnl_scale=0.0,
        reward_direction_scale=0.40,
        reward_hold_penalty_scale=0.10,
        reward_drawdown_penalty_scale=0.10,
        reward_action_bonus_scale=0.02,
        reward_turnover_penalty_scale=0.05,
        reward_clip=1.0,
        reward_ignore_transaction_cost=True,
        execution_mode="same_bar",
        spread_bps=0.0,
        slippage_bps=0.0,
        max_weight_delta_per_step=0.0,
        market_feature_columns=None,
        reward_mode="legacy",
        rolling_reward_window=100,
        reward_epsilon=1e-6,
        reward_sharpe_scale=0.0,
    ):
        super(TradingEnv, self).__init__()
        self.df = df
        self.include_position = bool(include_position_in_observation)
        self.current_step = 0
        self.price_column = 'RawClose' if 'RawClose' in self.df.columns else 'Close'
        self.execution_mode = str(execution_mode).lower()
        self.reward_ignore_transaction_cost = bool(reward_ignore_transaction_cost)
        self.max_weight_delta_per_step = float(max_weight_delta_per_step)
        if self.max_weight_delta_per_step < 0.0:
            raise ValueError("max_weight_delta_per_step must be >= 0.0")
        if self.max_weight_delta_per_step > 2.0:
            raise ValueError("max_weight_delta_per_step must be <= 2.0")
        if self.execution_mode not in {"same_bar", "next_bar"}:
            raise ValueError("execution_mode must be one of: same_bar, next_bar")
        self.pending_target_weight = 0.0

        # OOP Subsystems
        self.pm = PositionManager(
            initial_balance,
            transaction_cost_rate,
            trade_penalty,
            spread_bps=spread_bps,
            slippage_bps=slippage_bps,
        )
        self.re = RewardEvaluator(
            reward_mode, rolling_reward_window, reward_epsilon,
            reward_return_scale, reward_pnl_scale, reward_direction_scale, reward_hold_penalty_scale,
            reward_drawdown_penalty_scale, reward_action_bonus_scale, reward_turnover_penalty_scale, reward_clip,
            sharpe_scale=reward_sharpe_scale
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

    def _apply_max_weight_delta(self, current_weight, desired_weight):
        """Cap exposure changes per step when realism gating is enabled."""
        desired_weight = float(np.clip(desired_weight, -1.0, 1.0))
        if self.max_weight_delta_per_step <= 0.0:
            return desired_weight, False

        lower = max(-1.0, float(current_weight) - self.max_weight_delta_per_step)
        upper = min(1.0, float(current_weight) + self.max_weight_delta_per_step)
        capped_weight = float(np.clip(desired_weight, lower, upper))
        was_limited = abs(capped_weight - desired_weight) > 1e-12
        return capped_weight, was_limited

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
        self.pending_target_weight = 0.0
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
        # Accept scalar, 0-d ndarray, or 1-d action arrays from different callers/SB3 wrappers.
        action_array = np.asarray(action)
        if action_array.ndim == 0:
            raw_action = action_array.item()
        else:
            raw_action = action_array.reshape(-1)[0]

        # Backward-compat for legacy PPO discrete policies:
        # 0=Hold, 1=Buy(Long), 2=Sell(Short) -> map into continuous target weights.
        if isinstance(raw_action, (int, np.integer)) and raw_action in (0, 1, 2):
            desired_target_weight = {0: 0.0, 1: 1.0, 2: -1.0}[int(raw_action)]
        else:
            desired_target_weight = float(raw_action)

        if self.execution_mode == "next_bar":
            execution_target_weight = self.pending_target_weight
            self.pending_target_weight = desired_target_weight
        else:
            execution_target_weight = desired_target_weight

        execution_target_weight_pre_cap = float(execution_target_weight)
            
        current_price = max(float(self.df.loc[self.current_step, self.price_column]), 1e-8)
        pre_trade_weight = float(self.pm.current_weight)
        execution_target_weight, weight_delta_limited = self._apply_max_weight_delta(
            pre_trade_weight,
            execution_target_weight,
        )
        prev_net_worth = float(self.pm.net_worth)
        
        prev_step = max(0, self.current_step - 1)
        prev_price = max(float(self.df.loc[prev_step, self.price_column]), 1e-8)
        realized_return = (current_price / prev_price) - 1.0 if self.current_step > 0 else 0.0
        
        # Execute trade via Position Manager
        trade_executed, portfolio_return, drawdown, unrealized_pnl, execution_price, execution_fee, trade_penalty_paid, execution_notional = self.pm.step(
            execution_target_weight,
            current_price,
        )

        # Reward attribution uses prior exposure for this bar's realized return.
        # This avoids crediting a newly opened position for a return that occurred before the trade.
        exposure_weight = pre_trade_weight
        weight_change = float(self.pm.current_weight - pre_trade_weight)

        if self.reward_ignore_transaction_cost:
            ignored_cost = float(execution_fee + trade_penalty_paid)
            cost_ratio = ignored_cost / max(prev_net_worth, 1e-8)
            reward_portfolio_return = float(portfolio_return + cost_ratio)
        else:
            reward_portfolio_return = float(portfolio_return)
        
        # Evaluate reward
        reward, risk_metric, strategy_realized_return, dir_rew, pnl_rew, hold_pen, action_bon, turnover_pen, dd_pen = self.re.calculate(
            reward_portfolio_return,
            realized_return,
            exposure_weight,
            weight_change,
            trade_executed,
            drawdown,
        )
        
        self.current_step += 1
        terminated = self.current_step >= len(self.df) - 1
        truncated = False
        
        info = {
            "reward_total": reward,
            "reward_portfolio_return": portfolio_return,
            "reward_direction": dir_rew,
            "reward_pnl": pnl_rew,
            "reward_hold_penalty": hold_pen,
            "reward_action_bonus": action_bon,
            "reward_turnover_penalty": turnover_pen,
            "reward_drawdown_penalty": dd_pen,
            "realized_return": realized_return,
            "reward_drawdown": drawdown,
            "reward_net_worth": self.pm.net_worth,
            "reward_mode": self.re.mode,
            "reward_risk_metric": risk_metric,
            "execution_mode": self.execution_mode,
            "max_weight_delta_per_step": self.max_weight_delta_per_step,
            "execution_weight_delta_limited": int(weight_delta_limited),
            "execution_target_weight": execution_target_weight,
            "execution_target_weight_pre_cap": execution_target_weight_pre_cap,
            "desired_target_weight": desired_target_weight,
            "execution_price": execution_price,
            "execution_fee": execution_fee,
            "execution_trade_penalty": trade_penalty_paid,
            "execution_notional": execution_notional,
        }

        return self._get_obs(unrealized_pnl), reward, terminated, truncated, info

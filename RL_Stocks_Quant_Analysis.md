# RL Trading Agent — Quant Analysis & Roadmap

**Tags:** #rl #quant #trading #ppo #sac #stocks #project
**Status:** 🟡 Active Development
**Stack:** Python · Gymnasium · Stable Baselines3 · PPO → SAC · Streamlit · Yahoo Finance · NewsAPI

---

## 🧠 Project Summary

An RL-powered trading bot using PPO (Stable Baselines3 / Gymnasium) trained on Yahoo Finance OHLCV + news sentiment data for tech stocks. Includes a Streamlit analytics dashboard, multi-seed experiment runner with walk-forward validation, and leaderboard tracking.

**Long-term goal:** Dollar-neutral long/short shorting strategy with robust risk-adjusted returns.

---

## ✅ What's Solid

| Strength | Why It Matters |
|---|---|
| Walk-forward validation | Prevents temporal data leakage in train/test splits |
| Multi-seed sweeps | Catches instability — single-seed RL results are unreliable |
| Collapse rate tracking | Quantifies how often the agent degenerates to all-Hold |
| Reward includes transaction costs | Avoids unrealistic trade churn |
| News sentiment integration | Weak-form alpha signal beyond pure price action |
| Experiment leaderboard + snapshots | Reproducibility and comparison baseline |

---

## 🚨 Critical Issues (Fix First)

### 1. Look-Ahead Bias in Reward — HIGH PRIORITY

The `--reward-direction-scale` flag applies a weight on *"directional alignment with next-step movement."*

**Risk:** If `next_step_return` is computed as `(price[t+1] - price[t]) / price[t]` and used in the reward at timestep `t`, the agent is trained with future information it cannot have in production.

**Verify:**
```python
# UNSAFE — future price leaking into reward at step t
next_return = (price[t+1] - price[t]) / price[t]
reward += direction_scale * sign(action) * next_return

# SAFE — reward only uses information available at step t
reward = portfolio_return_at_t - transaction_cost - drawdown_penalty
```

**Fix:** Direction reward must use `price[t]` vs `price[t-1]` (realized, not future).

---

### 2. Non-Stationary Observation Space

Raw OHLCV prices are non-stationary — their distribution shifts over time, which breaks the i.i.d. assumption that neural networks depend on.

**Replace raw prices with:**

| Feature | Formula |
|---|---|
| Log return | `ln(close_t / close_{t-1})` |
| ATR (normalized) | `ATR_14 / close_t` |
| RSI (z-scored) | `(RSI - roll_mean) / roll_std` over trailing 60-bar window |
| Volume ratio | `volume_t / volume_roll_mean_20` |
| Sentiment delta | `sentiment_t - sentiment_{t-1}` (change, not raw score) |

```python
df['log_return'] = np.log(df['close'] / df['close'].shift(1))
df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
df['rsi_z'] = (df['rsi'] - df['rsi'].rolling(60).mean()) / df['rsi'].rolling(60).std()
```

---

### 3. Action Space — No Position Sizing

Binary Buy/Sell/Hold doesn't express conviction. A quant system modulates *size* based on signal strength.

**Option A — Discrete sizing (easier to implement):**
```
Actions: [-1, -0.5, 0, 0.5, 1]  → short full / short half / flat / long half / long full
```

**Option B — Continuous action space (better, use SAC):**
```
Action ∈ [-1, 1]  → -1 = full short, 0 = flat, 1 = full long
```

---

### 4. Wrong Optimization Target

`actionable_accuracy ≥ 0.55` is a classification metric, not a trading metric. A system with 40% win rate can be highly profitable with asymmetric risk/reward.

**Replace with financial metrics:**

| Metric | Target | Notes |
|---|---|---|
| Sharpe Ratio | > 1.5 | Risk-adjusted return (annualized) |
| Sortino Ratio | > 2.0 | Penalizes downside vol only |
| Max Drawdown | < 15% | Peak-to-trough loss |
| Calmar Ratio | > 1.0 | Ann. return / Max DD |
| Turnover | Minimize | Proxy for transaction cost sensitivity |

```python
def sharpe(returns, rf=0.0, periods=252):
    excess = returns - rf / periods
    return np.sqrt(periods) * excess.mean() / excess.std()

def max_drawdown(equity_curve):
    roll_max = equity_curve.cummax()
    drawdown = (equity_curve - roll_max) / roll_max
    return drawdown.min()
```

---

### 5. No Benchmark

Every backtest needs a null hypothesis. Without a benchmark, you can't tell if you're generating alpha or just riding market beta.

**Add to leaderboard:**
- Buy-and-hold QQQ (tech benchmark)
- Buy-and-hold SPY (broad market)
- Simple momentum: buy if 20-day return > 0, else hold

---

## 🗺️ Phased Roadmap

### Phase 1 — Audit & Fix (Week 1–2)
- [ ] Audit `trading_env.py` reward function for look-ahead bias
- [ ] Migrate observation space to stationary features
- [ ] Add Sharpe, Sortino, Max DD, Calmar to experiment leaderboard
- [ ] Add buy-and-hold benchmark column to leaderboard CSV

### Phase 2 — Upgrade RL Formulation (Week 2–4)
- [ ] Migrate from PPO → SAC with continuous action space `[-1, 1]`
- [ ] Add position exposure to observation vector (agent needs to know its own state)
- [ ] Add portfolio equity curve normalization to observation
- [ ] Implement market regime detection (simple: rolling realized vol threshold)
  - High vol regime → defensive sizing
  - Low vol regime → full exposure
- [ ] Train sub-agents per regime, ensemble at inference

### Phase 3 — Shorting Strategy (Month 2)
- [ ] Extend action space to support short exposure
- [ ] Add borrow cost to reward (annualized short fee, typically 0.5–3% for large caps)
- [ ] Implement dollar-neutral constraint: `|long_exposure - short_exposure| < threshold`
- [ ] Test on correlated tech basket (AAPL, MSFT, NVDA, GOOGL, META)
- [ ] Track market beta of portfolio — target β ≈ 0

### Phase 4 — Alpha Stack (Month 2–3)
- [ ] Upgrade sentiment: replace basic NLP with FinBERT or LLM-scored summaries
- [ ] Add earnings surprise feature: `actual_EPS - estimated_EPS`
- [ ] Add options-implied volatility (VIX or ticker-level IV from yfinance)
- [ ] Explore intraday data for order flow features (bid-ask imbalance, VWAP deviation)

---

## 🔄 PPO → SAC Migration Sketch

SAC (Soft Actor-Critic) is better suited for continuous action spaces and tends to be more sample-efficient than PPO in financial environments.

```python
from stable_baselines3 import SAC

model = SAC(
    "MlpPolicy",
    env,
    learning_rate=3e-4,
    buffer_size=100_000,       # Replay buffer (off-policy)
    batch_size=256,
    tau=0.005,                 # Soft target update
    gamma=0.99,
    ent_coef="auto",           # Auto-tune entropy (exploration)
    verbose=1,
)
model.learn(total_timesteps=500_000)
```

Key differences from PPO:
- **Off-policy** — uses a replay buffer, far more sample efficient
- **Continuous actions** — naturally handles position sizing
- **Entropy regularization** — auto-balances exploration vs. exploitation
- Trade-off: needs more hyperparameter care, slower per-step than PPO

---

## 📐 Dollar-Neutral Long/Short Framework

```
Portfolio at time t:
  long_weight  = max(0, action_t)   # [0, 1]
  short_weight = max(0, -action_t)  # [0, 1]
  
  P&L_t = long_weight  * return_long_asset_t
         - short_weight * return_short_asset_t
         - borrow_cost * short_weight / 252
         - transaction_cost * |action_t - action_{t-1}|

Constraint: |long_weight - short_weight| < 0.1  → β-neutral
```

This formulation removes market beta as a confounder. If the strategy is profitable, it's due to the model's signal, not riding a bull market.

---

## 🧪 Experiment Workflow (Current → Target)

```
CURRENT:
  Multi-seed PPO sweep → actionable_accuracy leaderboard → pick best seed

TARGET:
  Regime detection → route to sub-agent → SAC continuous position →
  Walk-forward Sharpe/Sortino evaluation → ensemble vote →
  Dollar-neutral portfolio construction → live paper trading
```

---

## 📦 Key Dependencies

```
stable-baselines3[extra]
gymnasium
yfinance
pandas-ta          # technical indicators
hmmlearn           # regime detection (HMM)
transformers       # FinBERT sentiment
quantstats         # Sharpe, Sortino, drawdown reporting
```

---

## 🔗 References

- [Stable Baselines3 SAC](https://stable-baselines3.readthedocs.io/en/master/modules/sac.html)
- [FinBERT](https://huggingface.co/ProsusAI/finbert)
- [QuantStats](https://github.com/ranaroussi/quantstats)
- [Advances in Financial ML — Lopez de Prado](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)

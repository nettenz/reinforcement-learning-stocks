# Project State: Reinforcement Learning Stocks
**Date:** April 30, 2026  
**Phase:** Base Architecture Grounding & Live Alpha Tuning  

---

## 1. Executive Summary

We have recently finalized a significant grounding of the foundational trading architecture, removing legacy look-ahead biases and converting noisy constants into true stationary signals. 

The agent is now trained using **sparse episodic rewards** (evaluating logic based solely on final holding returns against a benchmark) and executes on a strict **`next_bar`** basis to prevent same-bar close leakage. To ensure exposure to diverse market regimes, our foundational training data window has been successfully expanded to start in **2015**, capturing the deep learning inflection point, the 2018 correction, the 2022 rate hike cycle, and the modern AI boom.

## 2. Feature Engineering Ground Truth

We audited and corrected the stationary technical features feeding into the observation state to ensure strict realism:
1. **VolLogDiff:** Passed through directly (avoiding a double log-diff).
2. **RelOpen:** Passed through directly to preserve true overnight gap magnitude.
3. **RelRange:** Reconstructed using the true unnormalized High and Low prices for accurate intraday volatility signals.
4. **RelATR:** Computes True Range dynamically using true unnormalized prior closes.
5. **RelVWAP:** Typical price dynamically references true unnormalized High and Lows, while Volume is cleanly clipped at 0.0 to stabilize the rolling VWAP summation.

These updates shifted the agent from learning off constants/noise to leveraging true volatility, trend, and gap signals.

## 3. NVDA Baseline & Overtrade Tuning

Under this strictly realistic environment, a multi-seed run on NVDA demonstrated profound structural stability. The resulting models exhibited a **CV of 0.0683** across active seeds and achieved a near-zero validation/test drift (**0.0025**).

**The Overtrade Friction Challenge:**
While the agent successfully passed 4 of our 5 promotion gates (Accuracy, Win Rate, Val/Test Gap, and CV Safety), it failed the **Test Alpha** gate (-0.1929 vs QQQ benchmark). Analysis showed that the agent was executing a trade on **99.5%** of bars. Although the agent's directional picks were highly accurate (54%+ win rate), the constant transaction cost drag destroyed the alpha against a strong trending benchmark.

**Active Countermeasure:**
We are actively running the `sweep_overtrade_fix_nvda` parameter sweep to address this. The goal is to aggressively dial down the `reward_hold_penalty_scale` (to stop punishing patience during trends) while increasing the `reward_turnover_penalty_scale` (to directly tax hyperactive switching). The target is a trade rate of 60-75% which will mathematically eliminate the friction drag and flip the Alpha gate positive.

## 4. Immediate Next Steps

1. **Evaluate Sweep Results:** Analyze the `sweep_overtrade_fix_nvda` leaderboard to verify if the hold/turnover penalty tuning successfully drops the trade rate while preserving the >54% win rate.
2. **Promote the Champion:** Once a stable config passes all 5 gates (including positive Alpha), promote the champion NVDA model.
3. **Ensemble Architecture:** Integrate the promoted models into the `EnsembleAgent` wrapper in `src/trading_agent.py` to enable live, un-simulated prediction voting across tickers.

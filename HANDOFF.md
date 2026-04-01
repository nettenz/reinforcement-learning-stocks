# Cross-Platform Handoff: SAC Trading Optimization

This document provides context for continuing work on a different machine (Mac). Mention this file or the **Conversation ID: 571b035c-0bc2-4bbb-9c86-960241bbb173** to pick up where we left off.

## 🚀 Current Status
- **Success (`pressure-v1`)**: We successfully broke the "Inactivity Trap" (Degenerate behavior where the agent stays in cash to avoid volatility).
- **Metric Highlights (Seed 84)**:
    - **Val Accuracy**: 56.7%
    - **Test Accuracy**: 51.7% (Active & Positive signal returns).
    - **AI Analyst Confidence**: **20%** (Highest yet, Bullish/Neutral verdict).
- **Known Blocker**: Dashboard shows a shape mismatch error **(Model 15 vs Environment 17)**. This is because `experiments.py` doesn't currently save model weights, and the dashboard is loading an old model.

## 🛠️ Pending Implementation Plan
We have an approved-in-principle plan to:
1.  **Sync Model Weights**: Update `experiments.py` to save the "Best Model" from each sweep to `models/sac_trading_bot.zip`.
2.  **Dashboard Resilience**: Update `analytics_dashboard.py` to allow selecting model snapshots and to handle shape mismatches with clear diagnostics.

## 💻 Mac Setup Checklist
- [ ] [ ] **`.env`**: Ensure `GEMINI_API_KEY` is set for the AI Strategic Analyst.
- [ ] [ ] **Data Refreshed**: If the Parquet is missing, run:
  ```bash
  python -c "from src.market_data import get_tech_training_data; get_tech_training_data(refresh=True, include_news=True)"
  ```
- [ ] [ ] **Dependencies**: `pip install -r requirements.txt` (Ensure `tqdm` and `stable-baselines3` are installed).

## 📊 Next Strategic Step
- **"Pressure-v2"**: Reduce timesteps (40k -> 20k) to fight the 24% return gap (overfitting) while keeping the aggressive `reward_direction_scale=1.0` and `bonus_scale=0.25`.

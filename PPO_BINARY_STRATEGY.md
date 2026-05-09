# PPO Binary Architecture: The "Momentum Edge"

## 1. Overview
After extensive testing on mega-cap tech assets (NVDA, AMZN, GOOGL), we have transitioned the production architecture from continuous-action SAC to **Binary-Action PPO**. This shift addresses the "Hold-Bias Collapse" that plagued previous models.

## 2. Core Components
The "Gold Standard" configuration for new tickers:

| Component | Setting | Rationale |
| :--- | :--- | :--- |
| **Algorithm** | **PPO** | Superior stability in discrete-action spaces; less sensitive to noisy reward gradients than SAC. |
| **Action Space** | **Discrete(2)** | Eliminates position-sizing noise. Forces the model to focus on directional conviction (Buy vs. Hold). |
| **Min Hold Bars** | **3** | Suppresses HFT-style whipsaws. Ensures trades align with institutional holding periods and overcomes transaction costs. |
| **Entropy** | **0.05 - 0.08** | High exploration is required to break out of "Hold-Only" local minima in trending markets. |
| **Timesteps** | **60,000+** | Extended training is necessary for policy convergence in the stationary feature space. |

## 3. Validation Results (Stage 1 Pilot)
| Ticker | Alpha vs QQQ | Sharpe | Accuracy | Status |
| :--- | :--- | :--- | :--- | :--- |
| **GOOGL** | **+0.665** | 1.67 | 55.3% | CHAMPION (Seed 13) |
| **AMZN** | **+0.116** | 1.15 | 53.6% | PROMOTED |
| **MU** | **+0.152** | 1.28 | 54.1% | PROMOTED |

## 4. The "Exit Problem" & Refinement
Current models exhibit a **90%+ trade rate**, indicating they are "always long." While profitable in 2024-2026, we are refining the **Exit Logic** via:
1. **Higher `hold_penalty` (0.2 - 0.4)**: Forces the model to justify every bar of exposure.
2. **Confidence Thresholds (0.002 - 0.003)**: Prunes low-conviction entries.

## 5. Cross-Ticker Validation Plan
We are retrofitting the following "legacy" tickers with the PPO-Binary architecture to stabilize their performance:
- [ ] **NVDA**: Compare PPO-Binary vs. SAC-Continuous (Champion Alpha: +0.41).
- [ ] **AMD**: Compare PPO-Binary vs. SAC-Continuous (Champion Alpha: +1.37).
- [ ] **AAPL**: Attempt recovery of the previously "dropped" ticker.

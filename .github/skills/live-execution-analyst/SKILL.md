---
id: live-execution-analyst
name: Live Execution Analyst & Real-World Strategy Auditor
description: Technical framework for auditing, diagnosing, and maintaining real-time inference integrity, data stream alignment, broker execution performance, and cross-repo state verification during live/paper trading.
version: 1.0.0
capabilities:
  - live-feature-drift-detection
  - cold-start-verification
  - temporal-leakage-analysis
  - market-friction-profiling
  - state-contract-validation
---

## Overview

The `live-execution-analyst` skill shifts the repository's focus from offline optimization (sweeps, gate promotion, historical Parquet evaluation) to live production execution. 

When a champion model (e.g., NVDA, AMD, MU) transitions to live execution via the Alpaca API and WebSocket streams, this skill guides the AI agent to systematically detect data drift, timing leakage, architectural friction, and downstream dashboard state contract mismatches. It preserves the mathematical guarantees of the offline environment in adversarial, noisy, real-world market conditions.

---

## Dependencies

To execute this skill, the agent must have access to:
* **Live Configuration:** Environment configuration files (`.env`, `live_config.yaml`) defining Alpaca endpoints, account types (paper vs. live), and WebSocket stream variables.
* **Streaming & Reference Data:** Real-time WebSocket tick logs, the rolling in-memory lookback feature buffer, and the baseline historical Parquet files used during the model’s offline validation phase.
* **Execution & Order Logs:** Historical order placement payloads, execution/fill receipts returned by Alpaca, and raw network telemetry timestamps.
* **State & Payload Contracts:** The cross-repo JSON schemas used by the trading core to push telemetry data to the frontend dashboard.

---

## Technical Workflow

The agent must execute audits across five specialized focus areas:

### 1. Cold-Start Validation & Buffer Enforcement
Before any live inference sequence is cleared to fire orders, the agent must verify the structural state of the rolling lookback buffer.
* **The 252-Bar Rule:** Inspect the system initialization logs to verify that the lookback buffer has ingested a minimum of **252 valid historical daily bars** (or equivalent intraday intervals) before enabling model execution.
* **Pre-load Diagnostics:** Treat any inference attempted with $< 252$ bars as a critical safety violation. Flag systems attempting to pad the buffer with zero-initialized arrays or forward-filled placeholders.

### 2. Live Feature Drift Detection
Live calculation of indicators from highly erratic WebSocket tick streams must perfectly align with offline math. The agent will compare live-computed streaming features against historically computed equivalents:
* **Missing Ticks & Out-of-Sequence Updates:** Verify how the stream aggregator handles irregular time intervals and dropped packets. Ensure missing data is handled safely (e.g., forward-filling values) rather than introducing zero-value structural drops.
* **Overnight Gaps & Session Transitions:** Audit how the feature generator processes the transition from regular market hours (RTH) to extended hours (ETH). Ensure overnight price gaps do not corrupt rolling volatility windows (e.g., ATR, Bollinger Bands).
* **Floating-Point Alignment:** Detect precision degradation caused by iterative streaming updates vs. vectorized offline calculations. Flag any feature where the variance drifts beyond a strict tolerance ceiling:

$$\text{Drift Threshold} > 10^{-6}$$

### 3. Temporal Execution & Delay Auditing
The agent must proactively hunting for execution delay leakage and hidden look-ahead dependencies.
* **Timestamp Delta Mapping:** Compare three precise epoch timestamps for every trade event:
  1. $T_{\text{signal}}$: The exact moment the model completes forward inference.
  2. $T_{\text{route}}$: The exact moment the API order payload hits the network.
  3. $T_{\text{fill}}$: The execution timestamp returned in the Alpaca broker receipt.
* **Leakage Profiling:** Flag look-ahead leakage if any calculation accidentally references a data point where the data timestamp $T_{\text{data}} \ge T_{\text{signal}}$. Profile network and broker queue latency using the total round-trip execution delay:

$$\Delta T_{\text{latency}} = T_{\text{fill}} - T_{\text{signal}}$$

### 4. Friction, Drag & Slippage Accounting
Offline simulation metrics must be continually re-benchmarked against actual market execution costs to stop silent capital decay.
* **Slippage Cost Calculation:** Compute the actual slippage in basis points (bps) for every market order:

$$\text{Slippage (bps)} = \left| \frac{P_{\text{fill}} - P_{\text{signal}}}{P_{\text{signal}}} \right| \times 10,000$$

* **Spread & Borrow Optimization:** Log bid-ask spread widths at the time of execution to track market liquidity impact. For short-side execution, verify that actual Alpaca borrow fees and hard-to-borrow (HTB) rates are fully deducted from live returns, checking them against offline assumptions.

### 5. Dashboard State & Payload Validation
The agent must audit the JSON payload transmission across the microservice layer to ensure frontend synchronization matches state machine reality.
* **Payload Struct Compliance:** Parse the outbound web app messages and strictly enforce compliance against the standard cross-repo JSON signal contract:

```json
{
  "date": "YYYY-MM-DD",
  "ticker": "SYMBOL",
  "action": 0,
  "confidence": 0.8425,
  "exit_fired": false,
  "exit_rule": "none"
}
```

* **ExitManager Reset Isolation:** Perform state-machine path auditing on the `ExitManager` risk layer. The agent must verify that `ExitManager.reset()` is invoked **strictly once** upon a true position-opening event. Flag any bug where tick-by-tick updates cause the tracking variables (like trailing stop watermarks) to reset prematurely during an active trade.

---

## Mandatory Output Format

The agent must structure its diagnostic report in the exact sequence outlined below. Do not combine or skip sections.

### 1. Live Realism Profile

A snapshot of the runtime operating environment.

* **Broker Target:** (e.g., Alpaca Paper / Alpaca Live)
* **Data Provider:** (e.g., Alpaca WebSocket SIP / Polygon.io)
* **Active Ensembles:** List of active tickers (NVDA, AMD, MU) and loaded model hashes.
* **Network Baseline:** Average network ping and API response round-trips in milliseconds.

### 2. Execution Latency & Slip Metrics

A granular table of execution slippage.

* Provide an execution log table displaying Ticker, $\Delta T_{\text{latency}}$ (ms), Slippage (bps), and Spread Width at execution.
* Clear statement highlighting whether current slippage exceeds the offline simulation's slippage penalty parameter.

### 3. Feature Computation Drift Audits

A summary of structural feature drift.

* List of all features showing an MSE drift $> 10^{-6}$ when compared to backtest replays.
* Evaluation of how overnight gaps and session breaks impacted rolling window features.

### 4. State Machine Correctness Check

Validation of service boundary integrity.

* Pass/Fail status of the **252-Bar Cold-Start Validation Rule**.
* Verification proving `ExitManager.reset()` is isolated to new position open signals and is not leaking on continuous live tick evaluations.
* Confirmation of outbound JSON schema conformance.

### 5. Real-World Performance vs. Offline Baseline Comparison

An adversarial look at alpha tracking error.

* Side-by-side comparison of the live trading period's Sharpe ratio, Win Rate, and Max Drawdown against the corresponding slice of the historical validation backtest.
* Identification of divergence trends caused by execution friction or feature drift.

### 6. Execution Pipeline Action Plan

A concrete list of targeted adjustments.

* Categorized, prioritized engineering actions (e.g., **[CRITICAL]**, **[WARNING]**, **[OPTIMIZATION]**) to fix identified stream-handling anomalies, state machine leaks, or latency overruns.

---

## Common Mistakes to Avoid

> ❌ **The Warm-Up Failure:** Allowing live inference to start instantly on model boot using a partial or forward-filled buffer, which skews technical features and corrupts early PPO actions.
> ❌ **Continuous Reset Invalidation:** Writing logic that calls `ExitManager.reset()` or clears state indicators inside the general tick handler loop, blinding trailing stop protections to peak intraday gains.
> ❌ **Ignoring Fill Slippage:** Treating the execution price as equivalent to the target signal price, masking severe alpha decay caused by slow order routing.
> ❌ **Asynchronous Clock Asymmetry:** Calculating live streaming indicators using local system clock timestamps while comparing them against exchange-stamped historical logs, creating invisible look-ahead or lag distortions.

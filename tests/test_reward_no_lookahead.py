"""
Smoke test to verify reward function has NO LOOK-AHEAD BIAS.

This test confirms that:
1. Reward calculation only uses prices at timestep t or earlier
2. No future price information leaks into the reward
3. The directional reward uses realized returns (past to current)
4. Portfolio valuation uses current price, not next price
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.trading_env import TradingEnv


def test_no_future_price_in_reward():
    """Verify reward calculation doesn't use future prices."""
    
    # Create simple test data with predictable price movements
    test_data = pd.DataFrame({
        'Open': [100, 105, 110, 108, 112],
        'High': [102, 107, 112, 110, 115],
        'Low': [99, 104, 109, 107, 111],
        'Close': [101, 106, 111, 109, 113],
        'Volume': [1000, 1100, 1200, 1150, 1250],
    })
    
    env = TradingEnv(
        df=test_data,
        initial_balance=1000,
        reward_direction_scale=1.0,  # Max directional reward to test it
        reward_return_scale=0.0,  # Disable portfolio return for isolation
        reward_hold_penalty_scale=0.0,
        reward_drawdown_penalty_scale=0.0,
        reward_action_bonus_scale=0.0,
        transaction_cost_rate=0.0,
    )
    
    obs, info = env.reset()
    
    print("=" * 60)
    print("REWARD LOOK-AHEAD BIAS TEST")
    print("=" * 60)
    
    # Step 0 -> 1: Price goes from 101 to 106 (+4.95%)
    # If we take Long action at step 0, directional reward should be based on:
    # SAFE: realized return from step 0 to 1 (what we observe AFTER taking action)
    # At step 0, realized_return should be 0 or based on previous step
    
    print("\n[STEP 0] Taking LONG action at price 101")
    obs, reward, terminated, truncated, info = env.step(1)  # Long
    
    print(f"  Current step: {env.current_step}")
    print(f"  Reward total: {reward:.6f}")
    print(f"  Reward direction: {info['reward_direction']:.6f}")
    print(f"  Realized return: {info['realized_return']:.6f}")
    
    # At step 0, realized_return should be 0 (no previous step)
    # or very small (101/100 - 1 = 0.01 if prev exists)
    assert abs(info['realized_return']) < 0.02, \
        f"Step 0 realized_return should be ~0, got {info['realized_return']}"
    
    print("  [OK] Step 0: Uses realized return (not future price)")
    
    # Step 1 -> 2: Price goes from 106 to 111 (+4.72%)
    # At step 1, realized return should be (106/101 - 1) = +4.95%
    # NOT (111/106 - 1) which would be look-ahead
    
    print("\n[STEP 1] Taking LONG action at price 106")
    obs, reward, terminated, truncated, info = env.step(1)  # Long
    
    print(f"  Current step: {env.current_step}")
    print(f"  Reward total: {reward:.6f}")
    print(f"  Reward direction: {info['reward_direction']:.6f}")
    print(f"  Realized return: {info['realized_return']:.6f}")
    
    # Realized return should be (106/101 - 1) ≈ 0.0495 (4.95%)
    expected_realized = (106 / 101) - 1.0
    assert abs(info['realized_return'] - expected_realized) < 0.001, \
        f"Step 1 realized_return should be {expected_realized:.4f}, got {info['realized_return']:.4f}"
    
    # If using next price (111), would get (111/106 - 1) ≈ 0.0472
    future_return = (111 / 106) - 1.0
    assert abs(info['realized_return'] - future_return) > 0.001, \
        f"realized_return should NOT match future return {future_return:.4f}"
    
    print("  [OK] Step 1: Uses realized return (106/101), NOT future return (111/106)")
    
    # Step 2: Test Short position
    print("\n[STEP 2] Taking SHORT action at price 111")
    obs, reward, terminated, truncated, info = env.step(-1)  # Short (Weight -1.0)
    
    print(f"  Current step: {env.current_step}")
    print(f"  Reward direction: {info['reward_direction']:.6f}")
    print(f"  Realized return: {info['realized_return']:.6f}")
    
    # Realized return should be (111/106 - 1) ≈ 0.0472
    expected_realized = (111 / 106) - 1.0
    assert abs(info['realized_return'] - expected_realized) < 0.001, \
        f"Step 2 realized_return should be {expected_realized:.4f}, got {info['realized_return']:.4f}"
    
    # Directional reward for SHORT should be negative when price goes up
    assert info['reward_direction'] < 0, \
        f"Short position with positive realized return should give negative directional reward"
    
    print("  [OK] Step 2: Short position correctly uses realized return")
    
    print("\n" + "=" * 60)
    print("[OK] ALL TESTS PASSED - NO LOOK-AHEAD BIAS DETECTED")
    print("=" * 60)
    print("\nReward function now uses ONLY realized returns.")
    print("Agent learns from past/current prices, NOT future prices.")
    

def test_portfolio_valuation_no_lookahead():
    """Verify portfolio valuation uses current price, not next price."""
    
    test_data = pd.DataFrame({
        'Open': [100, 110, 120],
        'High': [102, 112, 122],
        'Low': [99, 109, 119],
        'Close': [101, 111, 121],
        'Volume': [1000, 1100, 1200],
    })
    
    env = TradingEnv(
        df=test_data,
        initial_balance=1000,
        reward_return_scale=1.0,
        reward_direction_scale=0.0,
        reward_hold_penalty_scale=0.0,
        reward_drawdown_penalty_scale=0.0,
        reward_action_bonus_scale=0.0,
        transaction_cost_rate=0.0,
    )
    
    obs, info = env.reset()
    
    print("\n" + "=" * 60)
    print("PORTFOLIO VALUATION TEST")
    print("=" * 60)
    
    # Take long position at step 0 (price 101)
    print("\n[STEP 0] Long position at price 101")
    obs, reward, terminated, truncated, info = env.step(1)
    
    reward_net_worth_step0 = info['reward_net_worth']
    print(f"  Reward net worth: {reward_net_worth_step0:.2f}")
    
    # The reward_net_worth should be calculated using current price (101), not next price (111)
    # With 1000 balance and ~9 shares at 101, net worth should be ~1000, not ~1100
    assert 950 < reward_net_worth_step0 < 1050, \
        f"Net worth at step 0 should be ~1000, got {reward_net_worth_step0}"
    
    print("  [OK] Portfolio valued at current price (101), not future price (111)")
    
    print("\n" + "=" * 60)
    print("[OK] PORTFOLIO VALUATION TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_no_future_price_in_reward()
    test_portfolio_valuation_no_lookahead()
    print("\n[PASS] ALL SMOKE TESTS PASSED - REWARD FUNCTION IS CLEAN")

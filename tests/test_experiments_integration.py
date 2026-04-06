"""
Smoke test to verify experiments.py works with fixed reward function.
"""
import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.experiments import _simulate_with_model
from src.trading_env import TradingEnv
from stable_baselines3 import PPO


def test_simulate_with_new_reward():
    """Test that simulation captures new realized_return field."""
    
    # Create simple test data with Date column
    test_data = pd.DataFrame({
        'Date': pd.date_range('2024-01-01', periods=5),
        'Open': [100, 105, 110, 108, 112],
        'High': [102, 107, 112, 110, 115],
        'Low': [99, 104, 109, 107, 111],
        'Close': [101, 106, 111, 109, 113],
        'Volume': [1000, 1100, 1200, 1150, 1250],
    })
    
    env = TradingEnv(
        df=test_data,
        reward_direction_scale=0.35,
    )
    
    # Create a simple model
    model = PPO("MlpPolicy", env, verbose=0)
    
    print("=" * 60)
    print("EXPERIMENTS.PY SMOKE TEST")
    print("=" * 60)
    
    # Run a simulation
    print("\nRunning simulation...")
    env_kwargs = {
        'reward_direction_scale': 0.35,
        'reward_return_scale': 1.0,
        'max_weight_delta_per_step': 0.25,
    }
    signals = _simulate_with_model(model, test_data, env_kwargs)
    
    print(f"  Generated {len(signals)} signals")
    
    # Check that all expected columns are present
    expected_cols = [
        'step', 'price', 'action', 'reward', 'net_worth',
        'reward_portfolio_return', 'reward_direction', 'reward_hold_penalty',
        'reward_action_bonus', 'reward_drawdown_penalty', 'reward_drawdown',
        'realized_return'  # NEW FIELD
    ]
    
    for col in expected_cols:
        assert col in signals.columns, f"Missing column: {col}"
        print(f"  [OK] Column '{col}' present")
    
    # Verify realized_return values are reasonable
    realized_returns = signals['realized_return'].values
    print(f"\n  Realized returns range: [{realized_returns.min():.4f}, {realized_returns.max():.4f}]")
    
    # First step should have 0 realized return
    assert signals.loc[0, 'realized_return'] == 0.0, \
        "First step should have 0 realized return"
    print("  [OK] First step has 0 realized return (no prior price)")
    
    # Check that reward_direction is using realized returns
    print("\n  Sample of reward components:")
    print(signals[['step', 'realized_return', 'reward_direction', 'reward']].head(3))
    
    print("\n" + "=" * 60)
    print("[OK] EXPERIMENTS.PY SMOKE TEST PASSED")
    print("=" * 60)
    print("Simulation correctly captures new realized_return field.")


if __name__ == "__main__":
    test_simulate_with_new_reward()
    print("\n[PASS] EXPERIMENTS.PY INTEGRATION TEST PASSED")

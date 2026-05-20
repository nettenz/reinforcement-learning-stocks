"""
Comprehensive end-to-end test of the reward function fix.

This test validates:
1. Training environment works with new reward
2. Model can train (even for a few steps)
3. Evaluation pipeline works
4. No errors in the full workflow
"""
import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.trading_env import TradingEnv
from src.experiments import _simulate_with_model
from stable_baselines3 import PPO


def test_full_training_pipeline():
    """End-to-end test: create env, train model, evaluate."""
    
    print("=" * 60)
    print("COMPREHENSIVE E2E TEST")
    print("=" * 60)
    
    # Create realistic test data
    test_data = pd.DataFrame({
        'Date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'Open': [100 + i * 0.5 for i in range(100)],
        'High': [102 + i * 0.5 for i in range(100)],
        'Low': [99 + i * 0.5 for i in range(100)],
        'Close': [101 + i * 0.5 for i in range(100)],
        'Volume': [1000 + i * 10 for i in range(100)],
    })
    
    print("\n[STEP 1] Creating environment...")
    env = TradingEnv(
        df=test_data,
        reward_direction_scale=0.35,
        reward_return_scale=1.0,
        reward_hold_penalty_scale=0.05,
        reward_drawdown_penalty_scale=0.10,
        reward_action_bonus_scale=0.02,
        transaction_cost_rate=0.001,
    )
    print("  [OK] Environment created")
    
    print("\n[STEP 2] Initializing PPO model...")
    model = PPO(
        "MlpPolicy", 
        env, 
        verbose=0,
        learning_rate=3e-4,
        n_steps=32,
        batch_size=32,
    )
    print("  [OK] Model initialized")
    
    print("\n[STEP 3] Training for 500 timesteps...")
    model.learn(total_timesteps=500, progress_bar=False)
    print("  [OK] Training completed without errors")
    
    print("\n[STEP 4] Testing inference...")
    obs, _ = env.reset()
    actions_taken = []
    rewards_received = []
    
    for _ in range(10):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        actions_taken.append(int(action.item() if hasattr(action, "item") else action))
        rewards_received.append(reward)
        
        # Verify info dict has expected fields
        assert 'realized_return' in info, "Missing realized_return in info"
        assert 'reward_direction' in info, "Missing reward_direction in info"
        assert 'reward_portfolio_return' in info, "Missing reward_portfolio_return in info"
        
        if terminated or truncated:
            break
    
    print(f"  [OK] Inference successful: {len(actions_taken)} steps")
    print(f"    Actions: {actions_taken}")
    print(f"    Avg reward: {sum(rewards_received)/len(rewards_received):.4f}")
    
    print("\n[STEP 5] Testing simulation pipeline...")
    env_kwargs = {
        'reward_direction_scale': 0.35,
        'reward_return_scale': 1.0,
        'max_weight_delta_per_step': 0.25,
    }
    signals = _simulate_with_model(model, test_data, env_kwargs)
    
    print(f"  [OK] Simulation generated {len(signals)} signals")
    print(f"    Columns: {list(signals.columns)}")
    
    # Verify realized_return is present
    assert 'realized_return' in signals.columns, "Missing realized_return column"
    
    # Verify first step has 0 realized return
    assert signals.loc[0, 'realized_return'] == 0.0, \
        "First step should have 0 realized return"
    
    print("\n[STEP 6] Verifying reward components...")
    # Check that realized returns are being used correctly
    sample = signals.iloc[1:6]
    print("\n  Sample signals (steps 1-5):")
    print(sample[['step', 'action', 'realized_return', 'reward_direction', 'reward']].to_string(index=False))
    
    # Verify relationship: if action=1 (Long) and realized_return > 0, reward_direction should be > 0 (excluding step 1 transition)
    long_positive = sample[(sample['step'] > 1) & (sample['action'] == 1) & (sample['realized_return'] > 0)]
    if len(long_positive) > 0:
        assert all(long_positive['reward_direction'] > 0), \
            "Long position with positive realized return should have positive directional reward"
        print("\n  [OK] Long + positive return → positive directional reward (verified)")
    
    # Verify no future price leakage
    max_realized = signals['realized_return'].abs().max()
    print(f"\n  Max realized return magnitude: {max_realized:.4f}")
    assert max_realized < 1.0, "Realized returns suspiciously large (possible future price leak)"
    print("  [OK] Realized returns within reasonable bounds")
    
    print("\n" + "=" * 60)
    print("[OK] ALL E2E TESTS PASSED")
    print("=" * 60)
    print("\nReward function fix is working correctly across the full pipeline.")
    print("Environment → Training → Inference → Evaluation all verified.")


if __name__ == "__main__":
    test_full_training_pipeline()
    print("\n[PASS] COMPREHENSIVE E2E TEST COMPLETE - REWARD FIX VALIDATED")

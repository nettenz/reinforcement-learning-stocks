import random
import numpy as np
import torch
from pathlib import Path
import sys
import json
import pandas as pd

# Ensure project root is on sys.path for src imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ensemble import SparseEnsemble
from src.trading_env import TradingEnv

root = Path('.')
with open(root / 'staging' / 'models' / 'ensemble_config.json') as f:
    cfg = json.load(f)
amd_seeds = cfg['amd']['active_seeds']

lb = pd.read_csv(root / 'data' / 'experiment_leaderboard.csv')
ensemble = SparseEnsemble(str(root / 'data' / 'experiment_leaderboard.csv'))
ensemble.active_seeds_df = lb[(lb['ticker'].str.lower() == 'amd') & (lb['seed'].isin(amd_seeds))].copy()
ensemble.load_top_n_models(n=len(amd_seeds), seed_filter=amd_seeds)

# data
df = pd.read_parquet(root / 'data' / 'tech_training_data_amd_stationary.parquet')
from scripts.backtest_exit_rules import _pick_market_cols
market_cols = _pick_market_cols(df)

env = TradingEnv(
    df.iloc[int(len(df)*0.85):].reset_index(drop=True),
    execution_mode='next_bar',
    include_position_in_observation=True,
    market_feature_columns=market_cols,
)
obs, _ = env.reset()

print('OBS SHAPE', obs.shape)

def set_seeds(s):
    random.seed(s)
    np.random.seed(s)
    try:
        import torch
        torch.manual_seed(s)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(s)
    except Exception:
        pass

print('\n== Per-model deterministic predictions with seeding ==')
seeds_to_try = [0, 1, 42, 2026]
for s in seeds_to_try:
    print(f'\n--- global seed {s} ---')
    set_seeds(s)
    # individual model predictions
    for name, model in ensemble.models.items():
        model_obs = obs[: model.observation_space.shape[0]] if obs.shape[0] >= model.observation_space.shape[0] else np.concatenate([obs, np.zeros(model.observation_space.shape[0]-obs.shape[0])])
        raw, _ = model.predict(model_obs, deterministic=True)
        raw_val = float(raw.item() if hasattr(raw, 'item') else raw)
        print(f'  model {name}: raw={raw_val:+.6f}')

print('\n== Ensemble multiple calls without resetting seed ==')
for i in range(5):
    a,c = ensemble.ensemble_predict(obs, method='voting')
    print(f'  call {i}: action={a}, conf={c}')

print('\n== Ensemble with reseeding before each call ==')
for s in seeds_to_try:
    print(f'\n--- reseed {s} ---')
    set_seeds(s)
    for i in range(3):
        a,c = ensemble.ensemble_predict(obs, method='voting')
        print(f'  call {i}: action={a}, conf={c}')

print('\nDone')

# Count buy votes across VAL and TEST splits
print('\n== Vote counts across VAL and TEST splits ==')
n = len(df)
train_end = int(n * 0.70)
val_end = int(n * 0.85)
val_df = df.iloc[train_end:val_end].reset_index(drop=True)
test_df = df.iloc[val_end:].reset_index(drop=True)

from scripts.backtest_exit_rules import _fit_obs

for name, split in [('VAL', val_df), ('TEST', test_df)]:
    env_split = TradingEnv(split, execution_mode='next_bar', include_position_in_observation=True, market_feature_columns=market_cols)
    obs_s, _ = env_split.reset()
    buy = 0
    total = 0
    for _ in range(max(1, len(split)-1)):
        obs_fit = obs_s
        action, conf = ensemble.ensemble_predict(obs_fit, method='voting')
        if action == 1:
            buy += 1
        total += 1
        obs_s, _, _, _, _ = env_split.step(0)
    print(f'{name}: buy_signals={buy}/{total} ({buy/total:.3f})')

from stable_baselines3 import PPO
from sb3_contrib import MaskablePPO
import zipfile
import json
from pathlib import Path

model_path = Path("/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/model_20260519-230017Z_mu-masked-ppo-v1-tuned_seed3.zip")

print("Checking Zip file contents:")
with zipfile.ZipFile(model_path, 'r') as zip_ref:
    for name in zip_ref.namelist()[:10]:
        print(f"  {name}")
    
    # Try reading data or parameter files
    try:
        data_bytes = zip_ref.read("data")
        # stable-baselines3 uses json/pickle for "data". Let's load the model via SB3 directly
    except Exception as e:
        print("Could not read 'data' file directly:", e)

print("\nLoading model via MaskablePPO:")
try:
    model = MaskablePPO.load(model_path)
    print("Model type:", type(model))
    print("Observation space:", model.observation_space)
    print("Action space:", model.action_space)
    if hasattr(model, "env"):
        print("Has env:", model.env)
except Exception as e:
    print("Error loading model:", e)

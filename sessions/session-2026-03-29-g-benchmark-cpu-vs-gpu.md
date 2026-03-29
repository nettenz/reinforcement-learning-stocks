# Session Handoff — 2026-03-29 (Benchmark: venv CUDA vs CPU)

## Context
Follow-up to the shorting/pipeline stabilization work. Goal was to estimate runtime for a 100k-step experiment and verify whether CPU or GPU is the better execution target on this machine.

## What was completed

### 1) Read prior session context
- Reviewed latest handoff: `sessions/session-2026-03-29-f-shorting-stable.md`.
- Confirmed recommended next run shape: larger timesteps, `--n-envs 4`, optional LR schedule.

### 2) Benchmark run (10k timesteps) with requested settings
Benchmark configuration:

```bash
python src/experiments.py --include-news --seeds 7 --timesteps 10000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.0 --max-runs 1 --n-envs 4 --use-lr-schedule --device <cpu|cuda>
```

- First run outside venv with `--device cuda` failed due to CUDA kernel compatibility (`sm_120`) in that Python environment.
- CPU fallback outside venv succeeded:
  - **10k elapsed:** `19.39s`
  - **100k projection:** `~3.2 min`

### 3) Re-run in project virtualenv (`.venv`)
- Executed benchmark with:
  - `.\.venv\Scripts\python.exe ... --device cuda`
- CUDA run succeeded in venv:
  - **10k elapsed:** `34.74s`
  - **100k projection:** `~5.8 min` (practical range ~6–8 min)

## Key conclusion
- For the current PPO `MlpPolicy` workload, **CPU is faster than CUDA** on this setup.
- Measured ratio: CPU (`19.39s`) vs venv CUDA (`34.74s`) at 10k steps → CPU is ~**1.8x faster**.
- Recommended default for experiment throughput: **`--device cpu --n-envs 4`**.

## Artifacts updated by benchmark
- `data/experiment_leaderboard.csv`
- `data/experiment_reward_leaderboard.csv`
- `data/experiment_summary.json`
- Snapshot files in `data/experiment_snapshots/` from benchmark executions.

## Suggested next step
- Run the intended 100k validation on CPU for fastest wall-clock:

```bash
.\.venv\Scripts\python.exe src/experiments.py --include-news --seeds 7 --timesteps 100000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.0 --max-runs 1 --n-envs 4 --use-lr-schedule --device cpu
```


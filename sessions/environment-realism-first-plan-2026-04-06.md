# Environment Realism First Plan (2026-04-06)

## Scope
This session plan captures the next realism-first execution path after entropy and reward calibration.

Primary objective:
- Determine whether current improvements are genuine or optimistic-simulator artifacts.

Current state summary:
- Entropy refinement improved robustness up to `ent_coef=0.10`.
- Reward calibration (phased) did not jointly solve alpha + stability.
- Behavior/performance mismatch persists.

Decision:
- Pivot to a minimal realism-first batch before additional reward tuning.

---

## Why Realism First
Observed risk profile from latest phase runs:
- `execution_mode=next_bar` is active (good), but fill frictions were optimistic.
- `spread_bps=0.0` and `slippage_bps=0.0` were used.
- `reward_ignore_transaction_cost=1` was active, reducing economic pressure in the learning signal.
- Benchmark alpha remains weak/negative across many runs.

Most likely inflation sources:
1. Zero spread/slippage assumptions.
2. Cost-insensitive reward path.
3. Turnover realism mismatch (weight-change penalty not always reflecting true share turnover).

---

## Realism Batch Design (Minimal, Comparable, Actionable)
Run 3 arms only, with same seeds and model settings.

Hold constant across all arms:
- `ticker=nvda`
- `seeds=7,13,21,42,84,101,123,256,512,777`
- `timesteps=20000`
- `learning_rate=0.0003`
- `gamma=0.99`
- `ent_coef=0.10`
- `reward_mode=sharpe`
- `reward_direction_scale=0.35`
- `reward_return_scale=1.0`
- `reward_hold_penalty_scale=0.10`
- `reward_action_bonus_scale=0.02`
- `reward_turnover_penalty_scale=0.05`
- `reward_drawdown_penalty_scale=0.10`
- `reward_clip=1.0`
- `max_weight_delta_per_step=0.25`
- `execution_mode=next_bar`

Arms:
1. Control (current optimistic baseline)
- `spread_bps=0.0`
- `slippage_bps=0.0`
- `reward_ignore_transaction_cost=true`

2. Realistic fills + cost-aware reward
- `spread_bps=1.0`
- `slippage_bps=1.0`
- `reward_ignore_transaction_cost=false`

3. Stress realism
- `spread_bps=2.0`
- `slippage_bps=2.0`
- `reward_ignore_transaction_cost=false`

---

## Success / Failure Rules
Success:
- Alpha degradation is limited versus control and rank ordering is reasonably stable.
- CV does not explode relative to control.
- Best arm remains economically interpretable.

Failure:
- Alpha collapses when modest friction is introduced.
- Ranking order flips erratically across seeds.
- CV rises materially with no alpha benefit.

If failure occurs:
- Stop further reward-term tuning.
- Continue with deeper realism fixes (turnover-notional penalty mode, borrow fee toggle).

---

## Rollback Rule
If realism arms fail due to tooling/config issues (not model behavior):
- Re-run control arm only to re-validate baseline integrity.
- Keep code changes; they are backward-compatible.
- Do not delete the realism setup; fix the offending flag and re-run.

---

## Leaderboard Comparability Impact
Impact level: Medium

Reason:
- Reward/cost semantics differ between control and realism arms (`reward_ignore_transaction_cost` and fill friction).
- Feature/input space unchanged.
- Compare results within this realism cohort; do not directly pool with prior optimistic cohorts for promotion decisions.

---

## Exact Commands

### 0) Setup
```powershell
Set-Location D:\code\agentic-development\reinforcement-learning-stocks
. .\.venv\Scripts\Activate.ps1
$py = ".\.venv\Scripts\python.exe"
```

### 1) Arm 1: Control (optimistic baseline)
```powershell
& $py src/experiments.py `
  --device cuda `
  --ticker nvda `
  --seeds 7,13,21,42,84,101,123,256,512,777 `
  --timesteps 20000 `
  --learning-rates 0.0003 `
  --gammas 0.99 `
  --ent-coefs 0.10 `
  --threshold 0.002 `
  --horizon 1 `
  --transaction-cost-rate 0.001 `
  --trade-penalty 0.05 `
  --execution-mode next_bar `
  --spread-bps 0.0 `
  --slippage-bps 0.0 `
  --reward-mode sharpe `
  --reward-return-scale 1.0 `
  --reward-pnl-scale 0.00 `
  --reward-direction-scale 0.35 `
  --reward-hold-penalty-scale 0.10 `
  --reward-drawdown-penalty-scale 0.10 `
  --reward-action-bonus-scale 0.02 `
  --reward-turnover-penalty-scale 0.05 `
  --reward-clip 1.0 `
  --reward-ignore-transaction-cost `
  --max-weight-delta-per-step 0.25 `
  --append `
  --run-label nvda-realism-phase-control-ent010
```

### 2) Arm 2: Realistic fills + cost-aware reward
```powershell
& $py src/experiments.py `
  --device cuda `
  --ticker nvda `
  --seeds 7,13,21,42,84,101,123,256,512,777 `
  --timesteps 20000 `
  --learning-rates 0.0003 `
  --gammas 0.99 `
  --ent-coefs 0.10 `
  --threshold 0.002 `
  --horizon 1 `
  --transaction-cost-rate 0.001 `
  --trade-penalty 0.05 `
  --execution-mode next_bar `
  --spread-bps 1.0 `
  --slippage-bps 1.0 `
  --reward-mode sharpe `
  --reward-return-scale 1.0 `
  --reward-pnl-scale 0.00 `
  --reward-direction-scale 0.35 `
  --reward-hold-penalty-scale 0.10 `
  --reward-drawdown-penalty-scale 0.10 `
  --reward-action-bonus-scale 0.02 `
  --reward-turnover-penalty-scale 0.05 `
  --reward-clip 1.0 `
  --no-reward-ignore-transaction-cost `
  --max-weight-delta-per-step 0.25 `
  --append `
  --run-label nvda-realism-phase-realistic-ent010
```

### 3) Arm 3: Stress realism
```powershell
& $py src/experiments.py `
  --device cuda `
  --ticker nvda `
  --seeds 7,13,21,42,84,101,123,256,512,777 `
  --timesteps 20000 `
  --learning-rates 0.0003 `
  --gammas 0.99 `
  --ent-coefs 0.10 `
  --threshold 0.002 `
  --horizon 1 `
  --transaction-cost-rate 0.001 `
  --trade-penalty 0.05 `
  --execution-mode next_bar `
  --spread-bps 2.0 `
  --slippage-bps 2.0 `
  --reward-mode sharpe `
  --reward-return-scale 1.0 `
  --reward-pnl-scale 0.00 `
  --reward-direction-scale 0.35 `
  --reward-hold-penalty-scale 0.10 `
  --reward-drawdown-penalty-scale 0.10 `
  --reward-action-bonus-scale 0.02 `
  --reward-turnover-penalty-scale 0.05 `
  --reward-clip 1.0 `
  --no-reward-ignore-transaction-cost `
  --max-weight-delta-per-step 0.25 `
  --append `
  --run-label nvda-realism-phase-stress-ent010
```

### 4) Quick realism cohort comparison
```bash
awk -F',' 'NR>1 && $3 ~ /nvda-realism-phase-/ {
  arm = ($3 ~ /control/ ? "control" : ($3 ~ /realistic/ ? "realistic" : "stress"));
  c[arm]++; a[arm]+=$45; sh[arm]+=$71; cv[arm]+=$86; r[arm]+=$70
}
END {
  print "arm,count,mean_test_alpha,mean_test_sharpe,mean_test_return,mean_test_cv";
  for (k in c) printf "%s,%d,%.6f,%.6f,%.6f,%.6f\n",k,c[k],a[k]/c[k],sh[k]/c[k],r[k]/c[k],cv[k]/c[k]
}' data/experiment_leaderboard.csv | sort
```

### 5) Generate report
```powershell
$py src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name realism-phase-analysis.md
```

---

## Decision After Batch
- If realism arms preserve alpha and ranking stability: continue narrow reward refinement.
- If realism arms collapse alpha or destabilize CV: pivot fully to realism-first implementation sequence.

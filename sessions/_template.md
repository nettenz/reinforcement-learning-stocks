# Session Handoff — YYYY-MM-DD

## Context
Brief summary of what this session focused on and why.

## What was completed

### 1) Task title
- What changed.
- Why it changed.
- Key result.

### 2) Task title
- What changed.
- Why it changed.
- Key result.

## Files changed
- `path/to/file.py`
- `path/to/another_file.py`

## Gemini CLI delegations
*Use this section when work is delegated to Gemini CLI for parallel execution.*

### Standard Delegation Workflow
**Always start with context reading:**
```text
Please read sessions\[delegation-file].md first to understand the context, then proceed with the specific tasks.
```

### Delegation: [Brief title]
- **Instruction file**: `sessions/gemini-cli-[task]-delegation.md`
- **Goal**: Brief description of the delegated task
- **Status**: [Queued/Running/Completed/Failed]
- **Key deliverables**: What Gemini CLI should produce
- **Integration notes**: How to merge results back into main workflow

## Validation performed
- Commands run:
  - `python tests/test_script.py`
- What passed/failed and any caveats.

## Current state
- What is working now.
- What is partially done.
- Known issues/risks.

## Continue on Windows
1. Pull branch and activate venv.
2. Install dependencies:
   - `python -m pip install -r requirements.txt`
3. Start app/dashboard:
   - `.\run_dashboard.ps1 -Action start -Port 8501`
4. Verify behavior and continue from Next Steps.

## Copilot resume prompt (Windows)
```text
I just resumed on Windows for reinforcement-learning-stocks.
Please read sessions/<latest-session-file>.md first, then continue from "Next steps".
Context:
- I run the dashboard with .\run_dashboard.ps1 -Action start -Port 8501
- Focus area: <fill this in>
- Keep changes cross-platform (Windows + macOS)
Before coding, summarize your understanding in 5 bullets, then implement.
```

## Next steps
- [ ] Next concrete task
- [ ] Next concrete task
- [ ] Next concrete task

## Dashboard Next Steps (standard format)
Use this exact structure whenever dashboard tuning or experiment interpretation is part of the handoff.

### Recommended dashboard settings
- Threshold: `0.0020`
- Prediction horizon: `1`
- Chart window: `2000`

### Actionable next steps (4 bullets)
- [ ] Lock current best run label and compare against the immediate prior baseline snapshot.
- [ ] Run one focused stability validation on expanded seeds before changing multiple hyperparameters.
- [ ] Run one single-variable A/B (for example `ent_coef` or `timesteps`) and compare mean + std, not best seed only.
- [ ] Promote defaults only if test actionable accuracy improves with equal or better stability.

## Commands reference
- Start dashboard: `./run_dashboard.sh start 8501`
- Stop dashboard: `./run_dashboard.sh stop 8501`
- Status: `./run_dashboard.sh status 8501`

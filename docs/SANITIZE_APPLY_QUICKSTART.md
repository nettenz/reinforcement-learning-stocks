# Data Sanitization Tools - Quick Reference

## Overview

Two-tool system for diagnosing and fixing RL trading experiment data quality issues:

1. **sanity_scan.py** (v0.2.0) - Diagnoses problems
2. **sanitize_apply.py** (v0.1.0) - Applies safe fixes (NEW! ✨)

## TL;DR - Quick Start

### Windows PowerShell
```powershell
# Preview what will happen (safe)
.\scripts\run_sanitize.ps1

# Apply mutations
.\scripts\run_sanitize.ps1 -Action execute

# Force (expert mode, skip checks)
.\scripts\run_sanitize.ps1 -Action force
```

### Linux/macOS Bash
```bash
# Preview what will happen (safe)
./scripts/run_sanitize.sh

# Apply mutations
./scripts/run_sanitize.sh execute

# Force (expert mode, skip checks)
./scripts/run_sanitize.sh force
```

### Direct Python
```bash
# Preview (default - no mutations)
python scripts/sanitize_apply.py --root-dir .

# Apply mutations
python scripts/sanitize_apply.py --root-dir . --execute

# Force override
python scripts/sanitize_apply.py --root-dir . --execute --force
```

## Complete Workflow

```bash
# 1️⃣ Diagnose issues
python scripts/sanity_scan.py --root-dir .
# → Creates: reports/sanity_scan_report.json

# 2️⃣ Preview mutations (no changes yet)
python scripts/sanitize_apply.py --root-dir . --dry-run

# 3️⃣ Apply mutations (creates backups first!)
python scripts/sanitize_apply.py --root-dir . --execute

# 4️⃣ Verify clean state
python scripts/sanity_scan.py --root-dir .

# 5️⃣ Keep rollback guide handy
cat docs/ROLLBACK_GUIDE.md
```

## Key Safety Features

✅ **Dry-run by default** - Never mutates without `--execute`  
✅ **Full backups** - Original files preserved forever  
✅ **Idempotency** - Warns on re-run, prevents double-sanitization  
✅ **Checksums** - SHA256 integrity verification  
✅ **Audit trail** - Every action logged with timestamp  
✅ **Rollback guide** - Auto-generated recovery procedures  

## Output Locations

After `--execute`, you'll find:

```
backups/
  sanity_backup_<TIMESTAMP>/    ← Immutable originals
  MANIFEST.json

archives/
  <file>_<TIMESTAMP>.csv        ← Original files + metadata
  MANIFEST.json

quarantine/
  <file>_bad_rows_<TIMESTAMP>.csv    ← Bad rows for audit

metadata/
  sanitization_log.json         ← Full audit trail

docs/
  ROLLBACK_GUIDE.md            ← Recovery procedures

data/
  <file>.csv                    ← CLEANED (bad rows removed)
```

## What Gets Cleaned?

- Experiment leaderboards (with bad metrics/configs)
- Reward leaderboards
- Snapshot CSVs
- Orphaned model references

## Recovery

### Need to restore everything?
```bash
cp backups/sanity_backup_<TIMESTAMP>/* data/
```

### Need specific rows back?
```python
import pandas as pd

# Load cleaned and quarantine
clean = pd.read_csv('data/experiment_leaderboard.csv')
bad = pd.read_csv('quarantine/experiment_leaderboard_bad_rows_<TS>.csv')

# Drop metadata columns
recovered = bad.drop(columns=['issue_code', 'reason', 'removed_at'])

# Restore
restored = pd.concat([clean, recovered], ignore_index=True)
restored.to_csv('data/experiment_leaderboard.csv', index=False)
```

## Documentation

- **User Guide:** `docs/SANITIZE_APPLY_GUIDE.md` (12 KB)
- **Reference:** `SANITIZATION_TOOLS_SUMMARY.md` (11.7 KB)
- **Checklist:** `DELIVERABLES.md` (8.8 KB)
- **Auto-generated:** `docs/ROLLBACK_GUIDE.md` (after execution)

## Common Commands

```bash
# Preview mutations
python scripts/sanitize_apply.py --root-dir .

# Preview with verbose output
python scripts/sanitize_apply.py --root-dir . --dry-run

# Execute (apply mutations)
python scripts/sanitize_apply.py --root-dir . --execute

# Execute with custom paths
python scripts/sanitize_apply.py \
  --root-dir . \
  --data-dir data \
  --report-json reports/sanity_scan_report.json

# Force re-application (dangerous!)
python scripts/sanitize_apply.py --root-dir . --execute --force

# Show help
python scripts/sanitize_apply.py --help
```

## Files Delivered

| File | Purpose |
|------|---------|
| `sanitize_apply.py` | Main mutation engine |
| `test_sanitize_apply.py` | Integration tests (3/3 passing) |
| `run_sanitize.ps1` | PowerShell launcher (Windows) |
| `run_sanitize.sh` | Bash launcher (Linux/macOS) |
| `docs/SANITIZE_APPLY_GUIDE.md` | Complete user guide |
| `SANITIZATION_TOOLS_SUMMARY.md` | Implementation summary |
| `DELIVERABLES.md` | Feature checklist |

## Test Results

✅ **All 3 integration tests passing:**
- Dry-run mode (no mutations occur)
- Execute mode (backups, filtering, metadata)
- Idempotency checks (re-run protection)

Run tests:
```bash
python scripts/test_sanitize_apply.py
```

## Version Info

- **sanitize_apply.py:** v0.1.0
- **Companion:** sanity_scan.py v0.2.0
- **Python:** 3.8+
- **Dependencies:** pandas

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Already applied" | Use `--force` to re-apply (if certain) |
| Need to recover rows | Use recovery procedure from ROLLBACK_GUIDE.md |
| Lost metadata | Check: backups/MANIFEST.json, archives/MANIFEST.json, metadata/sanitization_log.json |
| Want to verify checksums | Compare SHA256 in archives/MANIFEST.json |

## Command Line Reference

```
Usage: python scripts/sanitize_apply.py [options]

Options:
  --root-dir PATH               Repository root (default: .)
  --data-dir PATH              Data directory (default: data)
  --report-json PATH           Scan report (default: reports/sanity_scan_report.json)
  --quarantine-json PATH       Quarantine data (default: reports/sanity_quarantine.json)
  --dry-run                    Preview mode (default: True, no mutations)
  --execute                    Apply mutations
  --remove-orphans             Also archive orphaned models
  --force                      Skip idempotency checks (expert mode)
  --help                       Show full help
```

## Next Steps

1. Read: `docs/SANITIZE_APPLY_GUIDE.md`
2. Test: `python scripts/sanitize_apply.py --dry-run`
3. Execute: `python scripts/sanitize_apply.py --execute`
4. Verify: `python scripts/sanity_scan.py --root-dir .`
5. Archive: `cp docs/ROLLBACK_GUIDE.md docs/ROLLBACK_GUIDE_backup.md`

## Status

✅ **Production Ready**

All features implemented, tested, and documented. Safe to use in production with confidence in full recoverability.

---

For detailed information, see:
- `docs/SANITIZE_APPLY_GUIDE.md` - User guide
- `SANITIZATION_TOOLS_SUMMARY.md` - Technical reference
- `DELIVERABLES.md` - Feature checklist

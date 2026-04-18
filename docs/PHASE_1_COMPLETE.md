# Sanity Scan Phase 1 Complete ✅

## Version: 0.2.0

### Implementation Summary

**Phase 1** focused on **detection only** — no mutations to your data.

#### ✅ All 7 Phase 1 Todos Completed

| Feature | Status | Details |
|---------|--------|---------|
| Snapshot CSV scanning | ✅ | Scans `data/experiment_snapshots/*.csv` |
| JSON artifact validation | ✅ | Validates `reports/*.json` for corruption |
| Downstream dependency scanning | ✅ | Finds scripts reading leaderboards (13 found) |
| Quarantine file generation | ✅ | Generates `reports/sanity_quarantine.json` |
| Exact recommendations | ✅ | Delete/archive commands per bad row |
| Optional --apply flag | ✅ | `--apply dry-run` (default) or `execute` |
| Report schema refactor | ✅ | Enhanced JSON with new sections |

---

## Output Files Generated

### 1. **reports/sanity_scan_report.json** (26 MB)
Complete structured report with:
- `scan_metadata` — version, timestamp, apply mode
- `artifacts` — all main leaderboards with issues
- `snapshots` — experiment_snapshots/*.csv analysis
- `orphaned_models` — 1,057 orphaned model files
- `downstream_dependencies` — 13 scripts that read leaderboards
- `json_validation` — corrupted JSON check results
- `quarantine_rows` — structured list of rows to remove (0 currently)
- `all_issues` — detailed issue array with recommendations
- `summary` — aggregate counts

### 2. **reports/sanity_scan_summary.md** (4 MB)
Human-readable markdown with high-level findings.

### 3. **reports/sanity_quarantine.json** (180 B)
Metadata for rows to quarantine — ready for Phase 2 apply script.

---

## Key Metrics

```
High-Severity Issues:          4 (all mixed_run_families)
Rows to Sanitize:              4
Orphaned Models (safe delete): 1,057
Scripts Needing Review:        13
JSON Validation Issues:        0 ✓
Snapshot Files Scanned:        564
```

---

## Current Data Status

✅ **NO DATA MUTATIONS** — all original files untouched
- ✅ data/experiment_leaderboard.csv (360 rows, readable)
- ✅ data/experiment_reward_leaderboard.csv (readable)
- ✅ data/experiment_leaderboard_history.csv (readable)
- ✅ data/experiment_reward_leaderboard_history.csv (readable)

⚠️ **Issues Detected (Review Only)**
- Mixed experiment families in all 4 leaderboards
- 1,057 orphaned models waiting for cleanup decision

---

## How to Use v0.2.0

### Dry-Run (Safe, shows what would happen)
```bash
python scripts/sanity_scan.py --root-dir . --apply dry-run
```

### Full Report Review
1. Open `reports/sanity_scan_report.json` (structured data)
2. Read `reports/sanity_scan_summary.md` (human summary)
3. Check `reports/sanity_quarantine.json` (rows to remove)

### Next Steps: Phase 2
Once you review and approve, use `sanitize_apply.py` to:
- Back up originals (backups/)
- Move bad rows to quarantine/
- Archive originals (archives/)
- Remove orphaned models (optional)
- Regenerate clean leaderboards

---

## Safety Guarantee

**Cautious Approach (User Selected):**
- ✅ Scanner generates recommendations (read-only)
- ✅ User reviews report before any mutation
- ✅ Apply script requires explicit `--apply=execute` flag
- ✅ Backups kept forever (rollback-ready)
- ✅ Quarantine preserves bad rows (audit trail)

---

## Next: Phase 2 - Sanitize Apply Script

Ready to build `sanitize_apply.py` to execute mutations safely?

Topics for Phase 2:
1. Backup strategy (timestamps + checksums)
2. Regenerate clean leaderboards
3. Quarantine row storage
4. Archive originals
5. Optional orphaned model cleanup
6. Idempotent safety
7. Rollback documentation

**Status: 7/17 todos complete (Phase 1 done, Phase 2 pending)**

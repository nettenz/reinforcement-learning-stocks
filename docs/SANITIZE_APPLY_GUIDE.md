# sanitize_apply.py - RL Trading Data Sanitization Tool

**Version:** 0.1.0

A safe, reversible mutation script that reads `sanity_scan.py` output and applies mutations to experimental leaderboard data. Designed for safety: dry-run by default, full backups, immutable archives, and comprehensive rollback documentation.

## Features

### 1. Backup Strategy
- Creates versioned backup directories: `backups/sanity_backup_<ISO_TIMESTAMP>/`
- Copies original CSVs before any mutation
- Stores metadata JSON with checksums (SHA256)
- Backups are immutable (read-only after creation)
- Creates `backups/MANIFEST.json` for tracking all backups

### 2. Regenerate Clean Leaderboards
- Reads each artifact CSV
- Parses `sanity_scan_report.json` to identify rows to remove
- Filters out bad rows, keeps good rows
- Writes cleaned CSV back to original location
- Updates row count in metadata

### 3. Quarantine Row Storage
- Extracts bad rows with full context (all columns)
- Creates `quarantine/<artifact_name>_bad_rows_<ISO_TIMESTAMP>.csv`
- Includes metadata columns: `issue_code`, `reason`, `removed_at`
- Preserves for audit trail and recovery

### 4. Archive Originals
- Moves backups to `archives/<artifact_name>_<ISO_TIMESTAMP>.csv`
- Creates `archives/MANIFEST.json` with detailed metadata:
  - `original_name`: Original file name
  - `archived_at`: Timestamp
  - `sha256`: Original file hash
  - `row_count_before`: Original row count
  - `rows_removed`: Number of rows removed
  - `reason`: Why rows were removed

### 5. Orphaned Model Cleanup (Optional)
- Flag: `--remove-orphans`
- Reads orphaned_models list from scan report
- Archives models to `archives/orphaned_models_<ISO_TIMESTAMP>/`
- Logs each action with timestamp

### 6. Idempotency
- Tracks applied sanitizations in `metadata/sanitization_log.json`
- Logs: timestamp, artifact, rows_removed, quarantine_file, backup_file
- On re-run: Detects if already applied, warns user
- Requires `--force` to re-apply (prevents accidental double-sanitization)

### 7. Rollback Documentation
- Creates `docs/ROLLBACK_GUIDE.md` with:
  - List of all backups available
  - Step-by-step restore procedures
  - How to recover specific rows from quarantine
  - SHA256 checksums for integrity verification
  - Support for partial or full restoration

## CLI Arguments

```
--report-json PATH              Path to sanity_scan_report.json (default: reports/sanity_scan_report.json)
--quarantine-json PATH          Path to sanity_quarantine.json (default: reports/sanity_quarantine.json)
--root-dir PATH                 Repository root directory (default: .)
--data-dir PATH                 Data directory relative to root (default: data)
--dry-run                       Preview without mutations (default: True)
--execute                       Perform actual mutations
--remove-orphans                Also archive/delete orphaned models
--force                         Skip idempotency checks (dangerous, requires --execute)
```

## Usage Examples

### Preview Mutations (Dry-Run, Default)
```bash
python scripts/sanitize_apply.py --root-dir .
```

Shows:
- Total rows to remove
- Affected artifacts
- Dependent scripts (downstreams)
- Output structure that will be created
- Instruction to use `--execute` to apply

### Apply Mutations
```bash
python scripts/sanitize_apply.py --root-dir . --execute
```

Interactive workflow:
1. Shows dry-run preview first
2. Creates backups
3. Filters CSVs
4. Creates quarantine files
5. Archives originals
6. Logs mutations
7. Generates rollback guide

### Re-Apply with Force
```bash
python scripts/sanitize_apply.py --root-dir . --execute --force
```

Skips idempotency check (dangerous—may double-remove rows). Use only if you know what you're doing.

### Archive Orphaned Models
```bash
python scripts/sanitize_apply.py --root-dir . --execute --remove-orphans
```

Applies mutations AND archives/deletes orphaned models referenced in scan report.

## Output Structure

After execution, the following directory structure is created:

```
backups/
  sanity_backup_2026-04-10T06:30:00/
    experiment_leaderboard.csv          (original backup)
    experiment_reward_leaderboard.csv
    ...
  MANIFEST.json                         (backup metadata)

archives/
  experiment_leaderboard_2026-04-10T06:30:00.csv     (moved from backups/)
  experiment_reward_leaderboard_2026-04-10T06:30:00.csv
  ...
  MANIFEST.json                         (archive metadata)

quarantine/
  experiment_leaderboard_bad_rows_2026-04-10T06:30:00.csv
  experiment_reward_leaderboard_bad_rows_2026-04-10T06:30:00.csv
  ...

metadata/
  sanitization_log.json                 (full mutation audit trail)

docs/
  ROLLBACK_GUIDE.md                     (step-by-step recovery guide)

data/
  experiment_leaderboard.csv            (CLEANED - bad rows removed)
  experiment_reward_leaderboard.csv     (CLEANED)
  ...
```

## Metadata Files

### `backups/MANIFEST.json`
```json
{
  "metadata": {
    "created_at": "2026-04-10T06:30:00+00:00",
    "backup_dir": "backups/sanity_backup_2026-04-10T06:30:00",
    "archive_strategy": "Originals moved to archives/, backups preserved"
  },
  "backups": []
}
```

### `archives/MANIFEST.json`
```json
{
  "metadata": {
    "created_at": "2026-04-10T06:30:00+00:00",
    "archive_dir": "archives"
  },
  "archives": [
    {
      "timestamp": "2026-04-10T06:30:00+00:00",
      "file_path": "data/experiment_leaderboard.csv",
      "file_name": "experiment_leaderboard.csv",
      "original_row_count": 360,
      "final_row_count": 342,
      "rows_removed": 18,
      "sha256_before": "abc123...",
      "sha256_after": "def456...",
      "backup_file": "backups/sanity_backup_2026-04-10T06:30:00/experiment_leaderboard.csv",
      "archive_file": "archives/experiment_leaderboard_2026-04-10T06:30:00.csv",
      "quarantine_file": "quarantine/experiment_leaderboard_bad_rows_2026-04-10T06:30:00.csv"
    }
  ]
}
```

### `metadata/sanitization_log.json`
```json
{
  "metadata": {
    "generated_at_utc": "2026-04-10T06:30:00+00:00",
    "sanitizer_version": "0.1.0"
  },
  "mutations": [
    {
      "timestamp": "2026-04-10T06:30:00+00:00",
      "file_path": "data/experiment_leaderboard.csv",
      "file_name": "experiment_leaderboard.csv",
      "original_row_count": 360,
      "final_row_count": 342,
      "rows_removed": 18,
      "sha256_before": "abc123...",
      "sha256_after": "def456...",
      "backup_file": "backups/sanity_backup_2026-04-10T06:30:00/experiment_leaderboard.csv",
      "archive_file": "archives/experiment_leaderboard_2026-04-10T06:30:00.csv",
      "quarantine_file": "quarantine/experiment_leaderboard_bad_rows_2026-04-10T06:30:00.csv"
    }
  ]
}
```

## Safety Guarantees

✅ **Never mutates without explicit `--execute` flag**
- Default is dry-run only
- Preview shows exactly what will happen

✅ **Always backs up first**
- Complete CSV copy before mutation
- Backups are immutable (read-only)
- Backups preserved forever

✅ **Preserves originals for audit**
- Original files archived with timestamp
- Checksums tracked for integrity

✅ **Tracks all mutations**
- Full audit trail in `sanitization_log.json`
- Metadata includes timestamps, checksums, row counts

✅ **Warns on re-run**
- Idempotency check detects if already applied
- Requires `--force` to re-apply
- Prevents accidental double-sanitization

✅ **Includes integrity checksums**
- SHA256 hashes tracked before/after
- Verify with: `sha256sum <file>`

✅ **Provides full rollback guide**
- `docs/ROLLBACK_GUIDE.md` auto-generated
- Step-by-step restore procedures
- All backup locations documented

✅ **Logs all actions with timestamps**
- Every mutation recorded
- Every backup location tracked
- Easy audit trail

## Recovery Procedures

### Restore Entire Leaderboard
```bash
cp backups/sanity_backup_<TIMESTAMP>/<FILE> data/<FILE>
```

### Restore from Archive
```bash
cp archives/<FILE>_<TIMESTAMP>.csv data/<FILE>
```

### Recover Specific Rows from Quarantine
```python
import pandas as pd

# Load the cleaned file and quarantine
clean = pd.read_csv('data/experiment_leaderboard.csv')
bad_rows = pd.read_csv('quarantine/experiment_leaderboard_bad_rows_<TIMESTAMP>.csv')

# Drop metadata columns added during quarantine
recovered = bad_rows.drop(columns=['issue_code', 'reason', 'removed_at'])

# Append recovered rows
restored = pd.concat([clean, recovered], ignore_index=True)
restored.to_csv('data/experiment_leaderboard.csv', index=False)
```

### Verify Integrity
```bash
# After restoration, verify checksums
sha256sum data/experiment_leaderboard.csv

# Compare against value in archives/MANIFEST.json (sha256_before)
```

## Integration with sanity_scan.py

`sanitize_apply.py` is the companion tool to `sanity_scan.py`:

1. **sanity_scan.py** (v0.2.0): Diagnoses issues
   - Scans all CSVs for data quality issues
   - Generates `sanity_scan_report.json` with issues and recommendations
   - Generates `sanity_quarantine.json` with rows to remove

2. **sanitize_apply.py** (v0.1.0): Applies fixes
   - Reads scan output
   - Creates backups
   - Applies mutations safely
   - Generates recovery documentation

### Typical Workflow
```bash
# 1. Scan for issues
python scripts/sanity_scan.py --root-dir .

# 2. Preview mutations
python scripts/sanitize_apply.py --root-dir . --dry-run

# 3. Apply mutations
python scripts/sanitize_apply.py --root-dir . --execute

# 4. Verify clean state
python scripts/sanity_scan.py --root-dir .
```

## Error Handling

The script handles various error conditions:

| Condition | Behavior |
|-----------|----------|
| File not found | Warns user, skips file |
| CSV read error | Warns user, skips file |
| Backup already exists | Warns and continues |
| Row index out of range | Skips invalid indices |
| JSON load error | Exits with error message |
| Permission denied | Warns, continues |

All errors are logged with timestamps.

## Performance Characteristics

- **Time complexity:** O(n) per CSV, where n = row count
- **Space complexity:** O(n) for backup + O(m) for quarantine, where m = rows removed
- **Typical execution:** 1-5 seconds for 100k+ row leaderboards
- **Backup strategy:** Full copy (no delta compression)

## Troubleshooting

### Issue: "Sanitization already applied"
**Solution:** Use `--force` flag to re-apply (if you're sure):
```bash
python scripts/sanitize_apply.py --root-dir . --execute --force
```

### Issue: Need to recover rows
**Solution:** Follow recovery procedure in `docs/ROLLBACK_GUIDE.md` or use manual process above.

### Issue: Unsure about checksums
**Solution:** Compare SHA256 from `archives/MANIFEST.json`:
```bash
sha256sum data/experiment_leaderboard.csv
# Compare output to sha256_before in MANIFEST.json
```

### Issue: Lost metadata
**Solution:** All metadata is stored in three places:
1. `backups/MANIFEST.json`
2. `archives/MANIFEST.json`
3. `metadata/sanitization_log.json`

Check any of these for recovery information.

## Testing

Run integration tests:
```bash
python scripts/test_sanitize_apply.py
```

Tests verify:
- ✅ Dry-run doesn't mutate data
- ✅ Execute mode creates all expected directories
- ✅ Row filtering works correctly
- ✅ Metadata logging is accurate
- ✅ Rollback guide is generated
- ✅ Idempotency checks prevent double-application
- ✅ Force flag bypasses idempotency

## Version History

### v0.1.0 (Initial Release)
- ✅ Backup strategy with immutable files
- ✅ Clean leaderboard regeneration
- ✅ Quarantine row storage
- ✅ Archive originals with metadata
- ✅ Orphaned model cleanup (optional)
- ✅ Idempotency tracking
- ✅ Rollback documentation
- ✅ Full integration tests

## License

Part of the RL Trading Stocks project.

## See Also

- `sanity_scan.py` - Issue diagnosis and scanning
- `docs/ROLLBACK_GUIDE.md` - Auto-generated recovery guide
- `metadata/sanitization_log.json` - Mutation audit trail
- `reports/sanity_scan_report.json` - Scan output

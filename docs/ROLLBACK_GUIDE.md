# Rollback Guide - Data Sanitization

Generated: 2026-05-19T23:38:36.293485+00:00
Sanitizer Version: 0.1.0

## Overview

This guide documents how to roll back data sanitization mutations.
All original data is backed up in `backups/` and can be restored.

## Available Backups

### experiment_leaderboard_history.csv

- **File:** `data/experiment_leaderboard_history.csv`
- **Timestamp:** 2026-05-19T23:38:36.245294+00:00
- **Original Rows:** 593
- **Rows Removed:** 114
- **Final Rows:** 479
- **Backup:** `backups/sanity_backup_2026-05-19T233836+0000/experiment_leaderboard_history.csv`
- **Quarantine:** `/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/quarantine/experiment_leaderboard_history_bad_rows_2026-05-19T233836+0000.csv`
- **Integrity (SHA256)**
  - Before: `8e6d5549e678091f9c189007ee9f3e486ffff9573959991c3f2f5135738cca7d`
  - After: `db5444d92a27787b082eeebd1997f75a1d68111088155dc4451985e8c5f2c5cd`

### experiment_reward_leaderboard_history.csv

- **File:** `data/experiment_reward_leaderboard_history.csv`
- **Timestamp:** 2026-05-19T23:38:36.293152+00:00
- **Original Rows:** 593
- **Rows Removed:** 221
- **Final Rows:** 372
- **Backup:** `backups/sanity_backup_2026-05-19T233836+0000/experiment_reward_leaderboard_history.csv`
- **Quarantine:** `/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/quarantine/experiment_reward_leaderboard_history_bad_rows_2026-05-19T233836+0000.csv`
- **Integrity (SHA256)**
  - Before: `a587f2bdf36a53c14761cf7c45be680762b34164aed504e4333f240121ca5fac`
  - After: `4faea07a1fcf1bd6625a873915d39949c7828a7674938b1215b1350ce190402d`

## Restore Procedure

### Option 1: Restore Single File

```bash
cp backups/sanity_backup_<TIMESTAMP>/<FILE> data/<FILE>
```

### Option 2: Full Restoration

```bash
# Identify the most recent backup
ls -td backups/sanity_backup_* | head -1

# Restore all files
cp backups/sanity_backup_<TIMESTAMP>/* data/
```

### Option 3: Recover Specific Rows from Quarantine

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

## Integrity Verification

Verify file integrity using SHA256 checksums:

```bash
sha256sum backups/sanity_backup_<TIMESTAMP>/<FILE>
```

Compare against values listed above.

## Orphaned Models

The following 2243 models were orphaned and archived:

- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233129Z_nvda-intraday-5m-baseline-20k_seed7_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233232Z_nvda-intraday-5m-baseline-20k_seed13_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233335Z_nvda-intraday-5m-baseline-20k_seed21_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233439Z_nvda-intraday-5m-baseline-20k_seed42_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233544Z_nvda-intraday-5m-baseline-20k_seed84_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233649Z_nvda-intraday-5m-baseline-20k_seed101_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233756Z_nvda-intraday-5m-baseline-20k_seed123_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-233901Z_nvda-intraday-5m-baseline-20k_seed256_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-234006Z_nvda-intraday-5m-baseline-20k_seed512_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m/model_20260413-234110Z_nvda-intraday-5m-baseline-20k_seed777_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-002701Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed7_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-002817Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed13_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-002928Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed21_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003039Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed42_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003149Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed84_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003301Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed101_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003413Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed123_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003523Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed256_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003637Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed512_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- `{'path': '/Users/nettenz/Projects/agentic-dev/reinforcement-learning-stocks/data/experiment_snapshots/intraday_5m_batch_a/model_20260414-003748Z_nvda-intraday-5m-A-thr0p001-h3-20k_seed777_5m.zip', 'action_class': 'safe_delete', 'message': 'Model artifact is not referenced by scanned CSV rows.'}`
- ... and 2223 more

## Metadata Log

Full mutation metadata is stored in `metadata/sanitization_log.json`.
Check this file for complete audit trail of all mutations.

## Support

For issues or questions:
1. Check `metadata/sanitization_log.json` for mutation details
2. Verify backup integrity with SHA256 checksums
3. Review `backups/MANIFEST.json` for backup locations
4. Review `archives/MANIFEST.json` for archived data locations
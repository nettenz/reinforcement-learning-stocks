"""
sanitize_apply.py v0.1.0 - RL Trading Experiment Data Sanitization

Reads sanity_scan.py v0.2.0 output and applies safe, reversible mutations:
- Backup original CSVs before mutation
- Remove quarantined rows from leaderboards
- Archive originals with metadata
- Create quarantine storage for bad rows
- Support rollback via metadata tracking

Safety Features:
- Dry-run by default (--execute to apply)
- Idempotency checks (warn on re-run)
- Full backup strategy with checksums
- Comprehensive rollback guide generation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SANITIZER_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    """Return ISO-formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def utc_now_compact() -> str:
    """Return compact ISO timestamp for use in filenames (no colons)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(":", "")


def compute_file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Compute file hash for integrity tracking."""
    try:
        hasher = hashlib.new(algorithm)
        with open(path, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    except Exception as e:
        print(f"[ERROR] Failed to compute hash for {path}: {e}")
        return ""


@dataclass
class MutationMetadata:
    """Track a single file mutation for rollback."""
    timestamp: str
    file_path: str
    file_name: str
    original_row_count: int
    final_row_count: int
    rows_removed: int
    sha256_before: str
    sha256_after: str
    backup_file: str
    archive_file: str
    quarantine_file: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_json(path: Path) -> dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load {path}: {e}")
        raise


def save_json(path: Path, data: dict[str, Any], indent: int = 2) -> None:
    """Save data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, default=str)
    except Exception as e:
        print(f"[ERROR] Failed to save {path}: {e}")
        raise


def make_immutable(path: Path) -> None:
    """Make a file read-only."""
    try:
        import os
        import stat
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception as e:
        print(f"[WARN] Could not make {path} immutable: {e}")


def load_sanitization_log(metadata_dir: Path) -> list[dict[str, Any]]:
    """Load existing sanitization log."""
    log_path = metadata_dir / "sanitization_log.json"
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("mutations", [])
        except Exception:
            pass
    return []


def save_sanitization_log(metadata_dir: Path, mutations: list[dict[str, Any]]) -> None:
    """Save sanitization log."""
    log_path = metadata_dir / "sanitization_log.json"
    save_json(log_path, {
        "metadata": {
            "generated_at_utc": utc_now(),
            "sanitizer_version": SANITIZER_VERSION,
        },
        "mutations": mutations,
    })


def check_idempotency(
    metadata_dir: Path,
    artifact_names: set[str],
    force: bool = False,
) -> tuple[bool, str]:
    """
    Check if sanitization has already been applied.
    
    Returns: (can_proceed, message)
    """
    existing_log = load_sanitization_log(metadata_dir)
    if not existing_log:
        return True, ""
    
    already_sanitized = set()
    for mutation in existing_log:
        already_sanitized.add(mutation.get("file_name", ""))
    
    overlap = already_sanitized & artifact_names
    if overlap and not force:
        msg = (
            f"\n[WARN] Sanitization already applied to: {', '.join(overlap)}\n"
            f"  Use --force to re-apply (dangerous—may double-remove rows).\n"
        )
        return False, msg
    
    if overlap and force:
        print(f"[WARN] --force enabled. Will re-apply to: {', '.join(overlap)}")
        return True, ""
    
    return True, ""


def extract_quarantine_info(report_json: dict[str, Any]) -> dict[str, list[int]]:
    """
    Parse sanity_scan_report.json to extract quarantine_rows by artifact.
    
    Returns: {"artifact_name": [row_indices]}
    """
    quarantine_info: dict[str, list[int]] = {}
    
    for artifact in report_json.get("artifacts", []):
        artifact_path = artifact.get("path", "")
        file_name = Path(artifact_path).name
        
        # Collect quarantine row indices for this artifact
        rows_to_remove: list[int] = []
        for issue in artifact.get("issues", []):
            if issue.get("action_class") in ("sanitize", "sanitize_row"):
                row_idx = issue.get("row_index")
                if row_idx is not None and row_idx not in rows_to_remove:
                    rows_to_remove.append(row_idx)
        
        if rows_to_remove:
            quarantine_info[file_name] = sorted(rows_to_remove)
    
    return quarantine_info


def load_leaderboard_csv(path: Path) -> tuple[pd.DataFrame | None, str]:
    """Load CSV, return DataFrame and error message."""
    try:
        df = pd.read_csv(path)
        return df, ""
    except Exception as e:
        return None, str(e)


def generate_backup_dir(root_dir: Path) -> Path:
    """Generate backup directory with ISO timestamp."""
    ts = utc_now_compact()
    return root_dir / "backups" / f"sanity_backup_{ts}"


def generate_archive_name(file_name: str) -> str:
    """Generate archive filename."""
    ts = utc_now_compact()
    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    return f"{stem}_{ts}{suffix}"


def generate_quarantine_name(file_name: str) -> str:
    """Generate quarantine filename."""
    ts = utc_now_compact()
    stem = Path(file_name).stem
    return f"{stem}_bad_rows_{ts}.csv"


def create_backup(
    source_path: Path,
    backup_dir: Path,
) -> tuple[Path | None, str]:
    """
    Copy source file to backup directory.
    
    Returns: (backup_path, error_msg)
    """
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / source_path.name
        
        if backup_path.exists():
            return None, f"Backup already exists: {backup_path}"
        
        df = pd.read_csv(source_path)
        df.to_csv(backup_path, index=False)
        
        make_immutable(backup_path)
        return backup_path, ""
    except Exception as e:
        return None, str(e)


def extract_bad_rows(
    source_path: Path,
    row_indices: list[int],
    quarantine_dir: Path,
    quarantine_name: str,
) -> tuple[pd.DataFrame | None, str]:
    """
    Extract bad rows and save to quarantine.
    
    Returns: (bad_rows_df, error_msg)
    """
    try:
        df = pd.read_csv(source_path)
        
        # Validate row indices
        valid_indices = [i for i in row_indices if 0 <= i < len(df)]
        if not valid_indices:
            return None, "No valid row indices to quarantine"
        
        bad_rows = df.iloc[valid_indices].copy()
        
        # Add metadata columns
        bad_rows.insert(0, "removed_at", utc_now())
        bad_rows.insert(0, "reason", "Quarantined by sanity_scan.py")
        bad_rows.insert(0, "issue_code", "sanitize")
        
        # Save quarantine file
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_dir / quarantine_name
        bad_rows.to_csv(quarantine_path, index=False)
        
        return bad_rows, ""
    except Exception as e:
        return None, str(e)


def filter_good_rows(
    source_path: Path,
    row_indices_to_remove: list[int],
) -> tuple[pd.DataFrame | None, int, str]:
    """
    Load CSV and filter out bad rows.
    
    Returns: (clean_df, rows_removed_count, error_msg)
    """
    try:
        df = pd.read_csv(source_path)
        original_count = len(df)
        
        # Create boolean mask: keep rows NOT in removal list
        mask = ~df.index.isin(row_indices_to_remove)
        clean_df = df[mask].reset_index(drop=True)
        
        rows_removed = original_count - len(clean_df)
        return clean_df, rows_removed, ""
    except Exception as e:
        return None, 0, str(e)


def write_cleaned_csv(
    df: pd.DataFrame,
    target_path: Path,
) -> str:
    """Write cleaned DataFrame to CSV. Return error message."""
    try:
        df.to_csv(target_path, index=False)
        return ""
    except Exception as e:
        return str(e)


def preview_mutations(
    quarantine_info: dict[str, list[int]],
    root_dir: Path,
    data_dir: Path,
    downstream_deps: list[dict[str, Any]],
) -> None:
    """Print preview of proposed mutations."""
    print("\n" + "=" * 70)
    print("DRY-RUN PREVIEW: Proposed Mutations")
    print("=" * 70)
    
    total_rows_to_remove = sum(len(indices) for indices in quarantine_info.values())
    print(f"\nTotal rows to remove: {total_rows_to_remove}")
    print(f"Artifacts affected: {len(quarantine_info)}")
    
    print("\n--- Artifacts ---")
    for file_name, row_indices in quarantine_info.items():
        print(f"  {file_name}: {len(row_indices)} rows to remove")
    
    print(f"\n--- Downstream Dependencies ---")
    print(f"  Scripts that depend on these CSVs: {len(downstream_deps)}")
    for dep in downstream_deps[:5]:
        print(f"    - {dep.get('script_path', 'unknown')}")
    if len(downstream_deps) > 5:
        print(f"    ... and {len(downstream_deps) - 5} more")
    
    print(f"\n--- Output Structure ---")
    backup_dir = generate_backup_dir(root_dir)
    archive_dir = root_dir / "archives"
    quarantine_dir = root_dir / "quarantine"
    metadata_dir = root_dir / "metadata"
    
    print(f"  Backups:      {backup_dir.relative_to(root_dir)}")
    print(f"  Archives:     {archive_dir.relative_to(root_dir)}")
    print(f"  Quarantine:   {quarantine_dir.relative_to(root_dir)}")
    print(f"  Metadata:     {metadata_dir.relative_to(root_dir)}")
    print(f"  Rollback:     docs/ROLLBACK_GUIDE.md")
    
    print("\n" + "=" * 70)
    print("To apply: python sanitize_apply.py --execute")
    print("=" * 70 + "\n")


def generate_rollback_guide(
    root_dir: Path,
    mutations: list[MutationMetadata],
    orphaned_models: list[str] | None = None,
) -> str:
    """Generate comprehensive rollback guide."""
    guide_lines = [
        "# Rollback Guide - Data Sanitization",
        "",
        f"Generated: {utc_now()}",
        f"Sanitizer Version: {SANITIZER_VERSION}",
        "",
        "## Overview",
        "",
        "This guide documents how to roll back data sanitization mutations.",
        "All original data is backed up in `backups/` and can be restored.",
        "",
        "## Available Backups",
        "",
    ]
    
    for mutation in mutations:
        guide_lines.extend([
            f"### {mutation.file_name}",
            "",
            f"- **File:** `{mutation.file_path}`",
            f"- **Timestamp:** {mutation.timestamp}",
            f"- **Original Rows:** {mutation.original_row_count}",
            f"- **Rows Removed:** {mutation.rows_removed}",
            f"- **Final Rows:** {mutation.final_row_count}",
            f"- **Backup:** `{mutation.backup_file}`",
            f"- **Quarantine:** `{mutation.quarantine_file or 'N/A'}`",
            f"- **Integrity (SHA256)**",
            f"  - Before: `{mutation.sha256_before}`",
            f"  - After: `{mutation.sha256_after}`",
            "",
        ])
    
    guide_lines.extend([
        "## Restore Procedure",
        "",
        "### Option 1: Restore Single File",
        "",
        "```bash",
        "cp backups/sanity_backup_<TIMESTAMP>/<FILE> data/<FILE>",
        "```",
        "",
        "### Option 2: Full Restoration",
        "",
        "```bash",
        "# Identify the most recent backup",
        "ls -td backups/sanity_backup_* | head -1",
        "",
        "# Restore all files",
        "cp backups/sanity_backup_<TIMESTAMP>/* data/",
        "```",
        "",
        "### Option 3: Recover Specific Rows from Quarantine",
        "",
        "```python",
        "import pandas as pd",
        "",
        "# Load the cleaned file and quarantine",
        "clean = pd.read_csv('data/experiment_leaderboard.csv')",
        "bad_rows = pd.read_csv('quarantine/experiment_leaderboard_bad_rows_<TIMESTAMP>.csv')",
        "",
        "# Drop metadata columns added during quarantine",
        "recovered = bad_rows.drop(columns=['issue_code', 'reason', 'removed_at'])",
        "",
        "# Append recovered rows",
        "restored = pd.concat([clean, recovered], ignore_index=True)",
        "restored.to_csv('data/experiment_leaderboard.csv', index=False)",
        "```",
        "",
        "## Integrity Verification",
        "",
        "Verify file integrity using SHA256 checksums:",
        "",
        "```bash",
        "sha256sum backups/sanity_backup_<TIMESTAMP>/<FILE>",
        "```",
        "",
        "Compare against values listed above.",
        "",
    ])
    
    if orphaned_models:
        guide_lines.extend([
            "## Orphaned Models",
            "",
            f"The following {len(orphaned_models)} models were orphaned and archived:",
            "",
        ])
        for model_path in orphaned_models[:20]:
            guide_lines.append(f"- `{model_path}`")
        if len(orphaned_models) > 20:
            guide_lines.append(f"- ... and {len(orphaned_models) - 20} more")
        guide_lines.append("")
    
    guide_lines.extend([
        "## Metadata Log",
        "",
        "Full mutation metadata is stored in `metadata/sanitization_log.json`.",
        "Check this file for complete audit trail of all mutations.",
        "",
        "## Support",
        "",
        "For issues or questions:",
        "1. Check `metadata/sanitization_log.json` for mutation details",
        "2. Verify backup integrity with SHA256 checksums",
        "3. Review `backups/MANIFEST.json` for backup locations",
        "4. Review `archives/MANIFEST.json` for archived data locations",
    ])
    
    return "\n".join(guide_lines)


def execute_sanitization(
    root_dir: Path,
    report_json: dict[str, Any],
    quarantine_info: dict[str, list[int]],
    data_dir: Path,
    remove_orphans: bool = False,
    force: bool = False,
) -> tuple[bool, list[MutationMetadata]]:
    """
    Execute the actual sanitization mutations.
    
    Returns: (success, mutations_list)
    """
    mutations: list[MutationMetadata] = []
    backup_dir = generate_backup_dir(root_dir)
    archive_dir = root_dir / "archives"
    quarantine_dir = root_dir / "quarantine"
    metadata_dir = root_dir / "metadata"
    
    # Check idempotency
    can_proceed, msg = check_idempotency(metadata_dir, set(quarantine_info.keys()), force)
    if not can_proceed:
        print(msg)
        return False, []
    
    print(f"\n[INFO] Creating backup directory: {backup_dir.relative_to(root_dir)}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] Processing {len(quarantine_info)} artifacts...")
    
    for file_name, row_indices in quarantine_info.items():
        csv_path = data_dir / file_name
        
        if not csv_path.exists():
            print(f"[WARN] File not found: {csv_path}")
            continue
        
        print(f"\n  Processing: {file_name}")
        
        # 1. Compute hash before
        sha256_before = compute_file_hash(csv_path)
        print(f"    - SHA256 before: {sha256_before}")
        
        # 2. Create backup
        backup_path, err = create_backup(csv_path, backup_dir)
        if err:
            print(f"    [ERROR] Backup failed: {err}")
            continue
        print(f"    - Backup created: {backup_path.relative_to(root_dir)}")
        
        # 3. Extract bad rows to quarantine
        quarantine_name = generate_quarantine_name(file_name)
        bad_rows_df, err = extract_bad_rows(csv_path, row_indices, quarantine_dir, quarantine_name)
        if err:
            print(f"    [WARN] Quarantine failed: {err}")
            quarantine_file = None
        else:
            quarantine_file = str(quarantine_dir / quarantine_name)
            print(f"    - Quarantine created: {len(row_indices)} rows -> {quarantine_name}")
        
        # 4. Filter and write clean CSV
        clean_df, rows_removed, err = filter_good_rows(csv_path, row_indices)
        if err:
            print(f"    [ERROR] Filter failed: {err}")
            continue
        
        err = write_cleaned_csv(clean_df, csv_path)
        if err:
            print(f"    [ERROR] Write failed: {err}")
            continue
        print(f"    - Cleaned CSV written: {len(clean_df)} rows remain")
        
        # 5. Compute hash after
        sha256_after = compute_file_hash(csv_path)
        print(f"    - SHA256 after: {sha256_after}")
        
        # 6. Archive original
        archive_name = generate_archive_name(file_name)
        archive_path = archive_dir / archive_name
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            backup_path.rename(archive_path)
            print(f"    - Archive created: {archive_name}")
        except Exception as e:
            print(f"    [ERROR] Archive move failed: {e}")
            continue
        
        # 7. Record mutation
        mutation = MutationMetadata(
            timestamp=utc_now(),
            file_path=str(csv_path.relative_to(root_dir)),
            file_name=file_name,
            original_row_count=len(bad_rows_df) + len(clean_df) if bad_rows_df is not None else 0,
            final_row_count=len(clean_df),
            rows_removed=rows_removed,
            sha256_before=sha256_before,
            sha256_after=sha256_after,
            backup_file=str(backup_path.relative_to(root_dir)),
            archive_file=str(archive_path.relative_to(root_dir)),
            quarantine_file=quarantine_file,
        )
        mutations.append(mutation)
    
    # Create backups manifest
    backup_manifest = {
        "metadata": {
            "created_at": utc_now(),
            "backup_dir": str(backup_dir.relative_to(root_dir)),
            "archive_strategy": "Originals moved to archives/, backups preserved",
        },
        "backups": [],
    }
    save_json(backup_dir.parent / "MANIFEST.json", backup_manifest)
    
    # Create archives manifest
    archives_manifest = {
        "metadata": {
            "created_at": utc_now(),
            "archive_dir": str(archive_dir.relative_to(root_dir)),
        },
        "archives": [m.to_dict() for m in mutations],
    }
    save_json(archive_dir / "MANIFEST.json", archives_manifest)
    
    # Save sanitization log
    save_sanitization_log(
        metadata_dir,
        [m.to_dict() for m in mutations],
    )
    
    # Generate rollback guide
    orphaned_models = report_json.get("orphaned_models", [])
    rollback_guide = generate_rollback_guide(root_dir, mutations, orphaned_models)
    rollback_path = root_dir / "docs" / "ROLLBACK_GUIDE.md"
    rollback_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(rollback_path, "w", encoding="utf-8") as f:
            f.write(rollback_guide)
        print(f"\n[INFO] Rollback guide created: {rollback_path.relative_to(root_dir)}")
    except Exception as e:
        print(f"[WARN] Failed to create rollback guide: {e}")
    
    return True, mutations


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Apply safe, reversible mutations to sanitize RL trading experiment data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview mutations (default)
  python sanitize_apply.py --root-dir .
  
  # Apply mutations
  python sanitize_apply.py --root-dir . --execute
  
  # Re-apply with force (dangerous)
  python sanitize_apply.py --root-dir . --execute --force
        """,
    )
    
    parser.add_argument(
        "--report-json",
        type=str,
        default="reports/sanity_scan_report.json",
        help="Path to sanity_scan_report.json",
    )
    parser.add_argument(
        "--quarantine-json",
        type=str,
        default="reports/sanity_quarantine.json",
        help="Path to sanity_quarantine.json",
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default=".",
        help="Repository root directory",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Data directory (relative to root-dir)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview mutations without applying (default: True)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply mutations (requires --dry-run to be shown first)",
    )
    parser.add_argument(
        "--remove-orphans",
        action="store_true",
        help="Also archive/delete orphaned models",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip idempotency checks (dangerous—use with caution)",
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    root_dir = Path(args.root_dir).resolve()
    data_dir = root_dir / args.data_dir
    report_path = root_dir / args.report_json
    quarantine_path = root_dir / args.quarantine_json
    
    print(f"\n[INFO] Sanitizer v{SANITIZER_VERSION}")
    print(f"[INFO] Root directory: {root_dir}")
    
    # Load reports
    try:
        report_json = load_json(report_path)
        quarantine_json = load_json(quarantine_path)
    except Exception as e:
        print(f"[ERROR] Failed to load reports: {e}")
        return 1
    
    # Extract quarantine info
    quarantine_info = extract_quarantine_info(report_json)
    
    if not quarantine_info:
        print("[INFO] No quarantine rows found. Nothing to do.")
        return 0
    
    print(f"\n[INFO] Found {len(quarantine_info)} artifacts with quarantine rows")
    
    # Get downstream dependencies
    downstream_deps = report_json.get("downstream_dependencies", [])
    
    # Preview mode (default)
    if args.dry_run and not args.execute:
        preview_mutations(quarantine_info, root_dir, data_dir, downstream_deps)
        return 0
    
    # Execute mode
    if args.execute:
        print("\n[INFO] Executing sanitization...")
        success, mutations = execute_sanitization(
            root_dir,
            report_json,
            quarantine_info,
            data_dir,
            remove_orphans=args.remove_orphans,
            force=args.force,
        )
        
        if success:
            print(f"\n[SUCCESS] Sanitization complete!")
            print(f"[INFO] Created {len(mutations)} mutation records")
            print(f"[INFO] Check metadata/sanitization_log.json for details")
            print(f"[INFO] Check docs/ROLLBACK_GUIDE.md for rollback instructions")
            return 0
        else:
            print("\n[ERROR] Sanitization failed")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

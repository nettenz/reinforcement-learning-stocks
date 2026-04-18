"""
Integration test for sanitize_apply.py v0.1.0

Creates test data and verifies:
1. Backup creation
2. Row quarantine
3. Row filtering
4. Metadata logging
5. Rollback guide generation
"""

import json
import tempfile
from pathlib import Path
import pandas as pd
import sys
import shutil

def setup_test_env(test_dir: Path) -> None:
    """Create test CSV and scan report."""
    # Create test CSV
    data_dir = test_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Simple test leaderboard
    df = pd.DataFrame({
        "ticker": ["AAPL", "AAPL", "AAPL", "NVDA", "NVDA"],
        "run_label": ["test1", "test2", "test3", "test4", "test5"],
        "ranking_score": [0.8, 0.9, 0.5, 0.7, 0.85],
        "test_trade_win_rate": [0.5, 0.6, 0.7, 0.8, 0.9],
    })
    csv_path = data_dir / "test_leaderboard.csv"
    df.to_csv(csv_path, index=False)
    print(f"[TEST] Created test CSV: {csv_path} ({len(df)} rows)")
    
    # Create test scan report
    reports_dir = test_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "scan_metadata": {
            "generated_at_utc": "2026-04-10T12:00:00+00:00",
            "root_dir": str(test_dir),
            "scanner_version": "0.2.0",
        },
        "artifacts": [
            {
                "path": str(csv_path),
                "kind": "csv_artifact",
                "exists": True,
                "readable": True,
                "row_count": 5,
                "column_count": 4,
                "columns": ["ticker", "run_label", "ranking_score", "test_trade_win_rate"],
                "issues": [
                    {
                        "code": "bad_ranking_score",
                        "severity": "high",
                        "action_class": "sanitize",
                        "message": "Row 2 has ranking_score < 0.6",
                        "artifact": str(csv_path),
                        "row_index": 2,
                        "run_label": "test3",
                    },
                    {
                        "code": "outlier_trade_win_rate",
                        "severity": "high",
                        "action_class": "sanitize",
                        "message": "Row 4 has anomalous trade_win_rate",
                        "artifact": str(csv_path),
                        "row_index": 4,
                        "run_label": "test5",
                    },
                ]
            }
        ],
        "downstream_dependencies": [
            {
                "script_path": "scripts/analyze.py",
                "pattern": "test_leaderboard",
                "type": "read_leaderboard",
            }
        ],
        "orphaned_models": [],
        "json_validation": [],
        "quarantine_rows": [],
        "all_issues": [],
        "summary": {}
    }
    
    report_path = reports_dir / "sanity_scan_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[TEST] Created test report: {report_path}")
    
    # Create quarantine JSON
    quarantine = {
        "metadata": {
            "generated_at_utc": "2026-04-10T12:00:00+00:00",
            "scanner_version": "0.2.0",
        },
        "rows_to_quarantine": []
    }
    quarantine_path = reports_dir / "sanity_quarantine.json"
    with open(quarantine_path, "w") as f:
        json.dump(quarantine, f, indent=2)
    print(f"[TEST] Created quarantine JSON: {quarantine_path}")


def test_dry_run(test_dir: Path) -> bool:
    """Test dry-run mode."""
    print("\n[TEST] Running dry-run test...")
    import subprocess
    
    result = subprocess.run(
        [
            sys.executable, "sanitize_apply.py",
            "--root-dir", str(test_dir),
            "--report-json", "reports/sanity_scan_report.json",
            "--dry-run",
        ],
        cwd=test_dir,
        capture_output=True,
        text=True,
    )
    
    print(result.stdout)
    if result.returncode != 0:
        print(f"[ERROR] Dry-run failed: {result.stderr}")
        return False
    
    # Should not have created any actual mutations
    if (test_dir / "backups").exists():
        print("[ERROR] Backups should not exist in dry-run mode")
        return False
    
    print("[TEST] Dry-run test PASSED")
    return True


def test_execute_mode(test_dir: Path) -> bool:
    """Test execute mode."""
    print("\n[TEST] Running execute test...")
    import subprocess
    
    result = subprocess.run(
        [
            sys.executable, "sanitize_apply.py",
            "--root-dir", str(test_dir),
            "--report-json", "reports/sanity_scan_report.json",
            "--execute",
        ],
        cwd=test_dir,
        capture_output=True,
        text=True,
    )
    
    print(result.stdout)
    if result.returncode != 0:
        print(f"[ERROR] Execute failed: {result.stderr}")
        return False
    
    # Should have created directories and files
    checks = [
        (test_dir / "backups", "backups directory"),
        (test_dir / "archives", "archives directory"),
        (test_dir / "quarantine", "quarantine directory"),
        (test_dir / "metadata" / "sanitization_log.json", "sanitization log"),
        (test_dir / "docs" / "ROLLBACK_GUIDE.md", "rollback guide"),
    ]
    
    for check_path, desc in checks:
        if not check_path.exists():
            print(f"[ERROR] Missing: {desc}")
            return False
        print(f"[OK] {desc} created")
    
    # Verify cleaned CSV
    df_cleaned = pd.read_csv(test_dir / "data" / "test_leaderboard.csv")
    if len(df_cleaned) != 3:
        print(f"[ERROR] Expected 3 rows after cleaning, got {len(df_cleaned)}")
        return False
    print(f"[OK] CSV cleaned: 5 -> 3 rows")
    
    # Verify quarantine CSV exists
    quarantine_files = list((test_dir / "quarantine").glob("*.csv"))
    if not quarantine_files:
        print("[ERROR] No quarantine CSV created")
        return False
    print(f"[OK] Quarantine created: {len(quarantine_files)} files")
    
    # Verify metadata
    with open(test_dir / "metadata" / "sanitization_log.json") as f:
        log = json.load(f)
        mutations = log.get("mutations", [])
        if len(mutations) != 1:
            print(f"[ERROR] Expected 1 mutation record, got {len(mutations)}")
            return False
        mutation = mutations[0]
        if mutation["rows_removed"] != 2:
            print(f"[ERROR] Expected 2 rows removed, got {mutation['rows_removed']}")
            return False
        print(f"[OK] Metadata recorded: 2 rows removed")
    
    # Verify rollback guide
    rollback_path = test_dir / "docs" / "ROLLBACK_GUIDE.md"
    rollback_content = rollback_path.read_text()
    if "Restore Procedure" not in rollback_content:
        print("[ERROR] Rollback guide missing restore procedure")
        return False
    print(f"[OK] Rollback guide generated")
    
    print("[TEST] Execute test PASSED")
    return True


def test_idempotency_check(test_dir: Path) -> bool:
    """Test idempotency check (should warn on re-run)."""
    print("\n[TEST] Running idempotency check test...")
    import subprocess
    
    # First execution (already done above)
    # Second execution should warn
    result = subprocess.run(
        [
            sys.executable, "sanitize_apply.py",
            "--root-dir", str(test_dir),
            "--report-json", "reports/sanity_scan_report.json",
            "--execute",
        ],
        cwd=test_dir,
        capture_output=True,
        text=True,
    )
    
    print(result.stdout)
    # Should fail due to idempotency check
    if result.returncode == 0:
        print("[WARN] Second execution should fail idempotency check (optional behavior)")
    else:
        print("[OK] Idempotency check prevented re-application")
    
    # Try with --force
    result = subprocess.run(
        [
            sys.executable, "sanitize_apply.py",
            "--root-dir", str(test_dir),
            "--report-json", "reports/sanity_scan_report.json",
            "--execute",
            "--force",
        ],
        cwd=test_dir,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"[ERROR] Force flag should allow re-execution: {result.stderr}")
        return False
    
    print("[OK] Force flag bypassed idempotency check")
    print("[TEST] Idempotency check test PASSED")
    return True


def main() -> int:
    """Run all tests."""
    print("=" * 70)
    print("SANITIZE_APPLY.PY v0.1.0 INTEGRATION TEST")
    print("=" * 70)
    
    # Create temporary test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        print(f"\n[TEST] Using temporary directory: {test_dir}")
        
        try:
            # Setup
            setup_test_env(test_dir)
            
            # Copy sanitize_apply.py to test directory
            current_dir = Path(__file__).parent
            shutil.copy(
                current_dir / "sanitize_apply.py",
                test_dir / "sanitize_apply.py"
            )
            
            # Run tests
            tests = [
                test_dry_run,
                test_execute_mode,
                test_idempotency_check,
            ]
            
            passed = 0
            for test in tests:
                if test(test_dir):
                    passed += 1
                else:
                    print(f"\n[FAIL] {test.__name__} FAILED")
            
            print("\n" + "=" * 70)
            print(f"RESULTS: {passed}/{len(tests)} tests passed")
            print("=" * 70)
            
            return 0 if passed == len(tests) else 1
        
        except Exception as e:
            print(f"\n[ERROR] Test crashed: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())

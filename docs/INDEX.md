# Documentation Index

## 🚀 Quickstart

- **[SANITIZE_APPLY_QUICKSTART.md](SANITIZE_APPLY_QUICKSTART.md)** — Get started with data sanitization in 5 minutes
- **[README.md](../README.md)** — Project overview (in root)

---

## 📋 Phase 1-2: Data Sanitation Pipeline

### Phase 1: Detection (sanity_scan.py v0.2.0)
- **[PHASE_1_COMPLETE.md](PHASE_1_COMPLETE.md)** — Phase 1 completion summary, findings, and metrics

### Phase 2: Mutation (sanitize_apply.py v0.1.0)
- **[SANITIZE_APPLY_GUIDE.md](SANITIZE_APPLY_GUIDE.md)** — Complete guide to applying mutations safely
- **[DELIVERABLES.md](DELIVERABLES.md)** — Phase 2 deliverables checklist

### Combined Tools
- **[SANITIZATION_TOOLS_SUMMARY.md](SANITIZATION_TOOLS_SUMMARY.md)** — Technical reference for both v0.2.0 scanner and v0.1.0 apply script

---

## 🎯 Implementation Plans

- **[implementation_plan.md](implementation_plan.md)** — Original Phase 1-2 implementation strategy
- **[IMPLEMENTATION_PLAN_ENVIRONMENT_REALISM.md](IMPLEMENTATION_PLAN_ENVIRONMENT_REALISM.md)** — Environment realism audit plan

---

## 🏗️ Architecture & Research

- **[HANDOFF.md](HANDOFF.md)** — Handoff notes from previous agent work
- **[GEMINI_HANDOFF_REWARD_HYBRID_FIX.md](GEMINI_HANDOFF_REWARD_HYBRID_FIX.md)** — Reward model handoff documentation
- **[PLAN.md](PLAN.md)** — General project planning notes
- **[EXECUTION_PROCESS.md](EXECUTION_PROCESS.md)** — Execution workflow documentation

---

## 🔬 Technical Deep-Dives

- **[REWARD_FIX_DOCUMENTATION.md](REWARD_FIX_DOCUMENTATION.md)** — Reward model architecture and fixes
- **[SENTIMENT_INTEGRATION.md](SENTIMENT_INTEGRATION.md)** — News sentiment feature integration
- **[GPU_ACCELERATION.md](GPU_ACCELERATION.md)** — GPU optimization notes
- **[ENVIRONMENT_REALISM_AUDIT_2026_04_02.md](ENVIRONMENT_REALISM_AUDIT_2026_04_02.md)** — Environment realism analysis

---

## 🔄 Workflow

### Data Sanitation Workflow

```
1. Scan for contamination
   python scripts/sanity_scan.py --root-dir . --apply dry-run
   → reports/sanity_scan_report.json
   → reports/sanity_quarantine.json

2. Review findings
   Open reports/sanity_scan_report.json
   Read PHASE_1_COMPLETE.md for context

3. Apply mutations (if approved)
   python scripts/sanitize_apply.py --dry-run
   python scripts/sanitize_apply.py --execute

4. Verify clean state
   python scripts/sanity_scan.py --root-dir .
   Check backups/, archives/, quarantine/ directories

5. Rollback if needed
   See docs/ROLLBACK_GUIDE.md (auto-generated)
```

---

## 📁 Directory Structure

```
docs/
├── INDEX.md (this file)
├── SANITIZE_APPLY_QUICKSTART.md ⭐ START HERE
├── PHASE_1_COMPLETE.md
├── SANITIZATION_TOOLS_SUMMARY.md
├── SANITIZE_APPLY_GUIDE.md
├── DELIVERABLES.md
├── implementation_plan.md
└── ... (other research & handoff docs)

backups/                    ← Created by sanitize_apply.py
├── sanity_backup_<timestamp>/
└── MANIFEST.json

archives/                   ← Created by sanitize_apply.py
├── experiment_leaderboard_<timestamp>.csv
└── MANIFEST.json

quarantine/                 ← Created by sanitize_apply.py
└── *_bad_rows_<timestamp>.csv

metadata/                   ← Created by sanitize_apply.py
└── sanitization_log.json

reports/
├── sanity_scan_report.json
├── sanity_scan_summary.md
└── sanity_quarantine.json
```

---

## ✅ Status

**Phase 1 (Detection):** ✅ Complete
- Scanner v0.2.0 detects contamination, snapshots, dependencies, orphaned models

**Phase 2 (Mutation):** ✅ Complete  
- Apply script v0.1.0 safely mutates with backups, archiving, quarantine

**Phase 3 (Integration & Testing):** 🔄 In Progress
- Smoke tests
- Documentation review
- Final handoff notes

---

## 🆘 Need Help?

1. **Quick overview?** → [SANITIZE_APPLY_QUICKSTART.md](SANITIZE_APPLY_QUICKSTART.md)
2. **Full details?** → [SANITIZATION_TOOLS_SUMMARY.md](SANITIZATION_TOOLS_SUMMARY.md)
3. **How to recover?** → `docs/ROLLBACK_GUIDE.md` (auto-generated after apply)
4. **Phase 1 results?** → [PHASE_1_COMPLETE.md](PHASE_1_COMPLETE.md)

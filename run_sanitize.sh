#!/bin/bash
# Quick launcher for sanitize_apply.py v0.1.0
# Usage:
#   ./run_sanitize.sh preview              (default, shows what will happen)
#   ./run_sanitize.sh execute              (apply mutations)
#   ./run_sanitize.sh force                (expert mode, skip checks)
#   ./run_sanitize.sh help                 (show help)

ACTION="${1:-preview}"
ROOT_DIR="${2:-.}"
DATA_DIR="${3:-data}"
REPORT_JSON="${4:-reports/sanity_scan_report.json}"
QUARANTINE_JSON="${5:-reports/sanity_quarantine.json}"

SCRIPT_NAME="sanitize_apply.py"
SCRIPT_PATH="${ROOT_DIR}/${SCRIPT_NAME}"

# Verify script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "[ERROR] Script not found: $SCRIPT_PATH" >&2
    exit 1
fi

# Verify Python
if ! command -v python &> /dev/null; then
    echo "[ERROR] Python not found or not in PATH" >&2
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1)
echo "[INFO] Using: $PYTHON_VERSION"

# Build command
BASE_CMD=(
    python "$SCRIPT_PATH"
    --root-dir "$ROOT_DIR"
    --data-dir "$DATA_DIR"
    --report-json "$REPORT_JSON"
    --quarantine-json "$QUARANTINE_JSON"
)

case "$ACTION" in
    preview)
        echo "[INFO] Preview mode (dry-run)"
        echo "[INFO] No mutations will be applied"
        CMD=("${BASE_CMD[@]}" --dry-run)
        ;;
    execute)
        echo "[INFO] Execute mode"
        echo "[WARN] This will apply mutations!"
        CMD=("${BASE_CMD[@]}" --execute)
        ;;
    force)
        echo "[ERROR] Force mode - dangerous!"
        echo "[WARN] This will skip idempotency checks!"
        CMD=("${BASE_CMD[@]}" --execute --force)
        ;;
    help)
        echo "Usage: ./run_sanitize.sh <action> [root-dir] [data-dir]"
        echo ""
        echo "Actions:"
        echo "  preview   - Show what will happen (default, no mutations)"
        echo "  execute   - Apply mutations"
        echo "  force     - Force apply (skip idempotency checks, expert mode)"
        echo "  help      - Show this help"
        echo ""
        echo "Examples:"
        echo "  ./run_sanitize.sh                      # Preview mutations"
        echo "  ./run_sanitize.sh execute              # Apply mutations"
        echo "  ./run_sanitize.sh preview .            # Custom root"
        exit 0
        ;;
    *)
        echo "[ERROR] Unknown action: $ACTION" >&2
        echo "Try: ./run_sanitize.sh help" >&2
        exit 1
        ;;
esac

# Run command
echo ""
echo "Running: ${CMD[*]}"
echo ""

"${CMD[@]}"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "[SUCCESS] Command completed successfully"
else
    echo ""
    echo "[ERROR] Command failed with exit code: $EXIT_CODE" >&2
fi

exit $EXIT_CODE

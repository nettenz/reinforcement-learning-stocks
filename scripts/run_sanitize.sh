#!/usr/bin/env bash
set -euo pipefail

# Quick launcher for sanitize_apply.py v0.1.0
# Usage:
#   ./scripts/run_sanitize.sh preview              (default, shows what will happen)
#   ./scripts/run_sanitize.sh execute              (apply mutations)
#   ./scripts/run_sanitize.sh force                (expert mode, skip checks)
#   ./scripts/run_sanitize.sh help                 (show help)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ACTION="${1:-preview}"
ROOT_DIR="${2:-$DEFAULT_ROOT_DIR}"
DATA_DIR="${3:-data}"
REPORT_JSON="${4:-reports/sanity_scan_report.json}"
QUARANTINE_JSON="${5:-reports/sanity_quarantine.json}"

SCRIPT_NAME="sanitize_apply.py"
SCRIPT_PATH="${ROOT_DIR}/scripts/${SCRIPT_NAME}"

cd "$ROOT_DIR"

resolve_python() {
    if [[ -x "$ROOT_DIR/.venv-wsl/bin/python" ]]; then
        echo "$ROOT_DIR/.venv-wsl/bin/python"
        return 0
    fi
    if [[ -x "$ROOT_DIR/.venv-wsl/bin/python3" ]]; then
        echo "$ROOT_DIR/.venv-wsl/bin/python3"
        return 0
    fi
    if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
        echo "$ROOT_DIR/.venv/bin/python"
        return 0
    fi
    if [[ -x "$ROOT_DIR/.venv/bin/python3" ]]; then
        echo "$ROOT_DIR/.venv/bin/python3"
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
        echo "$ROOT_DIR/.venv/Scripts/python.exe"
        return 0
    fi
    return 1
}

# Verify script exists
if [[ ! -f "$SCRIPT_PATH" ]]; then
    echo "[ERROR] Script not found: $SCRIPT_PATH" >&2
    exit 1
fi

PYTHON_EXEC="$(resolve_python)"
PYTHON_VERSION="$("$PYTHON_EXEC" --version 2>&1)"
echo "[INFO] Using: $PYTHON_VERSION"

# Build command
BASE_CMD=(
    "$PYTHON_EXEC" "$SCRIPT_PATH"
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
        echo "Usage: ./scripts/run_sanitize.sh <action> [root-dir] [data-dir]"
        echo ""
        echo "Actions:"
        echo "  preview   - Show what will happen (default, no mutations)"
        echo "  execute   - Apply mutations"
        echo "  force     - Force apply (skip idempotency checks, expert mode)"
        echo "  help      - Show this help"
        echo ""
        echo "Examples:"
        echo "  ./scripts/run_sanitize.sh             # Preview mutations"
        echo "  ./scripts/run_sanitize.sh execute      # Apply mutations"
        echo "  ./scripts/run_sanitize.sh preview .    # Custom root"
        exit 0
        ;;
    *)
        echo "[ERROR] Unknown action: $ACTION" >&2
        echo "Try: ./scripts/run_sanitize.sh help" >&2
        exit 1
        ;;
esac

echo ""
echo "Running: ${CMD[*]}"
echo ""

"${CMD[@]}"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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

PYTHON_EXEC="$(resolve_python)"
exec "$PYTHON_EXEC" scripts/run_diagnostics.py "$@"

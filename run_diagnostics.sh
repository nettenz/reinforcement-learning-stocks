#!/bin/bash

# Wrapper script: run diagnostics via robust Python orchestrator
set -e

script_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$script_dir"

if [ -f ".venv/Scripts/python.exe" ]; then
  PYTHON_EXEC=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/python3" ]; then
  PYTHON_EXEC=".venv/bin/python3"
elif [ -f ".venv/bin/python" ]; then
  PYTHON_EXEC=".venv/bin/python"
else
  PYTHON_EXEC="python"
fi

exec "$PYTHON_EXEC" run_diagnostics.py "$@"

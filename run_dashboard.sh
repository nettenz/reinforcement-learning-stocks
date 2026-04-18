#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-start}"
PORT="${2:-8501}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
DASHBOARD_SCRIPT="$ROOT_DIR/src/analytics_dashboard.py"
PID_FILE="$ROOT_DIR/.streamlit_dashboard.pid"

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

get_dashboard_pids() {
  ps -ax -o pid= -o command= | awk -v port="$PORT" '
    /streamlit run/ && /analytics_dashboard.py/ && $0 ~ ("--server.port " port) {print $1}
  '
}

status_dashboard() {
  local pids
  pids="$(get_dashboard_pids || true)"
  if [[ -n "$pids" ]]; then
    echo "Dashboard is running on port $PORT. PID(s): $(echo "$pids" | tr '\n' ' ' | xargs)"
    return 0
  fi
  echo "Dashboard is not running on port $PORT."
  return 1
}

stop_dashboard() {
  local pids
  pids="$(get_dashboard_pids || true)"
  if [[ -z "$pids" ]]; then
    echo "No dashboard process found on port $PORT."
    rm -f "$PID_FILE"
    return 0
  fi

  while read -r pid; do
    [[ -z "$pid" ]] && continue
    kill "$pid"
    echo "Stopped dashboard process PID $pid."
  done <<< "$pids"

  rm -f "$PID_FILE"
}

start_dashboard() {
  local python_exec
  if ! python_exec="$(resolve_python)"; then
    echo "Python executable not found. Create .venv-wsl (preferred) or .venv, or add python/python3 to PATH." >&2
    exit 1
  fi

  if [[ ! -f "$DASHBOARD_SCRIPT" ]]; then
    echo "Dashboard script not found at '$DASHBOARD_SCRIPT'." >&2
    exit 1
  fi

  local pids
  pids="$(get_dashboard_pids || true)"
  if [[ -n "$pids" ]]; then
    echo "Dashboard already running on port $PORT. PID(s): $(echo "$pids" | tr '\n' ' ' | xargs)"
    return 0
  fi

  nohup "$python_exec" -m streamlit run "$DASHBOARD_SCRIPT" --server.headless true --server.port "$PORT" >"$ROOT_DIR/.streamlit_dashboard.log" 2>&1 &
  local pid=$!
  echo "$pid" >"$PID_FILE"
  echo "Dashboard started on http://127.0.0.1:$PORT (PID $pid)."
}

case "$ACTION" in
  start)
    start_dashboard
    ;;
  stop)
    stop_dashboard
    ;;
  status)
    status_dashboard
    ;;
  *)
    echo "Usage: ./run_dashboard.sh [start|stop|status] [port]" >&2
    exit 1
    ;;
esac

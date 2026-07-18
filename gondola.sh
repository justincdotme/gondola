#!/bin/sh
set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PID_FILE="$SCRIPT_DIR/gondola.pid"
LOG_FILE="$SCRIPT_DIR/gondola.log"
PROC_PATTERN="$SCRIPT_DIR/venv/bin/python main.py"

find_running_pid() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    cat "$PID_FILE"
    return 0
  fi
  pgrep -f "$PROC_PATTERN" 2>/dev/null || return 1
}

case "${1:-}" in
  --start)
    EXISTING=$(find_running_pid) && {
      echo "Already running (PID $EXISTING)"
      exit 1
    }
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
      echo "No .env file found. Run ./init.sh first." >&2
      exit 1
    fi
    set -a
    . "$SCRIPT_DIR/.env"
    set +a
    cd "$SCRIPT_DIR"
    nohup "$SCRIPT_DIR/venv/bin/python" main.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    PORT=${SENSOR_PORT:-8075}
    if [ -n "${SENSOR_TLS_CERT:-}" ] && [ -n "${SENSOR_TLS_KEY:-}" ] && \
       [ -f "${SENSOR_TLS_CERT:-}" ] && [ -f "${SENSOR_TLS_KEY:-}" ]; then
      HEALTH_URL="https://localhost:$PORT/api/v1/health"
      CURL_TLS="-sk"
    else
      HEALTH_URL="http://localhost:$PORT/api/v1/health"
      CURL_TLS="-s"
    fi
    TRIES=0
    while [ "$TRIES" -lt 10 ]; do
      sleep 1
      if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        rm "$PID_FILE"
        echo "Failed to start. Check gondola.log" >&2
        exit 1
      fi
      if curl $CURL_TLS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
        echo "Started (PID $!, listening on port $PORT)"
        break
      fi
      TRIES=$((TRIES + 1))
    done
    if [ "$TRIES" -eq 10 ]; then
      echo "Process running (PID $!) but not responding on port $PORT after 10s. Check gondola.log" >&2
      exit 1
    fi
    ;;
  --stop)
    PID=$(find_running_pid) || {
      echo "Not running (no PID file, no matching process)" >&2
      exit 1
    }
    if [ ! -f "$PID_FILE" ]; then
      echo "WARNING: No PID file. Found orphaned process (PID $PID)." >&2
    fi
    if kill "$PID" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "Stopped (PID $PID)"
    else
      rm -f "$PID_FILE"
      echo "Process $PID already exited, cleaned up" >&2
    fi
    ;;
  --restart)
    "$0" --stop || true
    sleep 1
    "$0" --start
    ;;
  --status)
    PID=$(find_running_pid) || {
      echo "Not running"
      [ -f "$PID_FILE" ] && rm "$PID_FILE"
      exit 1
    }
    if [ ! -f "$PID_FILE" ]; then
      echo "WARNING: No PID file. Process was started outside this script." >&2
    fi
    set -a
    . "$SCRIPT_DIR/.env"
    set +a
    PORT=${SENSOR_PORT:-8075}
    if [ -n "${SENSOR_TLS_CERT:-}" ] && [ -n "${SENSOR_TLS_KEY:-}" ] && \
       [ -f "${SENSOR_TLS_CERT:-}" ] && [ -f "${SENSOR_TLS_KEY:-}" ]; then
      HEALTH_URL="https://localhost:$PORT/api/v1/health"
      CURL_TLS="-sk"
    else
      HEALTH_URL="http://localhost:$PORT/api/v1/health"
      CURL_TLS="-s"
    fi
    if curl $CURL_TLS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
      echo "Running (PID $PID, listening on port $PORT)"
    else
      echo "Process running (PID $PID) but not responding on port $PORT"
    fi
    ;;
  *)
    echo "Usage: $0 {--start|--stop|--restart|--status}"
    exit 1
    ;;
esac

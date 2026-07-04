#!/bin/sh
set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PID_FILE="$SCRIPT_DIR/gondola.pid"
LOG_FILE="$SCRIPT_DIR/gondola.log"

case "${1:-}" in
  --start)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "Already running (PID $(cat "$PID_FILE"))"
      exit 1
    fi
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
    PORT=${SENSOR_PORT:-8443}
    HEALTH_URL="https://localhost:$PORT/api/v1/health"
    TRIES=0
    while [ "$TRIES" -lt 10 ]; do
      sleep 1
      if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        rm "$PID_FILE"
        echo "Failed to start. Check gondola.log" >&2
        exit 1
      fi
      if curl -sk --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
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
    if [ ! -f "$PID_FILE" ]; then
      echo "Not running (no PID file)"
      exit 1
    fi
    PID=$(cat "$PID_FILE")
    if kill "$PID" 2>/dev/null; then
      rm "$PID_FILE"
      echo "Stopped (PID $PID)"
    else
      rm "$PID_FILE"
      echo "Process $PID not found, cleaned up PID file"
    fi
    ;;
  --restart)
    "$0" --stop 2>/dev/null || true
    sleep 1
    "$0" --start
    ;;
  --status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      PID=$(cat "$PID_FILE")
      set -a
      . "$SCRIPT_DIR/.env"
      set +a
      PORT=${SENSOR_PORT:-8443}
      HEALTH_URL="https://localhost:$PORT/api/v1/health"
      if curl -sk --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
        echo "Running (PID $PID, listening on port $PORT)"
      else
        echo "Process running (PID $PID) but not responding on port $PORT"
      fi
    else
      echo "Not running"
      [ -f "$PID_FILE" ] && rm "$PID_FILE"
    fi
    ;;
  *)
    echo "Usage: $0 {--start|--stop|--restart|--status}"
    exit 1
    ;;
esac

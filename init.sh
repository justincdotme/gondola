#!/bin/sh
set -eu

INSTALL_DIR=$(cd "$(dirname "$0")" && pwd)

echo ""
echo "=== Gondola Setup ==="
echo ""

# --- .env ---
if [ ! -f "$INSTALL_DIR/.env" ]; then
  API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  cat > "$INSTALL_DIR/.env" <<EOF
SENSOR_GATEWAY_API_KEY=$API_KEY
SENSOR_DB_PATH=$INSTALL_DIR/readings.db
SENSOR_PORT=8443
SENSOR_TLS_CERT=$INSTALL_DIR/certs/dev.crt
SENSOR_TLS_KEY=$INSTALL_DIR/certs/dev.key
EOF
  echo "[+] Created .env with generated API key"
else
  echo "[=] .env already exists"
  if ! grep -q "SENSOR_TLS_CERT" "$INSTALL_DIR/.env"; then
    cat >> "$INSTALL_DIR/.env" <<EOF
SENSOR_TLS_CERT=$INSTALL_DIR/certs/dev.crt
SENSOR_TLS_KEY=$INSTALL_DIR/certs/dev.key
EOF
    echo "[+] Added TLS certificate paths to .env"
  fi
  if grep -q "SENSOR_PORT=8075" "$INSTALL_DIR/.env"; then
    sed -i 's/SENSOR_PORT=8075/SENSOR_PORT=8443/' "$INSTALL_DIR/.env"
    echo "[+] Updated port from 8075 to 8443 for TLS"
  fi
fi

# --- Hostname ---
echo ""
echo "How will you reach Gondola? Enter a hostname or LAN IP."
printf "Hostname or IP [localhost]: "
read -r GONDOLA_HOST
GONDOLA_HOST=${GONDOLA_HOST:-localhost}

# --- TLS certificates ---
if [ ! -f "$INSTALL_DIR/certs/dev.crt" ]; then
  sh "$INSTALL_DIR/generate-certs.sh" "$GONDOLA_HOST"
  echo "[+] Generated TLS certificates for $GONDOLA_HOST"
else
  echo "[=] TLS certificates already exist (delete certs/dev.* to regenerate)"
fi

# --- Virtual environment ---
if [ ! -d "$INSTALL_DIR/venv" ]; then
  python3 -m venv "$INSTALL_DIR/venv"
  echo "[+] Created virtual environment"
else
  echo "[=] Virtual environment already exists"
fi

"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"
echo "[+] Installed dependencies"

# --- Summary ---
API_KEY=$(grep SENSOR_GATEWAY_API_KEY "$INSTALL_DIR/.env" | cut -d= -f2)
PORT=$(grep SENSOR_PORT "$INSTALL_DIR/.env" | cut -d= -f2)
echo ""
echo "=== Gondola is ready ==="
echo ""
echo "  API key:  $API_KEY"
echo "  URL:      https://$GONDOLA_HOST:$PORT/api/v1/health"
echo ""
echo "  Start:    ./gondola.sh --start"
echo "  Stop:     ./gondola.sh --stop"
echo "  Restart:  ./gondola.sh --restart"
echo "  Status:   ./gondola.sh --status"
echo ""

#!/bin/sh
set -eu

INSTALL_DIR=$(cd "$(dirname "$0")" && pwd)

echo ""
echo "=== Gondola Setup ==="
echo ""

# --- .env ---
FIRST_RUN=false
if [ ! -f "$INSTALL_DIR/.env" ]; then
  FIRST_RUN=true
  API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "[+] Generated API key"
else
  echo "[=] .env already exists"
fi

# --- Hostname ---
echo ""
echo "How will you reach Gondola? Enter a hostname or LAN IP."
printf "Hostname or IP [localhost]: "
read -r GONDOLA_HOST
GONDOLA_HOST=${GONDOLA_HOST:-localhost}

# --- TLS configuration ---
TLS_CERT=""
TLS_KEY=""
TLS_PORT=8075

if [ "$FIRST_RUN" = "true" ]; then
  echo ""
  echo "=== TLS Configuration ==="
  echo ""
  echo "  1) Generate a self-signed certificate"
  echo "  2) Provide your own certificate and key"
  echo "  3) No TLS (HTTP only)"
  echo ""
  echo "  Running without TLS transmits all traffic including"
  echo "  credentials in plaintext. This is not recommended."
  echo ""
  printf "Select option [1]: "
  read -r TLS_CHOICE
  TLS_CHOICE=${TLS_CHOICE:-1}

  case "$TLS_CHOICE" in
    1)
      sh "$INSTALL_DIR/generate-certs.sh" "$GONDOLA_HOST"
      TLS_CERT="$INSTALL_DIR/certs/dev.crt"
      TLS_KEY="$INSTALL_DIR/certs/dev.key"
      TLS_PORT=8443
      echo "[+] Generated self-signed TLS certificates for $GONDOLA_HOST"
      ;;
    2)
      printf "Absolute path to TLS certificate file: "
      read -r TLS_CERT
      printf "Absolute path to TLS private key file: "
      read -r TLS_KEY
      if [ -z "$TLS_CERT" ] || [ -z "$TLS_KEY" ]; then
        echo "Error: both certificate and key paths are required." >&2
        exit 1
      fi
      if [ ! -f "$TLS_CERT" ]; then
        echo "Error: certificate file not found: $TLS_CERT" >&2
        exit 1
      fi
      if [ ! -f "$TLS_KEY" ]; then
        echo "Error: key file not found: $TLS_KEY" >&2
        exit 1
      fi
      TLS_PORT=8443
      echo "[+] Using provided TLS certificates"
      ;;
    3)
      echo ""
      echo "  WARNING: All API traffic including authentication"
      echo "  credentials will be transmitted in plaintext."
      echo "  This includes HMAC signatures sent with every request."
      echo ""
      printf "  Continue without TLS? (y/N): "
      read -r CONFIRM
      case "$CONFIRM" in
        y|Y) echo "[!] TLS disabled, running HTTP only" ;;
        *) echo "Aborted." ; exit 0 ;;
      esac
      ;;
    *)
      echo "Invalid option." >&2
      exit 1
      ;;
  esac

  # --- Write .env ---
  cat > "$INSTALL_DIR/.env" <<EOF
SENSOR_GATEWAY_API_KEY=$API_KEY
SENSOR_DB_PATH=$INSTALL_DIR/readings.db
SENSOR_PORT=$TLS_PORT
EOF
  if [ -n "$TLS_CERT" ]; then
    cat >> "$INSTALL_DIR/.env" <<EOF
SENSOR_TLS_CERT=$TLS_CERT
SENSOR_TLS_KEY=$TLS_KEY
EOF
  fi
  echo "[+] Created .env"

else
  # Re-run: check TLS cert status
  if grep -q "^SENSOR_TLS_CERT=.*certs/dev\.crt" "$INSTALL_DIR/.env" 2>/dev/null; then
    if [ ! -f "$INSTALL_DIR/certs/dev.crt" ]; then
      sh "$INSTALL_DIR/generate-certs.sh" "$GONDOLA_HOST"
      echo "[+] Regenerated self-signed TLS certificates"
    else
      echo "[=] TLS certificates present"
    fi
  elif grep -q "^SENSOR_TLS_CERT=.\+" "$INSTALL_DIR/.env" 2>/dev/null; then
    CERT_PATH=$(grep "^SENSOR_TLS_CERT=" "$INSTALL_DIR/.env" | cut -d= -f2)
    if [ -f "$CERT_PATH" ]; then
      echo "[=] TLS certificate present ($CERT_PATH)"
    else
      echo "[!] WARNING: TLS certificate not found at $CERT_PATH"
    fi
  else
    echo "[=] TLS not configured (edit .env to enable)"
  fi
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
if grep -q "^SENSOR_TLS_CERT=.\+" "$INSTALL_DIR/.env" 2>/dev/null; then
  SCHEME="https"
else
  SCHEME="http"
fi
echo ""
echo "=== Gondola is ready ==="
echo ""
echo "  API key:  $API_KEY"
echo "  URL:      $SCHEME://$GONDOLA_HOST:$PORT/api/v1/health"
echo ""
echo "  Start:    ./gondola.sh --start"
echo "  Stop:     ./gondola.sh --stop"
echo "  Restart:  ./gondola.sh --restart"
echo "  Status:   ./gondola.sh --status"
echo ""

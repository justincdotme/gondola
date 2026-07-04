#!/bin/sh
set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CERT_DIR="$SCRIPT_DIR/certs"

HOST="${1:-}"
if [ -z "$HOST" ]; then
  printf "Enter your hostname or LAN IP (e.g. 10.1.20.112 or vigilant.local): "
  read -r HOST
fi

if [ -z "$HOST" ]; then
  echo "Error: hostname/IP cannot be empty." >&2
  exit 1
fi

if printf '%s' "$HOST" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
  SAN="IP:$HOST"
elif printf '%s' "$HOST" | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$'; then
  SAN="DNS:$HOST"
else
  echo "Error: '$HOST' is not a valid IP address or hostname." >&2
  exit 1
fi

mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/dev.key" \
  -out "$CERT_DIR/dev.crt" \
  -subj "/CN=$HOST" \
  -addext "subjectAltName=$SAN"

echo "Certificates written to $CERT_DIR"
echo "  dev.crt"
echo "  dev.key"

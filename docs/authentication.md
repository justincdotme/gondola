# Authentication

Gondola authenticates requests with HMAC-SHA256 request signing, not a static bearer token. Every endpoint except `GET /api/v1/health` requires a valid signature.

## Overview

There is a single shared secret: `SENSOR_GATEWAY_API_KEY`, set in `.env` (or generated for you by `init.sh`). Clients use this secret to sign each request; Gondola recomputes the same signature server-side and compares them. The secret itself is never sent over the wire.

## Required headers

| Header | Description |
|--------|-------------|
| `X-Signature` | Hex-encoded HMAC-SHA256 signature of the canonical request string |
| `X-Timestamp` | Unix timestamp (seconds) the request was signed at |

## Building the signature

1. Build the canonical string:

   ```
   {METHOD}\n{PATH}\n{TIMESTAMP}
   ```

   - `METHOD` is the uppercase HTTP verb (`GET`)
   - `PATH` is the request path only, e.g. `/api/v1/readings`. It excludes scheme, host, and query string
   - `TIMESTAMP` is the same value sent in `X-Timestamp`, as a string

2. Compute `HMAC-SHA256(secret, canonical_string)` and hex-encode it. This is `X-Signature`.

The query string is not part of the signature, so `X-Signature` for `GET /api/v1/readings?mac=...&limit=50` is identical to the one for `GET /api/v1/readings` with no query string at all.

### Example: curl

```bash
SECRET="your-api-key"
METHOD="GET"
REQUEST_PATH="/api/v1/sensors"
TIMESTAMP=$(date +%s)
CANONICAL="${METHOD}
${REQUEST_PATH}
${TIMESTAMP}"
SIGNATURE=$(printf '%s' "$CANONICAL" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

curl -k "https://gondola.local:8443${REQUEST_PATH}" \
  -H "X-Signature: $SIGNATURE" \
  -H "X-Timestamp: $TIMESTAMP"
```

### Example: Python

```python
import hashlib
import hmac
import time

import requests

secret = "your-api-key"
method = "GET"
path = "/api/v1/sensors"
timestamp = str(int(time.time()))

canonical = f"{method}\n{path}\n{timestamp}"
signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

resp = requests.get(
    f"https://gondola.local:8443{path}",
    headers={"X-Signature": signature, "X-Timestamp": timestamp},
    verify="/path/to/certs/dev.crt",  # self-signed cert; see docs/building-a-consumer.md
)
```

### Example: PHP

```php
$secret = 'your-api-key';
$method = 'GET';
$path = '/api/v1/sensors';
$timestamp = (string) time();

$canonical = "{$method}\n{$path}\n{$timestamp}";
$signature = hash_hmac('sha256', $canonical, $secret);

$headers = [
    'X-Signature' => $signature,
    'X-Timestamp' => $timestamp,
];
```

## Clock skew

The server accepts timestamps within 60 seconds of its own clock in either direction. Requests signed outside that window are rejected even if the signature itself is correct, so keep client clocks in sync (NTP).

## Error responses

Any of the following results in `401 Unauthorized` with `{"error": "Invalid or missing API key"}`:

- Missing `X-Signature` or `X-Timestamp`
- `X-Timestamp` more than 60 seconds from the server's clock
- `X-Timestamp` that isn't a valid integer
- A signature that doesn't match what the server computes

## Failed-auth throttling

Gondola tracks failed authentication attempts per client IP. After 5 failures within a 5-minute window, that IP gets a 2-second delay added before each subsequent `401` response. This isn't a hard lockout; it slows down brute-force signature guessing without blocking it outright. The delay clears once the IP goes 5 minutes without a new failure.

## Security notes

- Signatures aren't single-use. A captured request stays valid for the rest of its 60-second window, so this scheme relies on TLS to keep requests from being observed in transit, not on the signature alone.
- The secret is shared across every consumer: there's no per-client key or key ID. That means there's no way to revoke one client without rotating the secret for all of them.

## Rotating the secret

Update `SENSOR_GATEWAY_API_KEY` in `.env` and restart Gondola (`./gondola.sh --restart`). There's no overlap window: every client needs the new key before the restart or its requests start failing.

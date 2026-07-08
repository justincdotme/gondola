# Building a Consumer

A practical guide to writing your own client against Gondola.

## 1. Sign every request

Every endpoint except `/api/v1/health` requires an HMAC-SHA256 signature. See [authentication.md](authentication.md) for the full scheme and code samples in curl, Python, and PHP.

## 2. Handle the TLS certificate

`init.sh` generates a self-signed certificate for Gondola (`generate-certs.sh`), so there's no CA a normal HTTP client will trust by default. Add `certs/dev.crt` to your consumer's trust store or CA bundle rather than disabling certificate verification. Verification is what proves you're actually talking to your Gondola instance and not something else on the network; skipping it turns TLS into encryption without authentication.

## 3. Pick the right endpoint for the job

- **`/api/v1/sensors`**: the current state of every sensor. Good for a live dashboard, since it reflects the most recent BLE advertisement, which can be far more frequent than what's persisted.
- **`/api/v1/readings`**: the historical, persisted series for one sensor. Resolution is capped by `SENSOR_WRITE_INTERVAL` (60 seconds by default) regardless of how often the sensor actually broadcasts.

If you need both a live number and a history chart, poll `/sensors` for the former and `/readings` for the latter. Don't try to reconstruct history from repeated `/sensors` polls.

## 4. Paginate readings correctly

`/api/v1/readings` pages oldest-first. To walk forward through history:

1. Request with `from` unset (or set to your last known timestamp) and a `limit`.
2. Take the `recorded_at` of the last row in the response and use it as `from` on the next request. `from` is exclusive, so you won't get a duplicate.
3. Repeat while `has_more` is `true`.

Stop as soon as a page comes back with zero readings, even if the previous page said `has_more: true`. An empty page can't advance your cursor, so continuing to trust `has_more` past that point risks looping forever on the same request.

## 5. Handle errors

| Status | What it means | What to do |
|--------|----------------|------------|
| 401 | Bad, missing, or expired signature | Check your clock is in sync, verify the secret, re-sign and retry |
| 404 | `mac` has never reported a reading | Don't retry; the sensor may not exist or hasn't been seen yet |
| 422 | Malformed `from`/`to` | Fix the request; retrying unchanged will fail again |
| 429 | Rate limited | Wait `Retry-After` seconds before retrying |

## 6. Poll, don't push

Gondola has no webhook or streaming endpoint, so consumers poll. `GET /api/v1/health` is unauthenticated and unthrottled, making it a cheap way to check Gondola is reachable before spending a signed request. Keep polling frequency under the 60-requests-per-60-seconds rate limit per IP: polling `/sensors` every few seconds for a live view is fine, but a tight loop across multiple endpoints can eat the budget fast.

## Minimal working example (Python)

```python
import hashlib
import hmac
import time

import requests

BASE_URL = "https://gondola.local:8443"
SECRET = "your-api-key"
CA_BUNDLE = "/path/to/certs/dev.crt"


def signed_headers(method: str, path: str) -> dict:
    timestamp = str(int(time.time()))
    canonical = f"{method}\n{path}\n{timestamp}"
    signature = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {"X-Signature": signature, "X-Timestamp": timestamp}


def get_sensors() -> list[dict]:
    path = "/api/v1/sensors"
    resp = requests.get(
        BASE_URL + path,
        headers=signed_headers("GET", path),
        verify=CA_BUNDLE,
    )
    resp.raise_for_status()
    return resp.json()["sensors"]


def get_readings(mac: str, since: str | None = None) -> list[dict]:
    path = "/api/v1/readings"
    readings = []
    from_ts = since
    while True:
        resp = requests.get(
            BASE_URL + path,
            params={"mac": mac, "from": from_ts, "limit": 500},
            headers=signed_headers("GET", path),
            verify=CA_BUNDLE,
        )
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        body = resp.json()
        if not body["readings"]:
            break
        readings.extend(body["readings"])
        from_ts = body["readings"][-1]["recorded_at"]
        if not body["has_more"]:
            break
    return readings
```

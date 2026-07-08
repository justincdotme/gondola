import hashlib
import hmac
import os
import time

os.environ.setdefault("SENSOR_GATEWAY_API_KEY", "test-api-key")


def make_hmac_headers(method, path, secret="test-key", timestamp=None):
    if timestamp is None:
        timestamp = int(time.time())
    canonical = f"{method}\n{path}\n{timestamp}"
    signature = hmac.new(
        secret.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    return {"X-Signature": signature, "X-Timestamp": str(timestamp)}

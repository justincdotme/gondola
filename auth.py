import hashlib
import hmac
import os
import time

from fastapi import Header, Request


class InvalidApiKey(Exception):
    pass


TIMESTAMP_WINDOW = 60


def require_hmac_auth(
    request: Request,
    x_signature: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
) -> None:
    secret = os.environ.get("SENSOR_GATEWAY_API_KEY", "")

    if x_signature and x_timestamp:
        try:
            ts = int(x_timestamp)
            if abs(time.time() - ts) <= TIMESTAMP_WINDOW:
                canonical = (
                    f"{request.method}\n{request.url.path}\n{x_timestamp}"
                )
                expected = hmac.new(
                    secret.encode(), canonical.encode(), hashlib.sha256
                ).hexdigest()
                if hmac.compare_digest(x_signature, expected):
                    return
        except ValueError:
            pass

    raise InvalidApiKey()

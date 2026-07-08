import asyncio
import hashlib
import hmac
import logging
import os
import time

from fastapi import Header, Request


logger = logging.getLogger(__name__)


class InvalidApiKey(Exception):
    pass


class AuthTracker:
    def __init__(self, max_failures=5, window_seconds=300, delay_seconds=2.0):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.delay_seconds = delay_seconds
        self._failures: dict[str, list[float]] = {}

    def record_failure(self, client_ip: str) -> None:
        now = time.monotonic()
        if client_ip not in self._failures:
            self._failures[client_ip] = []
        self._failures[client_ip].append(now)
        logger.warning(
            "Failed auth attempt from %s",
            client_ip,
        )

    def should_delay(self, client_ip: str) -> bool:
        if client_ip not in self._failures:
            return False
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._failures[client_ip] = [
            t for t in self._failures[client_ip] if t > cutoff
        ]
        if not self._failures[client_ip]:
            del self._failures[client_ip]
            return False
        return len(self._failures[client_ip]) >= self.max_failures


# Allow 60-second clock skew to tolerate client/server time drift.
TIMESTAMP_WINDOW = 60


async def require_hmac_auth(
    request: Request,
    x_signature: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
) -> None:
    secret = os.environ.get("SENSOR_GATEWAY_API_KEY", "")
    if not secret:
        logger.error(
            "SENSOR_GATEWAY_API_KEY not configured; rejecting auth"
        )
        raise InvalidApiKey()

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

    tracker = getattr(request.app.state, "auth_tracker", None)
    if tracker and request.client:
        client_ip = request.client.host
        tracker.record_failure(client_ip)
        if tracker.should_delay(client_ip):
            await asyncio.sleep(tracker.delay_seconds)

    raise InvalidApiKey()

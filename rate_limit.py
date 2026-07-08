import time


class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def check(self, client_ip: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = self._requests.get(client_ip, [])
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= self.max_requests:
            retry_after = int(timestamps[0] + self.window_seconds - now) + 1
            self._requests[client_ip] = timestamps
            return False, max(retry_after, 1)

        timestamps.append(now)
        self._requests[client_ip] = timestamps
        return True, 0

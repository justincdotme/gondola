from unittest.mock import patch
from rate_limit import RateLimiter


def test_requests_under_limit_allowed():
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        allowed, _ = limiter.check("10.0.0.1")
        assert allowed


def test_requests_over_limit_rejected():
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        limiter.check("10.0.0.1")
    allowed, retry_after = limiter.check("10.0.0.1")
    assert not allowed
    assert retry_after > 0


def test_different_ips_independent():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.check("10.0.0.1")
    limiter.check("10.0.0.1")
    allowed_1, _ = limiter.check("10.0.0.1")
    allowed_2, _ = limiter.check("10.0.0.2")
    assert not allowed_1
    assert allowed_2


def test_window_expiry_allows_new_requests():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    with patch("time.monotonic", return_value=1000.0):
        limiter.check("10.0.0.1")
        limiter.check("10.0.0.1")
    with patch("time.monotonic", return_value=1061.0):
        allowed, _ = limiter.check("10.0.0.1")
        assert allowed


def test_retry_after_is_positive():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    limiter.check("10.0.0.1")
    _, retry_after = limiter.check("10.0.0.1")
    assert retry_after >= 1

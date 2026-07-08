import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from auth import require_hmac_auth, InvalidApiKey, AuthTracker
from conftest import make_hmac_headers


@pytest.fixture
def app_with_auth(monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "test-secret")

    app = FastAPI()

    @app.exception_handler(InvalidApiKey)
    async def handle_invalid_api_key(request, exc):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing API key"},
        )

    @app.get("/protected")
    def protected(_: None = Depends(require_hmac_auth)):
        return {"status": "ok"}

    return TestClient(app)


def test_valid_hmac(app_with_auth):
    headers = make_hmac_headers("GET", "/protected", secret="test-secret")
    resp = app_with_auth.get("/protected", headers=headers)
    assert resp.status_code == 200


def test_missing_signature(app_with_auth):
    resp = app_with_auth.get(
        "/protected", headers={"X-Timestamp": str(int(time.time()))}
    )
    assert resp.status_code == 401


def test_missing_timestamp(app_with_auth):
    resp = app_with_auth.get("/protected", headers={"X-Signature": "abc123"})
    assert resp.status_code == 401


def test_no_headers(app_with_auth):
    resp = app_with_auth.get("/protected")
    assert resp.status_code == 401


def test_wrong_signature(app_with_auth):
    headers = make_hmac_headers("GET", "/protected", secret="wrong-secret")
    resp = app_with_auth.get("/protected", headers=headers)
    assert resp.status_code == 401


def test_expired_timestamp(app_with_auth):
    old_ts = int(time.time()) - 120
    headers = make_hmac_headers(
        "GET", "/protected", secret="test-secret", timestamp=old_ts
    )
    resp = app_with_auth.get("/protected", headers=headers)
    assert resp.status_code == 401


def test_invalid_timestamp_format(app_with_auth):
    headers = make_hmac_headers("GET", "/protected", secret="test-secret")
    headers["X-Timestamp"] = "not-a-number"
    resp = app_with_auth.get("/protected", headers=headers)
    assert resp.status_code == 401


def test_tracker_records_failure():
    tracker = AuthTracker(max_failures=3, window_seconds=300)
    tracker.record_failure("192.168.1.10")
    assert "192.168.1.10" in tracker._failures
    assert len(tracker._failures["192.168.1.10"]) == 1


def test_tracker_no_delay_below_threshold():
    tracker = AuthTracker(max_failures=3, window_seconds=300)
    tracker.record_failure("192.168.1.10")
    tracker.record_failure("192.168.1.10")
    assert not tracker.should_delay("192.168.1.10")


def test_tracker_delay_at_threshold():
    tracker = AuthTracker(max_failures=3, window_seconds=300)
    for _ in range(3):
        tracker.record_failure("192.168.1.10")
    assert tracker.should_delay("192.168.1.10")


def test_tracker_window_expiry():
    tracker = AuthTracker(max_failures=3, window_seconds=300)
    with patch("time.monotonic", return_value=1000.0):
        for _ in range(3):
            tracker.record_failure("192.168.1.10")
    with patch("time.monotonic", return_value=1400.0):
        assert not tracker.should_delay("192.168.1.10")


def test_tracker_independent_ips():
    tracker = AuthTracker(max_failures=3, window_seconds=300)
    for _ in range(3):
        tracker.record_failure("192.168.1.10")
    assert tracker.should_delay("192.168.1.10")
    assert not tracker.should_delay("192.168.1.20")


def test_backoff_delays_response_after_threshold(monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "test-secret")

    app = FastAPI()
    app.state.auth_tracker = AuthTracker(
        max_failures=3, window_seconds=300, delay_seconds=0.1
    )

    @app.exception_handler(InvalidApiKey)
    async def handle_invalid_api_key(request, exc):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing API key"},
        )

    @app.get("/protected")
    async def protected(_: None = Depends(require_hmac_auth)):
        return {"status": "ok"}

    client = TestClient(app)

    for _ in range(3):
        client.get("/protected", headers={"X-Signature": "bad"})

    start = time.monotonic()
    client.get("/protected", headers={"X-Signature": "bad"})
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1

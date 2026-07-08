import time
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from auth import require_hmac_auth, InvalidApiKey
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

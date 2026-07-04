import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from auth import require_api_key, InvalidApiKey


@pytest.fixture
def app_with_auth(monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "test-secret")

    app = FastAPI()

    @app.exception_handler(InvalidApiKey)
    async def handle_invalid_api_key(request, exc):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing API key"}
        )

    @app.get("/protected")
    def protected(key: str = Depends(require_api_key)):
        return {"status": "ok"}

    return TestClient(app)


def test_valid_api_key(app_with_auth):
    resp = app_with_auth.get("/protected", headers={"X-API-Key": "test-secret"})
    assert resp.status_code == 200


def test_missing_api_key(app_with_auth):
    resp = app_with_auth.get("/protected")
    assert resp.status_code == 401
    assert resp.json()["error"] == "Invalid or missing API key"


def test_wrong_api_key(app_with_auth):
    resp = app_with_auth.get("/protected", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401

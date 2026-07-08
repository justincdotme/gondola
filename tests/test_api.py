import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from main import create_app
from collector import Reading
from database import init_db, insert_reading
from conftest import make_hmac_headers


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


def _reading(temperature=22.5, humidity=45.0, battery=87, rssi=-42,
             recorded_at="2026-07-03T14:00:00Z"):
    return Reading(
        mac="A4:C1:38:7D:3A:14", device_name="GVH5075_3A14",
        sensor_type="govee_h5075",
        measurements={"temperature": temperature, "humidity": humidity},
        battery=battery, rssi=rssi, recorded_at=recorded_at,
    )


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("SENSOR_DB_PATH", db_path)
    app = create_app()
    app.state.collector_latest = {
        "A4:C1:38:7D:3A:14": _reading(),
    }
    app.state.collector_running = True
    db = init_db(db_path)
    insert_reading(db, _reading(recorded_at="2026-07-03T14:00:00Z"))
    insert_reading(db, _reading(temperature=22.0, humidity=44.0, rssi=-45,
                                recorded_at="2026-07-03T13:59:00Z"))
    app.state.db = db
    return TestClient(app)


def test_health_no_auth_required(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["collector_running"] is True
    assert body["sensors_seen"] == 1


def test_sensors_returns_latest(client):
    headers = make_hmac_headers("GET", "/api/v1/sensors")
    resp = client.get("/api/v1/sensors", headers=headers)
    assert resp.status_code == 200
    sensors = resp.json()["sensors"]
    assert len(sensors) == 1
    assert sensors[0]["mac"] == "A4:C1:38:7D:3A:14"
    assert sensors[0]["sensor_type"] == "govee_h5075"
    assert sensors[0]["last_reading"]["measurements"]["temperature"] == 22.5


def test_sensors_requires_auth(client):
    resp = client.get("/api/v1/sensors")
    assert resp.status_code == 401


def test_readings_ascending_order(client):
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["has_more"] is False
    assert body["readings"][0]["recorded_at"] == "2026-07-03T13:59:00Z"
    assert body["readings"][1]["recorded_at"] == "2026-07-03T14:00:00Z"


def test_readings_with_limit(client):
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14", "limit": 1},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["has_more"] is True
    assert body["readings"][0]["recorded_at"] == "2026-07-03T13:59:00Z"


def test_readings_with_from(client):
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14", "from": "2026-07-03T13:59:30Z"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["has_more"] is False
    assert body["readings"][0]["recorded_at"] == "2026-07-03T14:00:00Z"


def test_readings_with_to(client):
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14", "to": "2026-07-03T13:59:00Z"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["has_more"] is False
    assert body["readings"][0]["recorded_at"] == "2026-07-03T13:59:00Z"


def test_readings_from_to_window(client):
    db = client.app.state.db
    insert_reading(db, _reading(temperature=23.0, humidity=46.0,
                                recorded_at="2026-07-03T14:01:00Z"))
    insert_reading(db, _reading(temperature=24.0, humidity=47.0,
                                recorded_at="2026-07-03T14:02:00Z"))
    resp = client.get("/api/v1/readings", params={
        "mac": "A4:C1:38:7D:3A:14",
        "from": "2026-07-03T13:59:00Z",
        "to": "2026-07-03T14:01:00Z",
    }, headers=make_hmac_headers("GET", "/api/v1/readings"))
    body = resp.json()
    assert body["count"] == 2
    assert body["has_more"] is False
    assert body["readings"][0]["recorded_at"] == "2026-07-03T14:00:00Z"
    assert body["readings"][1]["recorded_at"] == "2026-07-03T14:01:00Z"


def test_readings_has_more(client):
    db = client.app.state.db
    for i in range(5):
        insert_reading(db, _reading(temperature=20.0 + i, humidity=40.0 + i,
                                    battery=85, rssi=-50,
                                    recorded_at=f"2026-07-03T15:0{i}:00Z"))
    resp = client.get("/api/v1/readings",
                      params={"mac": "A4:C1:38:7D:3A:14", "limit": 3},
                      headers=make_hmac_headers("GET", "/api/v1/readings"))
    body = resp.json()
    assert body["count"] == 3
    assert body["has_more"] is True
    assert body["readings"][0]["recorded_at"] == "2026-07-03T13:59:00Z"

    last_ts = body["readings"][-1]["recorded_at"]
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14", "limit": 3, "from": last_ts},
        headers=headers,
    )
    body = resp.json()
    assert body["count"] == 3
    assert body["has_more"] is True

    last_ts = body["readings"][-1]["recorded_at"]
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14", "limit": 3, "from": last_ts},
        headers=headers,
    )
    body = resp.json()
    assert body["count"] == 1
    assert body["has_more"] is False


def test_readings_invalid_from_returns_422(client):
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "A4:C1:38:7D:3A:14", "from": "not-a-date"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_readings_unknown_mac(client):
    headers = make_hmac_headers("GET", "/api/v1/readings")
    resp = client.get(
        "/api/v1/readings",
        params={"mac": "00:00:00:00:00:00"},
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "Unknown sensor"


def test_readings_requires_auth(client):
    resp = client.get("/api/v1/readings", params={"mac": "A4:C1:38:7D:3A:14"})
    assert resp.status_code == 401


def test_health_not_rate_limited(client):
    limiter = client.app.state.rate_limiter
    limiter.max_requests = 1
    client.get("/api/v1/health")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_rate_limited_returns_429(client):
    limiter = client.app.state.rate_limiter
    limiter.max_requests = 1
    headers = make_hmac_headers("GET", "/api/v1/sensors")
    client.get("/api/v1/sensors", headers=headers)
    headers = make_hmac_headers("GET", "/api/v1/sensors")
    resp = client.get("/api/v1/sensors", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers

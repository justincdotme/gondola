import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from main import create_app
from collector import Reading
from database import init_db, insert_reading


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("SENSOR_DB_PATH", db_path)
    app = create_app()
    app.state.collector_latest = {
        "A4:C1:38:7D:3A:14": Reading(
            mac="A4:C1:38:7D:3A:14",
            device_name="GVH5075_3A14",
            temperature=22.5,
            humidity=45.0,
            battery=87,
            rssi=-42,
            recorded_at="2026-07-03T14:00:00Z",
        )
    }
    app.state.collector_running = True
    db = init_db(db_path)
    insert_reading(db, "A4:C1:38:7D:3A:14", "GVH5075_3A14", 22.5, 45.0, 87, -42, "2026-07-03T14:00:00Z")
    insert_reading(db, "A4:C1:38:7D:3A:14", "GVH5075_3A14", 22.0, 44.0, 87, -45, "2026-07-03T13:59:00Z")
    app.state.db = db
    return TestClient(app)


HEADERS = {"X-API-Key": "test-key"}


def test_health_no_auth_required(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["collector_running"] is True
    assert body["sensors_seen"] == 1


def test_sensors_returns_latest(client):
    resp = client.get("/api/v1/sensors", headers=HEADERS)
    assert resp.status_code == 200
    sensors = resp.json()["sensors"]
    assert len(sensors) == 1
    assert sensors[0]["mac"] == "A4:C1:38:7D:3A:14"
    assert sensors[0]["last_reading"]["temperature"] == 22.5


def test_sensors_requires_auth(client):
    resp = client.get("/api/v1/sensors")
    assert resp.status_code == 401


def test_readings_with_limit(client):
    resp = client.get("/api/v1/readings", params={"mac": "A4:C1:38:7D:3A:14", "limit": 1}, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert len(body["readings"]) == 1


def test_readings_with_since(client):
    resp = client.get("/api/v1/readings", params={"mac": "A4:C1:38:7D:3A:14", "since": "2026-07-03T13:59:30Z"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_readings_unknown_mac(client):
    resp = client.get("/api/v1/readings", params={"mac": "00:00:00:00:00:00"}, headers=HEADERS)
    assert resp.status_code == 404
    assert resp.json()["error"] == "Unknown sensor"


def test_readings_requires_auth(client):
    resp = client.get("/api/v1/readings", params={"mac": "A4:C1:38:7D:3A:14"})
    assert resp.status_code == 401

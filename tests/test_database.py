import os
import tempfile
import pytest
from database import init_db, insert_reading, get_readings, delete_old_readings


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def db(db_path):
    return init_db(db_path)


def test_init_db_creates_table(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='readings'")
    assert cursor.fetchone() is not None


def test_init_db_enables_wal(db):
    cursor = db.execute("PRAGMA journal_mode")
    assert cursor.fetchone()[0] == "wal"


def test_insert_and_query_reading(db):
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 22.5, 45.0, 87,
                   -42, "2026-07-03T14:00:00Z")
    rows = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=10)
    assert len(rows) == 1
    assert rows[0]["mac"] == "AA:BB:CC:DD:EE:FF"
    assert rows[0]["temperature"] == 22.5
    assert rows[0]["humidity"] == 45.0
    assert rows[0]["battery"] == 87
    assert rows[0]["rssi"] == -42


def test_get_readings_respects_limit(db):
    for i in range(5):
        insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 20.0 + i,
                       40.0, 90, -40, f"2026-07-03T14:0{i}:00Z")
    rows = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=3)
    assert len(rows) == 3
    # most recent first
    assert rows[0]["temperature"] == 24.0


def test_get_readings_respects_since(db):
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 20.0, 40.0, 90,
                   -40, "2026-07-03T14:00:00Z")
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 21.0, 41.0, 90,
                   -40, "2026-07-03T15:00:00Z")
    rows = get_readings(db, "AA:BB:CC:DD:EE:FF",
                        since="2026-07-03T14:30:00Z")
    assert len(rows) == 1
    assert rows[0]["temperature"] == 21.0


def test_get_readings_unknown_mac_returns_empty(db):
    rows = get_readings(db, "00:00:00:00:00:00")
    assert rows == []


def test_delete_old_readings(db):
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 20.0, 40.0, 90,
                   -40, "2020-01-01T00:00:00Z")
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 21.0, 41.0, 90,
                   -40, "2026-07-03T14:00:00Z")
    deleted = delete_old_readings(db, days=90)
    assert deleted >= 1
    rows = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1
    assert rows[0]["temperature"] == 21.0

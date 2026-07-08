import os
import sqlite3
import tempfile
import pytest
from collector import Reading
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


def _reading(mac="AA:BB:CC:DD:EE:FF", temperature=22.5, humidity=45.0,
             battery=87, rssi=-42, recorded_at="2026-07-03T14:00:00Z"):
    return Reading(
        mac=mac, device_name="GVH5075_TEST", sensor_type="govee_h5075",
        measurements={"temperature": temperature, "humidity": humidity},
        battery=battery, rssi=rssi, recorded_at=recorded_at,
    )


def test_init_db_creates_table(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='readings'")
    assert cursor.fetchone() is not None


def test_init_db_enables_wal(db):
    cursor = db.execute("PRAGMA journal_mode")
    assert cursor.fetchone()[0] == "wal"


def test_insert_and_query_reading(db):
    insert_reading(db, _reading())
    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=10)
    assert len(rows) == 1
    assert has_more is False
    assert rows[0]["mac"] == "AA:BB:CC:DD:EE:FF"
    assert rows[0]["sensor_type"] == "govee_h5075"
    assert rows[0]["measurements"]["temperature"] == 22.5
    assert rows[0]["measurements"]["humidity"] == 45.0
    assert rows[0]["battery"] == 87
    assert rows[0]["rssi"] == -42


def test_get_readings_respects_limit(db):
    for i in range(5):
        insert_reading(db, _reading(temperature=20.0 + i,
                                    recorded_at=f"2026-07-03T14:0{i}:00Z"))
    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=3)
    assert len(rows) == 3
    assert has_more is True
    assert rows[0]["measurements"]["temperature"] == 20.0


def test_get_readings_respects_from_ts(db):
    insert_reading(db, _reading(temperature=20.0, recorded_at="2026-07-03T14:00:00Z"))
    insert_reading(db, _reading(temperature=21.0, humidity=41.0,
                                recorded_at="2026-07-03T15:00:00Z"))
    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF",
                                  from_ts="2026-07-03T14:30:00Z")
    assert len(rows) == 1
    assert has_more is False
    assert rows[0]["measurements"]["temperature"] == 21.0


def test_get_readings_respects_to_ts(db):
    insert_reading(db, _reading(temperature=20.0, recorded_at="2026-07-03T14:00:00Z"))
    insert_reading(db, _reading(temperature=21.0, humidity=41.0,
                                recorded_at="2026-07-03T15:00:00Z"))
    insert_reading(db, _reading(temperature=22.0, humidity=42.0,
                                recorded_at="2026-07-03T16:00:00Z"))
    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF",
                                  to_ts="2026-07-03T15:00:00Z")
    assert len(rows) == 2
    assert has_more is False
    assert rows[0]["measurements"]["temperature"] == 20.0
    assert rows[1]["measurements"]["temperature"] == 21.0


def test_get_readings_from_to_window(db):
    for i in range(5):
        insert_reading(db, _reading(temperature=20.0 + i,
                                    recorded_at=f"2026-07-03T14:0{i}:00Z"))
    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF",
                                  from_ts="2026-07-03T14:01:00Z",
                                  to_ts="2026-07-03T14:03:00Z")
    assert len(rows) == 2
    assert has_more is False
    assert rows[0]["measurements"]["temperature"] == 22.0
    assert rows[1]["measurements"]["temperature"] == 23.0


def test_get_readings_has_more_paging(db):
    for i in range(5):
        insert_reading(db, _reading(temperature=20.0 + i,
                                    recorded_at=f"2026-07-03T14:0{i}:00Z"))
    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=2)
    assert len(rows) == 2
    assert has_more is True
    assert rows[0]["measurements"]["temperature"] == 20.0
    assert rows[1]["measurements"]["temperature"] == 21.0

    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=2,
                                  from_ts=rows[-1]["recorded_at"])
    assert len(rows) == 2
    assert has_more is True
    assert rows[0]["measurements"]["temperature"] == 22.0
    assert rows[1]["measurements"]["temperature"] == 23.0

    rows, has_more = get_readings(db, "AA:BB:CC:DD:EE:FF", limit=2,
                                  from_ts=rows[-1]["recorded_at"])
    assert len(rows) == 1
    assert has_more is False
    assert rows[0]["measurements"]["temperature"] == 24.0


def test_get_readings_unknown_mac_returns_empty(db):
    rows, has_more = get_readings(db, "00:00:00:00:00:00")
    assert rows == []
    assert has_more is False


def test_delete_old_readings(db):
    insert_reading(db, _reading(temperature=20.0, recorded_at="2020-01-01T00:00:00Z"))
    insert_reading(db, _reading(temperature=21.0, humidity=41.0,
                                recorded_at="2026-07-03T14:00:00Z"))
    deleted = delete_old_readings(db, days=90)
    assert deleted >= 1
    rows, _ = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1
    assert rows[0]["measurements"]["temperature"] == 21.0


def test_migrate_old_schema(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac TEXT NOT NULL,
            device_name TEXT,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            battery INTEGER,
            rssi INTEGER,
            recorded_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO readings (mac, device_name, temperature, humidity, battery, rssi, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 22.5, 45.0, 87, -42, "2026-07-03T14:00:00Z"),
    )
    conn.commit()
    conn.close()

    db = init_db(db_path)
    rows, _ = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1
    assert rows[0]["sensor_type"] == "govee_h5075"
    assert rows[0]["measurements"]["temperature"] == 22.5
    assert rows[0]["measurements"]["humidity"] == 45.0
    assert rows[0]["battery"] == 87
    db.close()

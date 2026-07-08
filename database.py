import json
import sqlite3
from datetime import datetime, timedelta, timezone


def _needs_migration(conn: sqlite3.Connection) -> bool:
    cursor = conn.execute("PRAGMA table_info(readings)")
    columns = {row[1] for row in cursor.fetchall()}
    return "temperature" in columns and "sensor_type" not in columns


def _migrate_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE readings_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            mac             TEXT    NOT NULL,
            device_name     TEXT,
            sensor_type     TEXT    NOT NULL,
            measurements    TEXT    NOT NULL,
            battery         INTEGER,
            rssi            INTEGER,
            recorded_at     TEXT    NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO readings_new
            (mac, device_name, sensor_type, measurements, battery, rssi, recorded_at)
        SELECT mac, device_name, 'govee_h5075',
               json_object('temperature', temperature, 'humidity', humidity),
               battery, rssi, recorded_at
        FROM readings
    """)
    conn.execute("DROP TABLE readings")
    conn.execute("ALTER TABLE readings_new RENAME TO readings")
    conn.commit()


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='readings'"
    )
    if cursor.fetchone() is not None:
        if _needs_migration(conn):
            _migrate_schema(conn)
    else:
        conn.execute("""
            CREATE TABLE readings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                mac             TEXT    NOT NULL,
                device_name     TEXT,
                sensor_type     TEXT    NOT NULL,
                measurements    TEXT    NOT NULL,
                battery         INTEGER,
                rssi            INTEGER,
                recorded_at     TEXT    NOT NULL
            )
        """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_mac_recorded
        ON readings (mac, recorded_at DESC)
    """)
    conn.commit()
    return conn


def insert_reading(conn: sqlite3.Connection, reading) -> None:
    query = """
        INSERT INTO readings
        (mac, device_name, sensor_type, measurements, battery, rssi, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    conn.execute(query, (
        reading.mac, reading.device_name, reading.sensor_type,
        json.dumps(reading.measurements), reading.battery, reading.rssi,
        reading.recorded_at,
    ))
    conn.commit()


def get_readings(conn: sqlite3.Connection, mac: str, limit: int = 100,
                 from_ts: str | None = None,
                 to_ts: str | None = None) -> tuple[list[dict], bool]:
    clauses = ["mac = ?"]
    params: list = [mac]
    if from_ts:
        clauses.append("recorded_at > ?")
        params.append(from_ts)
    if to_ts:
        clauses.append("recorded_at <= ?")
        params.append(to_ts)
    params.append(limit + 1)
    cursor = conn.execute(
        "SELECT mac, device_name, sensor_type, measurements, battery, rssi, "
        "recorded_at FROM readings WHERE " + " AND ".join(clauses)
        + " ORDER BY recorded_at ASC LIMIT ?",
        params,
    )
    rows = [dict(r) for r in cursor.fetchall()]
    for row in rows:
        row["measurements"] = json.loads(row["measurements"])
    has_more = len(rows) > limit
    return rows[:limit], has_more


def delete_old_readings(conn: sqlite3.Connection, days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.execute("DELETE FROM readings WHERE recorded_at < ?", (cutoff,))
    conn.commit()
    conn.execute("PRAGMA optimize")
    return cursor.rowcount

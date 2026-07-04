import sqlite3
from datetime import datetime, timedelta, timezone


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mac         TEXT    NOT NULL,
            device_name TEXT,
            temperature REAL    NOT NULL,
            humidity    REAL    NOT NULL,
            battery     INTEGER,
            rssi        INTEGER,
            recorded_at TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_mac_recorded
        ON readings (mac, recorded_at DESC)
    """)
    conn.commit()
    return conn


def insert_reading(conn: sqlite3.Connection, mac: str, device_name: str | None,
                   temperature: float, humidity: float, battery: int | None,
                   rssi: int | None, recorded_at: str) -> None:
    query = """
        INSERT INTO readings
        (mac, device_name, temperature, humidity, battery, rssi, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    conn.execute(query, (mac, device_name, temperature, humidity, battery, rssi,
                         recorded_at))
    conn.commit()


def get_readings(conn: sqlite3.Connection, mac: str, limit: int = 100,
                 since: str | None = None) -> list[dict]:
    query_base = """
        SELECT mac, device_name, temperature, humidity, battery, rssi,
               recorded_at FROM readings
        WHERE mac = ?
    """
    if since:
        query = query_base + " AND recorded_at > ?"
        cursor = conn.execute(query + " ORDER BY recorded_at DESC LIMIT ?",
                              (mac, since, limit))
    else:
        cursor = conn.execute(query_base + " ORDER BY recorded_at DESC LIMIT ?",
                              (mac, limit))
    return [dict(row) for row in cursor.fetchall()]


def delete_old_readings(conn: sqlite3.Connection, days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.execute("DELETE FROM readings WHERE recorded_at < ?", (cutoff,))
    conn.commit()
    conn.execute("PRAGMA optimize")
    return cursor.rowcount

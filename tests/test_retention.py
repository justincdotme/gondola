import asyncio
import os
import tempfile

import pytest

from database import init_db, insert_reading, get_readings
from main import retention_loop


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = init_db(path)
    yield conn
    conn.close()
    os.unlink(path)


@pytest.mark.asyncio
async def test_retention_loop_deletes_old_rows(db):
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 20.0, 40.0, 90, -40, "2020-01-01T00:00:00Z")
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 21.0, 41.0, 90, -40, "2026-07-03T14:00:00Z")

    task = asyncio.create_task(retention_loop(db, retention_days=90))
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    rows, _ = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1
    assert rows[0]["temperature"] == 21.0


@pytest.mark.asyncio
async def test_retention_loop_skips_when_disabled(db):
    insert_reading(db, "AA:BB:CC:DD:EE:FF", "GVH5075_TEST", 20.0, 40.0, 90, -40, "2020-01-01T00:00:00Z")

    task = asyncio.create_task(retention_loop(db, retention_days=0))
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    rows, _ = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1

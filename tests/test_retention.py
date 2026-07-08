import asyncio
import os
import tempfile

import pytest

from collector import Reading
from database import init_db, insert_reading, get_readings
from main import retention_loop


def _reading(temperature=22.5, humidity=45.0, battery=90, rssi=-40,
             recorded_at="2026-07-03T14:00:00Z"):
    return Reading(
        mac="AA:BB:CC:DD:EE:FF", device_name="GVH5075_TEST",
        sensor_type="govee_h5075",
        measurements={"temperature": temperature, "humidity": humidity},
        battery=battery, rssi=rssi, recorded_at=recorded_at,
    )


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
    insert_reading(db, _reading(temperature=20.0, recorded_at="2020-01-01T00:00:00Z"))
    insert_reading(db, _reading(temperature=21.0, humidity=41.0,
                                recorded_at="2026-07-03T14:00:00Z"))

    task = asyncio.create_task(retention_loop(db, retention_days=90))
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    rows, _ = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1
    assert rows[0]["measurements"]["temperature"] == 21.0


@pytest.mark.asyncio
async def test_retention_loop_skips_when_disabled(db):
    insert_reading(db, _reading(temperature=20.0, recorded_at="2020-01-01T00:00:00Z"))

    task = asyncio.create_task(retention_loop(db, retention_days=0))
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    rows, _ = get_readings(db, "AA:BB:CC:DD:EE:FF")
    assert len(rows) == 1

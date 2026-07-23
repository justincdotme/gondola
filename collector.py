import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone
from dataclasses import dataclass

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from config import Config
from database import insert_reading
from sensors import detect_and_parse
import re


class WriteThrottle:
    def __init__(self, interval: int):
        self._interval = interval
        self._last_write: dict[str, float] = {}

    def should_write(self, mac: str) -> bool:
        last = self._last_write.get(mac)
        if last is None:
            return True
        return (time.monotonic() - last) >= self._interval

    def record_write(self, mac: str) -> None:
        self._last_write[mac] = time.monotonic()


logger = logging.getLogger(__name__)


_CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f-\x9f]')


def sanitize_device_name(raw: str) -> str:
    cleaned = _CONTROL_CHARS.sub('', raw)
    return cleaned.encode('utf-8')[:64].decode('utf-8', errors='ignore')


@dataclass
class Reading:
    mac: str
    device_name: str | None
    sensor_type: str
    measurements: dict[str, float | int]
    battery: int | None
    rssi: int | None
    recorded_at: str


class Collector:
    def __init__(self, config: Config, db: sqlite3.Connection):
        self._config = config
        self._db = db
        self._throttle = WriteThrottle(config.write_interval)
        self.latest_readings: dict[str, Reading] = {}
        self.running = False

    async def run(self) -> None:
        self.running = True
        scanner_kwargs = {}
        if self._config.bluetooth_adapter:
            scanner_kwargs["adapter"] = self._config.bluetooth_adapter

        async with BleakScanner(
            detection_callback=self._on_detection, **scanner_kwargs
        ):
            logger.info("BLE collector started")
            while True:
                await asyncio.sleep(1)

    def _on_detection(self, device: BLEDevice, advertisement_data: AdvertisementData) -> None:
        name = sanitize_device_name(device.name or "")
        result = detect_and_parse(advertisement_data.manufacturer_data, name)
        if result is None:
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mac = device.address

        reading = Reading(
            mac=mac,
            device_name=name,
            sensor_type=result.sensor_type,
            measurements=result.measurements,
            battery=result.battery,
            rssi=advertisement_data.rssi,
            recorded_at=now,
        )

        self.latest_readings[mac] = reading
        logger.info(
            "%s | %s | %s | %s | bat=%s | rssi=%s",
            now, mac, result.sensor_type, result.measurements,
            result.battery, advertisement_data.rssi,
        )

        if self._throttle.should_write(mac):
            insert_reading(self._db, reading)
            self._throttle.record_write(mac)

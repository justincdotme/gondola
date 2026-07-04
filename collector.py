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


GOVEE_COMPANY_ID = 0xEC88
MIN_PAYLOAD_LENGTH = 5


def parse_h5075(data: bytes | None) -> tuple[float, float, int] | None:
    if data is None or len(data) < MIN_PAYLOAD_LENGTH:
        return None

    raw_value = (data[1] << 16) | (data[2] << 8) | data[3]
    is_negative = bool(raw_value & 0x800000)
    magnitude = raw_value & 0x7FFFFF

    temperature = ((-1 if is_negative else 1) * (magnitude // 1000)) / 10
    humidity = (magnitude % 1000) / 10
    battery = data[4]

    return temperature, humidity, battery


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


@dataclass
class Reading:
    mac: str
    device_name: str | None
    temperature: float
    humidity: float
    battery: int
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
        name = device.name or ""
        if "h5075" not in name.lower():
            return

        mfr_data = advertisement_data.manufacturer_data.get(GOVEE_COMPANY_ID)
        if mfr_data is None:
            return

        result = parse_h5075(mfr_data)
        if result is None:
            return

        temperature, humidity, battery = result
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mac = device.address

        reading = Reading(
            mac=mac,
            device_name=name,
            temperature=temperature,
            humidity=humidity,
            battery=battery,
            rssi=advertisement_data.rssi,
            recorded_at=now,
        )

        self.latest_readings[mac] = reading
        logger.info(
            "%s | %s | %.1f°C | %.1f%% RH | bat=%d%% | rssi=%s | raw=%s",
            now, mac, temperature, humidity, battery,
            advertisement_data.rssi, mfr_data.hex(),
        )

        if self._throttle.should_write(mac):
            insert_reading(self._db, mac, name, temperature, humidity, battery, advertisement_data.rssi, now)
            self._throttle.record_write(mac)

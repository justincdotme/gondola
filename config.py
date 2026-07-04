import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    api_key: str
    db_path: str
    write_interval: int
    retention_days: int
    host: str
    port: int
    bluetooth_adapter: str | None
    tls_cert: str | None
    tls_key: str | None


def load_config() -> Config:
    api_key = os.environ.get("SENSOR_GATEWAY_API_KEY")
    if not api_key:
        print(
            "FATAL: SENSOR_GATEWAY_API_KEY environment variable is required",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        api_key=api_key,
        db_path=os.environ.get("SENSOR_DB_PATH", "./readings.db"),
        write_interval=int(os.environ.get("SENSOR_WRITE_INTERVAL", "60")),
        retention_days=int(os.environ.get("SENSOR_RETENTION_DAYS", "90")),
        host=os.environ.get("SENSOR_HOST", "0.0.0.0"),
        port=int(os.environ.get("SENSOR_PORT", "8075")),
        bluetooth_adapter=os.environ.get("BLUETOOTH_ADAPTER") or None,
        tls_cert=os.environ.get("SENSOR_TLS_CERT") or None,
        tls_key=os.environ.get("SENSOR_TLS_KEY") or None,
    )

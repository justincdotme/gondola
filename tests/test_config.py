import pytest
from config import load_config


def test_load_config_with_all_defaults(monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "test-key")
    cfg = load_config()
    assert cfg.api_key == "test-key"
    assert cfg.db_path == "./readings.db"
    assert cfg.write_interval == 60
    assert cfg.retention_days == 90
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8075
    assert cfg.bluetooth_adapter is None


def test_load_config_custom_values(monkeypatch):
    monkeypatch.setenv("SENSOR_GATEWAY_API_KEY", "custom-key")
    monkeypatch.setenv("SENSOR_DB_PATH", "/tmp/test.db")
    monkeypatch.setenv("SENSOR_WRITE_INTERVAL", "30")
    monkeypatch.setenv("SENSOR_RETENTION_DAYS", "0")
    monkeypatch.setenv("SENSOR_PORT", "9000")
    monkeypatch.setenv("BLUETOOTH_ADAPTER", "hci1")
    cfg = load_config()
    assert cfg.api_key == "custom-key"
    assert cfg.db_path == "/tmp/test.db"
    assert cfg.write_interval == 30
    assert cfg.retention_days == 0
    assert cfg.port == 9000
    assert cfg.bluetooth_adapter == "hci1"


def test_load_config_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("SENSOR_GATEWAY_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        load_config()

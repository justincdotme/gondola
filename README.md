# Sensor Gateway

BLE sensor gateway for Govee H5075 thermometer/hygrometers. Collects temperature, humidity, and battery readings from Bluetooth Low Energy sensors and serves them via a REST API.

## Requirements

- Python 3.11 or later
- BlueZ (Linux Bluetooth stack, required for BLE via D-Bus)
- Bluetooth adapter

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `SENSOR_GATEWAY_API_KEY` to a secure API key. See `.env.example` for the complete list of configuration options:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENSOR_GATEWAY_API_KEY` | yes | | Authentication key for API requests |
| `SENSOR_DB_PATH` | no | `./readings.db` | Path to SQLite database |
| `SENSOR_WRITE_INTERVAL` | no | `60` | Seconds between writes per sensor |
| `SENSOR_RETENTION_DAYS` | no | `90` | Days to keep readings (0 = forever) |
| `SENSOR_HOST` | no | `0.0.0.0` | Bind address |
| `SENSOR_PORT` | no | `8075` | Listen port |
| `BLUETOOTH_ADAPTER` | no | auto-detect | D-Bus adapter name |
| `SENSOR_TLS_CERT` | no | | Path to TLS certificate file |
| `SENSOR_TLS_KEY` | no | | Path to TLS private key file |

When both TLS variables are set, the server uses HTTPS.

Or use the setup script (recommended for first-time deployment):

```bash
./init.sh
```

This generates an API key, creates a self-signed TLS certificate, sets up the virtual environment, and installs dependencies.

## Running

### Development

```bash
python main.py
```

### Production

After running `init.sh`, manage the server with:

```bash
./gondola.sh --start
./gondola.sh --stop
./gondola.sh --restart
./gondola.sh --status
```

Logs are written to `gondola.log`.

## API

All endpoints except `/api/v1/health` require the `X-API-Key` header with your API key.

### `GET /api/v1/health`

Service status and uptime (no authentication).

**Response:**
```json
{
  "status": "ok",
  "collector_running": true,
  "sensors_seen": 4,
  "uptime_seconds": 3600
}
```

### `GET /api/v1/sensors`

List all sensors with their most recent reading.

**Response:**
```json
{
  "sensors": [
    {
      "mac": "4C:65:A8:D0:12:34",
      "device_name": "Govee H5075",
      "last_reading": {
        "temperature": 21.5,
        "humidity": 55.2,
        "battery": 85,
        "rssi": -67,
        "recorded_at": "2025-07-03T12:34:56+00:00"
      }
    }
  ]
}
```

### `GET /api/v1/readings?mac=...`

Historical readings for a specific sensor, ordered oldest-first for cursor-based pagination.

**Query parameters:**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `mac` | yes | | Sensor MAC address |
| `from` | no | | ISO 8601 timestamp; return readings after this time (exclusive) |
| `to` | no | | ISO 8601 timestamp; return readings up to this time (inclusive) |
| `limit` | no | 100 | Max results per page, capped at 1000 |

**Response:**
```json
{
  "mac": "A4:C1:38:7D:3A:14",
  "count": 100,
  "has_more": true,
  "readings": [
    {
      "temperature": 21.5,
      "humidity": 55.2,
      "battery": 85,
      "rssi": -67,
      "recorded_at": "2026-07-03T12:34:56Z"
    }
  ]
}
```

**Paging:** Results are ascending (oldest-first). To page through readings, pass the last `recorded_at` from the previous response as `from` in the next request. Continue until `has_more` is `false`.

OpenAPI docs are disabled in production. To generate the schema locally, temporarily remove the `docs_url=None` kwargs from `create_app()` in main.py.

## Development

Run tests:

```bash
python -m pytest tests/ -v
```

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

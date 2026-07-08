# Sensor Gateway

BLE sensor gateway for Bluetooth Low Energy environmental sensors. Collects readings such as temperature, humidity, and battery level and serves them via a REST API. Ships with a parser for the Govee H5075 thermometer/hygrometer; adding support for another sensor only requires a new parser, see [docs/writing-a-parser.md](docs/writing-a-parser.md).

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

Base path: `/api/v1`. Requests are authenticated with HMAC-SHA256 request signing, not a static API key header. See the docs below for the header format, signing examples, and full endpoint reference.

- [docs/authentication.md](docs/authentication.md): how to sign requests, clock skew, failed-auth throttling
- [docs/api-reference.md](docs/api-reference.md): endpoints, parameters, response shapes, rate limits
- [docs/building-a-consumer.md](docs/building-a-consumer.md): a practical guide to writing a client, covering TLS, pagination, and error handling

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

To add support for a new sensor, see [docs/writing-a-parser.md](docs/writing-a-parser.md).

# Gondola — Govee H5075 BLE Sensor Gateway

This project runs on a Raspberry Pi 3B to collect Bluetooth temperature/humidity readings from Govee H5075 sensors and serve them via REST API.

## Project Conventions

### Technology Stack

- **Python:** 3.11+
- **HTTP:** FastAPI + uvicorn
- **BLE:** bleak
- **Database:** SQLite (stdlib sqlite3), no ORM
- **Configuration:** environment variables only

### Structure

- **Flat layout:** No `src/` directory, no `__init__.py` files
- **Raw SQL:** All database queries use parameterized queries; no ORM abstractions
- **Configuration:** All config via `.env` file (copy from `.env.example`)

### Testing

- **Framework:** pytest
- **Async:** pytest-asyncio for async/await tests
- **HTTP:** httpx for testing FastAPI endpoints
- **Run:** `python -m pytest tests/ -v`

### Running

**Development:**
```bash
python main.py
```

**With uvicorn (production):**
```bash
uvicorn main:app --host 0.0.0.0 --port 8075
```

### Environment Variables

Required:
- `SENSOR_GATEWAY_API_KEY` — API key for authentication

Optional:
- `SENSOR_DB_PATH` — SQLite database file (default: `./readings.db`)
- `SENSOR_WRITE_INTERVAL` — Write readings to DB every N seconds (default: 60)
- `SENSOR_RETENTION_DAYS` — Purge readings older than N days (default: 90)
- `SENSOR_HOST` — Listen host (default: `0.0.0.0`)
- `SENSOR_PORT` — Listen port (default: 8075)
- `BLUETOOTH_ADAPTER` — BLE adapter name; leave blank to auto-select

## Code Standards

- Explain why, not what, in comments
- Minimum code that solves the problem
- No abstractions for single-use code
- Surgical changes only; touch what you must
- Every test must pin real logic or edge cases; never test setters/getters

# API Reference

Base path for all endpoints: `/api/v1`. See [authentication.md](authentication.md) for how to sign requests.

## Rate limiting

Authenticated endpoints are limited to 60 requests per 60 seconds per client IP. Requests over the limit get `429 Too Many Requests` with a `Retry-After` header (seconds until the window clears). `GET /api/v1/health` is exempt.

## Error format

Errors are JSON: `{"error": "<message>"}`, sometimes with extra context fields (e.g. `mac` on a 404). HTTP status communicates the error class:

| Status | Meaning |
|--------|---------|
| 401 | Missing/invalid signature; see [authentication.md](authentication.md) |
| 404 | Resource not found (e.g. unknown sensor MAC) |
| 422 | Malformed query parameter (e.g. unparsable `from`/`to` timestamp) |
| 429 | Rate limit exceeded |

## `GET /api/v1/health`

No authentication, not rate limited. Use this for connectivity checks before hitting authenticated endpoints.

**Response**
```json
{
  "status": "ok",
  "collector_running": true,
  "sensors_seen": 4,
  "uptime_seconds": 3600
}
```

## `GET /api/v1/sensors`

Every sensor Gondola has seen since it started, with its most recent reading. This reflects live BLE advertisements: it updates every time a sensor broadcasts, not only when a reading is persisted to the database.

**Response**
```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:7D:3A:14",
      "device_name": "GVH5075_3A14",
      "sensor_type": "govee_h5075",
      "last_reading": {
        "measurements": { "temperature": 21.5, "humidity": 55.2 },
        "battery": 85,
        "rssi": -67,
        "recorded_at": "2026-07-03T12:34:56Z"
      }
    }
  ]
}
```

## `GET /api/v1/readings`

Historical readings for one sensor, persisted at most once every `SENSOR_WRITE_INTERVAL` seconds (default 60) even if the sensor advertises more often. Ordered oldest-first for cursor-based pagination.

**Query parameters**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `mac` | yes | | Sensor MAC address |
| `from` | no | | ISO 8601 timestamp; readings after this time (exclusive) |
| `to` | no | | ISO 8601 timestamp; readings up to this time (inclusive) |
| `limit` | no | 100 | Max results per page, capped at 1000 |

**Response**
```json
{
  "mac": "A4:C1:38:7D:3A:14",
  "count": 100,
  "has_more": true,
  "readings": [
    {
      "sensor_type": "govee_h5075",
      "measurements": { "temperature": 21.5, "humidity": 55.2 },
      "battery": 85,
      "rssi": -67,
      "recorded_at": "2026-07-03T12:34:56Z"
    }
  ]
}
```

Returns `404` if `mac` has never reported a reading. See [building-a-consumer.md](building-a-consumer.md) for how to page through results correctly.

## Data model notes

- `measurements` is a dict keyed by metric name (`temperature`, `humidity` for the H5075). Future sensor types may add different keys, so don't assume a fixed set.
- `recorded_at` is always UTC, formatted `YYYY-MM-DDTHH:MM:SSZ`.
- `battery` and `rssi` are nullable if the advertisement didn't include them.

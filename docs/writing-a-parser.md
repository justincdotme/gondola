# Writing a Sensor Parser

Gondola isn't tied to the Govee H5075. The collector runs a small parser registry (`sensors.py`) that turns raw BLE advertisement bytes into a common shape. Adding a new sensor type means writing one function and registering it. No changes to the API, database, or collector loop are needed.

## How detection works

Every BLE advertisement carries `manufacturer_data`, a dict keyed by a Bluetooth SIG company identifier, and usually a local device name. `detect_and_parse()` walks the `PARSERS` list in order and, for each entry, checks whether the device name contains the registered pattern and whether `manufacturer_data` has an entry for the registered manufacturer ID. On the first match, it calls that entry's parser function and returns the result. Order matters if two entries could both match the same advertisement: put the more specific one first.

## The `SensorResult` contract

```python
@dataclass
class SensorResult:
    sensor_type: str
    measurements: dict[str, float | int]
    battery: int | None
```

- `sensor_type`: a stable string identifier. It's persisted in the database and returned as-is by `/api/v1/sensors` and `/api/v1/readings`. Once readings exist under a `sensor_type`, don't rename it; that orphans the existing history.
- `measurements`: whatever metrics the device reports, keyed by name (`temperature`, `humidity`, `pressure`, whatever applies). Different sensor types are expected to have different keys; consumers already treat this as an open map (see [api-reference.md](api-reference.md)).
- `battery`: percentage if the device reports one, otherwise `None`.

## Writing the parser function

A parser is a plain function: `bytes | None -> SensorResult | None`.

```python
def parse_my_sensor(data: bytes | None) -> SensorResult | None:
    if data is None or len(data) < MIN_PAYLOAD_LENGTH:
        return None

    # decode data according to the manufacturer's advertisement layout

    return SensorResult(
        sensor_type="my_sensor",
        measurements={"temperature": temperature},
        battery=battery,
    )
```

Return `None` for anything that isn't a valid reading: missing data, a short payload, an unrecognized format. BLE advertisements are unreliable and malformed packets happen; failing closed here is expected, not an error condition to handle upstream.

## Registering it

Add a tuple to `PARSERS` in `sensors.py`:

```python
PARSERS = [
    (GOVEE_COMPANY_ID, "h5075", parse_govee_h5075),
    (MY_SENSOR_COMPANY_ID, "my-sensor-name", parse_my_sensor),
]
```

- **Company ID**: the Bluetooth SIG-assigned manufacturer identifier that shows up as a key in `manufacturer_data`. Find it either in the device's documentation or by logging raw advertisements during a scan.
- **Name pattern**: a lowercase substring matched against the device's advertised local name. Keep it specific enough that it won't collide with an unrelated device from the same manufacturer.

## Testing

Follow the pattern in `tests/test_sensors.py`: a parametrized test with real captured payloads (hex string in, expected measurements out), a too-short-payload case, a `None`-input case, and a `detect_and_parse` case confirming the registry wiring picks up the new entry. No changes to `database.py`, `main.py`, or the API docs are needed, since `sensor_type` and `measurements` flow through generically end to end.

from dataclasses import dataclass


GOVEE_COMPANY_ID = 0xEC88
MIN_PAYLOAD_LENGTH = 5


@dataclass
class SensorResult:
    sensor_type: str
    measurements: dict[str, float | int]
    battery: int | None


def parse_govee_h5075(data: bytes | None) -> SensorResult | None:
    if data is None or len(data) < MIN_PAYLOAD_LENGTH:
        return None

    raw_value = (data[1] << 16) | (data[2] << 8) | data[3]
    is_negative = bool(raw_value & 0x800000)
    magnitude = raw_value & 0x7FFFFF

    temperature = ((-1 if is_negative else 1) * (magnitude // 1000)) / 10
    humidity = (magnitude % 1000) / 10
    battery = data[4]

    return SensorResult(
        sensor_type="govee_h5075",
        measurements={"temperature": temperature, "humidity": humidity},
        battery=battery,
    )


# (manufacturer_id, name_pattern, parser_fn)
PARSERS = [
    (GOVEE_COMPANY_ID, "h5075", parse_govee_h5075),
]


def detect_and_parse(manufacturer_data: dict[int, bytes], device_name: str) -> SensorResult | None:
    name_lower = device_name.lower()
    for mfr_id, name_pattern, parser_fn in PARSERS:
        if name_pattern not in name_lower:
            continue
        data = manufacturer_data.get(mfr_id)
        if data is None:
            continue
        result = parser_fn(data)
        if result is not None:
            return result
    return None

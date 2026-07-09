import pytest
from sensors import parse_govee_h5075, parse_gondola_lux, detect_and_parse, GOVEE_COMPANY_ID, ESPRESSIF_COMPANY_ID


@pytest.mark.parametrize("payload_hex,expected_temp,expected_humidity,expected_battery", [
    ("0003704c37", 22.5, 35.6, 55),
    ("0003d90d64", 25.2, 17.3, 100),
    ("00818c4c5a", -10.1, 45.2, 90),
], ids=["live-capture", "documented-example", "negative-temp"])
def test_parse_govee_h5075_valid(payload_hex, expected_temp, expected_humidity, expected_battery):
    data = bytes.fromhex(payload_hex)
    result = parse_govee_h5075(data)
    assert result is not None
    assert result.sensor_type == "govee_h5075"
    assert result.measurements["temperature"] == pytest.approx(expected_temp, abs=0.05)
    assert result.measurements["humidity"] == pytest.approx(expected_humidity, abs=0.05)
    assert result.battery == expected_battery


def test_parse_govee_h5075_too_short():
    assert parse_govee_h5075(bytes.fromhex("0003d9")) is None


def test_parse_govee_h5075_none_input():
    assert parse_govee_h5075(None) is None


def test_detect_and_parse_matches_govee():
    payload = bytes.fromhex("0003704c37")
    result = detect_and_parse({GOVEE_COMPANY_ID: payload}, "GVH5075_3A14")
    assert result is not None
    assert result.sensor_type == "govee_h5075"
    assert result.measurements["temperature"] == pytest.approx(22.5, abs=0.05)


def test_detect_and_parse_skips_unknown_device():
    payload = bytes.fromhex("0003704c37")
    assert detect_and_parse({GOVEE_COMPANY_ID: payload}, "SomeOtherDevice") is None


def test_detect_and_parse_skips_unknown_manufacturer():
    payload = bytes.fromhex("0003704c37")
    assert detect_and_parse({0x0000: payload}, "GVH5075_3A14") is None


@pytest.mark.parametrize("payload_hex,expected_lux,expected_white,expected_als,expected_battery", [
    ("01000186D201F401C2FF", 1000.50, 500, 450, None),
    ("010000000000000000FF", 0.0, 0, 0, None),
    ("0100989680FFFFFFFF55", 100000.0, 65535, 65535, 85),
], ids=["normal", "zero", "high-with-battery"])
def test_parse_gondola_lux_valid(payload_hex, expected_lux, expected_white, expected_als, expected_battery):
    data = bytes.fromhex(payload_hex)
    result = parse_gondola_lux(data)
    assert result is not None
    assert result.sensor_type == "gondola_lux"
    assert result.measurements["lux"] == pytest.approx(expected_lux, abs=0.01)
    assert result.measurements["white"] == expected_white
    assert result.measurements["als"] == expected_als
    assert result.battery == expected_battery


def test_parse_gondola_lux_short_payload():
    assert parse_gondola_lux(bytes.fromhex("01000186D201F401C2")) is None


def test_parse_gondola_lux_none_input():
    assert parse_gondola_lux(None) is None


def test_parse_gondola_lux_wrong_version():
    assert parse_gondola_lux(bytes.fromhex("02000186D201F401C2FF")) is None


def test_detect_and_parse_gondola_lux():
    payload = bytes.fromhex("01000186D201F401C2FF")
    result = detect_and_parse({ESPRESSIF_COMPANY_ID: payload}, "Gondola-Lux-01")
    assert result is not None
    assert result.sensor_type == "gondola_lux"
    assert result.measurements["lux"] == pytest.approx(1000.50, abs=0.01)


def test_detect_and_parse_skips_non_lux_name():
    payload = bytes.fromhex("01000186D201F401C2FF")
    assert detect_and_parse({ESPRESSIF_COMPANY_ID: payload}, "SomeOtherESP32") is None

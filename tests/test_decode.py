import pytest
from collector import parse_h5075


@pytest.mark.parametrize("payload_hex,expected", [
    # Live capture from GVH5075_3A14
    ("0003704c37", (22.5, 35.6, 55)),
    # Documented example
    ("0003d90d64", (25.2, 17.3, 100)),
    # Negative temperature (top bit set)
    ("00818c4c5a", (-10.1, 45.2, 90)),
], ids=["live-capture", "documented-example", "negative-temp"])
def test_parse_h5075_valid(payload_hex, expected):
    data = bytes.fromhex(payload_hex)
    result = parse_h5075(data)
    assert result is not None
    temp, humidity, battery = result
    assert temp == pytest.approx(expected[0], abs=0.05)
    assert humidity == pytest.approx(expected[1], abs=0.05)
    assert battery == expected[2]


def test_parse_h5075_too_short():
    assert parse_h5075(bytes.fromhex("0003d9")) is None


def test_parse_h5075_none_input():
    assert parse_h5075(None) is None

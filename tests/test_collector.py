import pytest
from collector import sanitize_device_name


@pytest.mark.parametrize("raw,expected", [
    ("Gondola-Lux-01", "Gondola-Lux-01"),
    ("GVH5075_3A14", "GVH5075_3A14"),
    ("has\x00null\x01chars", "hasnullchars"),
    ("\x1b[31mred\x1b[0m", "[31mred[0m"),
    ("a" * 100, "a" * 64),
    ("", ""),
    ("café" + "\x00", "café"),
    ("a" * 63 + "é", "a" * 63),
], ids=[
    "clean-gondola-name",
    "clean-govee-name",
    "null-and-control-chars",
    "ansi-escape-sequences",
    "over-64-bytes-ascii",
    "empty-string",
    "multibyte-with-control",
    "truncate-avoids-splitting-multibyte",
])
def test_sanitize_device_name(raw, expected):
    assert sanitize_device_name(raw) == expected

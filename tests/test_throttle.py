import time
import pytest
from collector import WriteThrottle


def test_first_write_always_allowed():
    throttle = WriteThrottle(interval=60)
    assert throttle.should_write("AA:BB:CC:DD:EE:FF") is True


def test_second_write_within_interval_blocked():
    throttle = WriteThrottle(interval=60)
    throttle.record_write("AA:BB:CC:DD:EE:FF")
    assert throttle.should_write("AA:BB:CC:DD:EE:FF") is False


def test_write_after_interval_allowed():
    throttle = WriteThrottle(interval=1)
    throttle.record_write("AA:BB:CC:DD:EE:FF")
    time.sleep(1.1)
    assert throttle.should_write("AA:BB:CC:DD:EE:FF") is True


def test_different_macs_independent():
    throttle = WriteThrottle(interval=60)
    throttle.record_write("AA:BB:CC:DD:EE:FF")
    assert throttle.should_write("11:22:33:44:55:66") is True

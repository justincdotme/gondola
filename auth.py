import os
from fastapi import Header


class InvalidApiKey(Exception):
    pass


def require_api_key(x_api_key: str = Header(default=None)) -> str:
    expected = os.environ.get("SENSOR_GATEWAY_API_KEY", "")
    if not x_api_key or x_api_key != expected:
        raise InvalidApiKey()
    return x_api_key

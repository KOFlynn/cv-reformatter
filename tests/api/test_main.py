"""``python -m cvr.api`` serves on the configured host and port."""

from cvr.api.__main__ import DEFAULT_HOST, DEFAULT_PORT, address


def test_the_defaults_when_unset():
    assert address({}) == (DEFAULT_HOST, DEFAULT_PORT) == ("127.0.0.1", 8000)


def test_host_and_port_from_the_environment():
    env = {"CVR_API_HOST": "0.0.0.0", "CVR_API_PORT": "8080"}
    assert address(env) == ("0.0.0.0", 8080)


def test_an_empty_value_is_the_default():
    assert address({"CVR_API_HOST": "", "CVR_API_PORT": ""}) == (
        DEFAULT_HOST,
        DEFAULT_PORT,
    )

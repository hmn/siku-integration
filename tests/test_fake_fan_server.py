"""Tests for fake fan server protocol behavior."""

from fake_fan.fake_fan_server import (
    FakeFanController,
    FUNC_READ,
    FUNC_READ_WRITE,
    PACKET_PREFIX,
    PACKET_PROTOCOL_TYPE,
)


# ruff: noqa: D103


def _build_request(
    fan: FakeFanController, func: str, data: str, *, device_id: str, password: str
) -> bytes:
    id_hex = device_id.encode("utf-8").hex().upper()
    pwd_hex = password.encode("utf-8").hex().upper()

    packet = (
        PACKET_PREFIX
        + PACKET_PROTOCOL_TYPE
        + f"{len(device_id):02X}"
        + id_hex
        + f"{len(password):02X}"
        + pwd_hex
        + func
        + data
    )
    packet += fan._checksum(packet)
    return bytes.fromhex(packet)


def _hexlist(data: bytes) -> list[str]:
    hex_str = data.hex().upper()
    return [hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]


def test_fake_fan_supports_high_byte_read_requests():
    fan = FakeFanController("0036001B4246570E", "123456")

    # App-style polling uses page 0x03 with low-byte parameters (e.g. 0x10, 0x11, 0x20).
    request = _build_request(
        fan,
        FUNC_READ,
        "FF03101120",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()
    assert "FF03" in response_hex
    assert "10" in response_hex
    assert "11" in response_hex
    assert "20" in response_hex


def test_fake_fan_supports_high_byte_read_write_requests():
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "FF032A01",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    assert fan.passive_boost_enabled is True

    # Verify checksum in generated response
    response_hexlist = _hexlist(response)
    assert fan._verify_checksum(response_hexlist) is True

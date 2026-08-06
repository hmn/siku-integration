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


def test_fake_fan_supports_page1_restore_preset_read():
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ,
        "FF012A",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()
    assert "FF01" in response_hex
    assert "2A00" in response_hex


def test_fake_fan_supports_page3_sensor_status_reads():
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ,
        "FF030405",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()
    # page 0x03 + low-byte commands 0x04 and 0x05
    assert "FF03" in response_hex
    assert "0400" in response_hex
    assert "0500" in response_hex


def test_fake_fan_page3_sensor_status_is_read_only_default_zero():
    fan = FakeFanController("0036001B4246570E", "123456")

    write_request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "FF0304010500",
        device_id="0036001B4246570E",
        password="123456",
    )
    write_response = fan.process_packet(write_request)

    assert write_response is not None

    read_request = _build_request(
        fan,
        FUNC_READ,
        "FF030405",
        device_id="0036001B4246570E",
        password="123456",
    )
    read_response = fan.process_packet(read_request)

    assert read_response is not None
    read_response_hex = read_response.hex().upper()
    assert "FF03" in read_response_hex
    assert "0400" in read_response_hex
    assert "0500" in read_response_hex


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


def test_fake_fan_legacy_read_returns_values_not_only_unsupported():
    fan = FakeFanController("1234567890123456", "1234")

    request = _build_request(
        fan,
        FUNC_READ,
        "B9010244B706070B254A4B6483863A3B3C3D3E3F",
        device_id="1234567890123456",
        password="1234",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()

    # Should contain at least some normal cmd/value pairs.
    assert "B9" in response_hex
    assert "01" in response_hex
    assert "02" in response_hex

    # Should not be a full stream of FD <cmd> unsupported markers.
    assert "FDB9FD01FD02" not in response_hex


def test_fake_fan_supports_filter_replacement_timer_setup_read():
    fan = FakeFanController("0036001B4246570E", "123456")
    fan.filter_replacement_timer_setup_days = 365

    request = _build_request(
        fan,
        FUNC_READ,
        "63",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()
    # FE 02 63 6D 01 means value is 0x016D (365) in little-endian on wire.
    assert "FE02636D01" in response_hex


def test_fake_fan_supports_room_temperature_read():
    """Test room temperature (0x21) multi-byte read."""
    fan = FakeFanController("0036001B4246570E", "123456")
    fan.room_temperature_x10 = 239  # 23.9°C

    request = _build_request(
        fan,
        FUNC_READ,
        "21",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()
    # FE 02 21 EF 00 means 239 (0x00EF) in little-endian
    assert "FE0221EF00" in response_hex


def test_fake_fan_supports_night_mode_timer_read_write():
    """Test night mode timer (0x0302) multi-byte read/write."""
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "FF03FE0202301001",  # FF 03 (page 0x03) FE 02 (size marker) 02 (cmd) 30 10 (16:48 in LE)
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    # 16 * 60 + 48 = 1008 minutes
    assert fan.night_mode_timer_minutes == 1008

    response_hex = response.hex().upper()
    # Should contain the set value in response
    assert "FF03" in response_hex or "FE0202" in response_hex


def test_fake_fan_supports_party_mode_timer_read_write():
    """Test party mode timer (0x0303) multi-byte read/write."""
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "FF03FE0203001D01",  # FF 03 (page 0x03) FE 02 (size marker) 03 (cmd) 00 1D (29:00 in LE)
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    # 29 * 60 + 0 = 1740 minutes
    assert fan.party_mode_timer_minutes == 1740


def test_fake_fan_supports_iaq_index_read():
    """Test IAQ index (0x0320) multi-byte read."""
    fan = FakeFanController("0036001B4246570E", "123456")
    fan.iaq_index = 42

    request = _build_request(
        fan,
        FUNC_READ,
        "FF0320",  # FF 03 (page 0x03) 20 (command)
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    response_hex = response.hex().upper()
    # Should contain page 0x03, command 20, and value 2A 00 (42 in little-endian)
    assert "FF03" in response_hex
    assert "20" in response_hex
    assert "2A" in response_hex


def test_fake_fan_supports_preset_speed_commands():
    """Test preset speed commands (0x3A-0x3F) read/write."""
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "3A643B64",  # Set supply_speed_1 (0x3A) and exhaust_speed_1 (0x3B) to 100 (0x64)
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    assert fan.preset_speeds["supply_speed_1"] == 100
    assert fan.preset_speeds["exhaust_speed_1"] == 100


def test_fake_fan_supports_passive_ventilation_modes():
    """Test passive ventilation mode commands."""
    fan = FakeFanController("0036001B4246570E", "123456")

    # Enable passive boost
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

    # Enable passive ventilation mode
    request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "FF032B01",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)
    assert response is not None
    assert fan.passive_ventilation_mode is True

    # Verify in response
    response_hex = response.hex().upper()
    assert "2B01" in response_hex


def test_fake_fan_supports_filter_replacement_timer_setup_read_write():
    fan = FakeFanController("0036001B4246570E", "123456")

    request = _build_request(
        fan,
        FUNC_READ_WRITE,
        "FE02634601",
        device_id="0036001B4246570E",
        password="123456",
    )

    response = fan.process_packet(request)

    assert response is not None
    assert fan.filter_replacement_timer_setup_days == 326

    response_hex = response.hex().upper()
    assert "FE02634601" in response_hex

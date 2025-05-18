"""Tests for SikuV1Api."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from custom_components.siku.api_v1 import (
    FEEDBACK_PACKET_PREFIX,
    OperationMode,
    SikuV1Api,
    SpeedSelection,
    SpeedManual,
    Direction,
    Timer,
    OffOn,
    TimerSeconds,
    HumiditySensorThreshold,
    HumidityLevel,
    NoYes,
    NoYesYes,
    SPEED_MANUAL_MIN,
)

# ruff: noqa: D103


@pytest.fixture
def api():
    return SikuV1Api("127.0.0.1", 12345)


@pytest.mark.asyncio
async def test_control_packet_valid(api):
    packet = await api._control_packet([("speed", SpeedSelection.LOW)])
    assert isinstance(packet, bytes)
    assert packet.startswith(b"\x04")


@pytest.mark.asyncio
async def test_control_packet_invalid_command(api):
    with pytest.raises(ValueError):
        await api._control_packet([("invalid", 1)])


@pytest.mark.asyncio
async def test_control_packet_invalid_value_type(api):
    with pytest.raises(TypeError):
        await api._control_packet([("speed", "not_an_enum")])


@pytest.mark.asyncio
async def test_control_packet_none_value(api):
    packet = await api._control_packet([("status", None)])
    assert isinstance(packet, bytes)
    assert packet.startswith(b"\x01")


@pytest.mark.asyncio
async def test_send_command_success(api):
    fake_response = (
        FEEDBACK_PACKET_PREFIX
        + b"\x03\x01\x04\x01\x05\x16\x06\x00\x08\x40\x09\x00\x11\x50\x0c\x00\x0d\x00\x0e\x00\x0f\x00\x10\x00\x11\x50\x12\x00\x13\x00\x14\x00\x00\x00\x15\x00\x00\x00\x16\x00\x00\x00\x17\x00\x00\x00\x18\x00\x19\x00\x1a\x00\x1b\x00\x1c\x00\x1d\x00\x1e\x00\x1f\x00\x20\x01\x21\x01\x22\x01\x23\x01\x25\x05\x26\x00\x27\x00"
    )
    with patch("socket.socket") as mock_socket:
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.recvfrom.return_value = (fake_response, ("127.0.0.1", 12345))
        result = await api._send_command(b"\x01\x00")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)
        assert result[0] == "03"


@pytest.mark.asyncio
async def test_send_command_timeout(api):
    with patch("socket.socket") as mock_socket:
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.recvfrom.side_effect = TimeoutError
        with pytest.raises(TimeoutError):
            await api._send_command(b"\x01\x00")


@pytest.mark.asyncio
async def test_translate_response(api):
    # Simulate a response with status ON, speed HIGH, direction VENTILATION, etc.
    hexlist = [
        "03",
        "01",  # status: ON
        "04",
        "03",  # speed: HIGH
        "05",
        "16",  # manual_speed: 22
        "06",
        "00",  # direction: VENTILATION
        "08",
        "40",  # humidity_level: 64
        "09",
        "00",  # operation_mode: REGULAR
        "0b",
        "50",  # humidity_sensor_threshold: 80
        "12",
        "01",  # filter_end_of_life: YES
        "14",
        "01",  # boost_mode_after_sensor: YES
        "0e",
        "00",
        "00",
        "05",  # countdown_timer: 10 sec
    ]
    result = await api._translate_response(hexlist)
    assert result["status"] == OffOn.ON
    assert result["speed"] == SpeedSelection.HIGH
    assert int(result["manual_speed"]) == int(SpeedManual(22))
    assert result["direction"] == Direction.VENTILATION
    assert int(result["humidity_level"]) == int(HumidityLevel(64))
    assert result["operation_mode"] == OperationMode.REGULAR
    assert int(result["humidity_sensor_threshold"]) == int(HumiditySensorThreshold(80))
    assert result["filter_end_of_life"] == NoYes.YES
    assert result["boost_mode_after_sensor"] == NoYesYes.YES
    assert int(result["timer_countdown"]) == int(TimerSeconds(5))


@pytest.mark.asyncio
async def test_format_response(api):
    data = {
        "status": OffOn.ON,
        "speed": SpeedSelection.LOW,
        "manual_speed": SpeedManual(SPEED_MANUAL_MIN),
        "direction": Direction.HEAT_RECOVERY,
        "operation_mode": Timer.AUTO,
        "humidity_level": HumidityLevel(50),
        "filter_end_of_life": NoYes.NO,
        "timer_countdown": TimerSeconds(0),
        "boost_mode_after_sensor": NoYesYes.NO,
        "boost_mode_timer": TimerSeconds(0),
        "night_mode_timer": TimerSeconds(0),
        "party_mode_timer": TimerSeconds(0),
    }
    formatted = await api._format_response(data)
    assert formatted["is_on"] is True
    assert formatted["speed"] == SpeedSelection.LOW
    assert formatted["oscillating"] is True
    assert formatted["alarm"] is False
    assert formatted["version"] == "1"


@pytest.mark.asyncio
async def test_power_on_off(api):
    # Patch _send_command and _translate_response to simulate device state
    with (
        patch.object(api, "_send_command", new=AsyncMock(return_value=["03", "00"])),
        patch.object(
            api,
            "_translate_response",
            new=AsyncMock(
                return_value={
                    "status": OffOn.OFF,
                    "speed": SpeedSelection.LOW,
                    "manual_speed": SpeedManual(SPEED_MANUAL_MIN),
                    "direction": Direction.VENTILATION,
                    "operation_mode": Timer.AUTO,
                    "humidity_level": HumidityLevel(50),
                    "filter_end_of_life": NoYes.NO,
                    "timer_countdown": TimerSeconds(0),
                    "boost_mode_after_sensor": NoYesYes.NO,
                    "boost_mode_timer": TimerSeconds(0),
                    "night_mode_timer": TimerSeconds(0),
                    "party_mode_timer": TimerSeconds(0),
                }
            ),
        ),
        patch.object(
            api, "_format_response", new=AsyncMock(return_value={"is_on": True})
        ),
    ):
        result = await api.power_on()
        assert result["is_on"] is True

    with (
        patch.object(api, "_send_command", new=AsyncMock(return_value=["03", "01"])),
        patch.object(
            api,
            "_translate_response",
            new=AsyncMock(
                return_value={
                    "status": OffOn.ON,
                    "speed": SpeedSelection.LOW,
                    "manual_speed": SpeedManual(SPEED_MANUAL_MIN),
                    "direction": Direction.VENTILATION,
                    "operation_mode": Timer.AUTO,
                    "humidity_level": HumidityLevel(50),
                    "filter_end_of_life": NoYes.NO,
                    "timer_countdown": TimerSeconds(0),
                    "boost_mode_after_sensor": NoYesYes.NO,
                    "boost_mode_timer": TimerSeconds(0),
                    "night_mode_timer": TimerSeconds(0),
                    "party_mode_timer": TimerSeconds(0),
                }
            ),
        ),
        patch.object(
            api, "_format_response", new=AsyncMock(return_value={"is_on": False})
        ),
    ):
        result = await api.power_off()
        assert result["is_on"] is False


@pytest.mark.asyncio
async def test_direction_invalid(api):
    with pytest.raises(ValueError):
        await api.direction("invalid_direction")

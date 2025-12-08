"""Tests for SikuV2Api."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from custom_components.siku.api_v2 import SPEED_MANUAL_MAX, SPEED_MANUAL_MIN, SikuV2Api
from custom_components.siku.const import (
    FAN_SPEEDS,
    DIRECTIONS,
    DIRECTION_FORWARD,
    DIRECTION_ALTERNATING,
)

# ruff: noqa: D103


@pytest.fixture
def api():
    return SikuV2Api("127.0.0.1", 12345, "1234567890abcdef", "pass1234")


@pytest.mark.asyncio
async def test_status(api):
    with (
        patch.object(
            api,
            "_send_command",
            new=AsyncMock(return_value=["FDFD", "02", "10", "12", "08", "06"]),
        ),
        patch.object(
            api, "_parse_response", new=AsyncMock(return_value={"01": "01", "02": "01"})
        ),
        patch.object(
            api,
            "_translate_response",
            new=AsyncMock(return_value={"is_on": True, "speed": "01"}),
        ),
    ):
        result = await api.status()
        assert result["is_on"] is True
        assert result["speed"] == "01"


@pytest.mark.asyncio
async def test_status_manual(api):
    with patch.object(
        api,
        "_send_command",
        new=AsyncMock(
            return_value=[
                "FD",
                "FD",
                "02",
                "10",
                "30",
                "30",
                "32",
                "45",
                "30",
                "30",
                "32",
                "32",
                "35",
                "37",
                "34",
                "36",
                "35",
                "37",
                "30",
                "34",
                "08",
                "44",
                "65",
                "52",
                "6F",
                "6F",
                "73",
                "32",
                "34",
                "06",
                "FE",
                "02",
                "B9",
                "03",
                "00",
                "01",
                "01",
                "02",
                "FF",
                "44",
                "7C",
                "B7",
                "01",
                "06",
                "00",
                "07",
                "00",
                "FE",
                "03",
                "0B",
                "00",
                "00",
                "00",
                "25",
                "33",
                "FE",
                "02",
                "4A",
                "84",
                "03",
                "FE",
                "04",
                "64",
                "2F",
                "0F",
                "55",
                "00",
                "83",
                "00",
                "FE",
                "06",
                "86",
                "00",
                "09",
                "08",
                "07",
                "E8",
                "07",
                "9C",
                "11",
            ]
        ),
    ):
        result = await api.status()
        assert result["is_on"] is True
        assert result["speed"] == "255"
        assert result["manual_speed_selected"] is True
        # check that manual speed is in range and is equal to the calculated value 49%
        assert result["manual_speed"] >= SPEED_MANUAL_MIN
        assert result["manual_speed"] <= SPEED_MANUAL_MAX
        assert result["manual_speed"] == int(SPEED_MANUAL_MAX / 100 * 49)
        assert result["manual_speed_low_high_range"] == (
            float(SPEED_MANUAL_MIN),
            float(SPEED_MANUAL_MAX),
        )
        assert result["oscillating"] is False
        assert result["direction"] == "alternating"
        assert result["boost"] is False
        assert result["mode"] == "auto"
        assert result["humidity"] == 51
        assert result["rpm"] == 900
        assert result["firmware"] == "0.7"
        assert result["filter_timer_days"] == 5115
        assert result["timer_countdown"] == 0
        assert result["alarm"] is False
        assert result["version"] == "2"


@pytest.mark.asyncio
async def test_power_on(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(api, "status", new=AsyncMock(return_value={"is_on": True})),
    ):
        result = await api.power_on()
        assert result["is_on"] is True


@pytest.mark.asyncio
async def test_power_off(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(api, "status", new=AsyncMock(return_value={"is_on": False})),
    ):
        result = await api.power_off()
        assert result["is_on"] is False


@pytest.mark.asyncio
async def test_speed_valid(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(
            api, "status", new=AsyncMock(return_value={"speed": FAN_SPEEDS[0]})
        ),
    ):
        result = await api.speed(FAN_SPEEDS[0])
        assert result["speed"] == FAN_SPEEDS[0]


@pytest.mark.asyncio
async def test_speed_invalid(api):
    with pytest.raises(ValueError):
        await api.speed("invalid")


@pytest.mark.asyncio
async def test_speed_manual(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(api, "status", new=AsyncMock(return_value={"manual_speed": 100})),
    ):
        result = await api.speed_manual("50")
        assert "manual_speed" in result


@pytest.mark.asyncio
async def test_speed_manual_hex_formatting_bug(api):
    """Test that speed_manual correctly formats the speed value as hexadecimal.

    This test verifies the fix for the bug where integer speed values were incorrectly
    concatenated as decimal strings instead of being formatted as hex.
    For example, speed 123 (decimal) should be formatted as "7B" (hex).
    The command should be "447B" (44 is COMMAND_MANUAL_SPEED, 7B is hex for 123).
    """
    with (
        patch.object(api, "_send_command", new=AsyncMock()) as mock_send,
        patch.object(api, "status", new=AsyncMock(return_value={"manual_speed": 123})),
    ):
        # 48.6% of 255 ≈ 123, which should be formatted as hex "7B"
        result = await api.speed_manual(48.6)

        # Verify that _send_command was called with the correct hex-formatted command
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        command_data = call_args[1]  # Second argument is the data

        # The command should be "447B" (COMMAND_MANUAL_SPEED + hex(123))
        # not "44123" (COMMAND_MANUAL_SPEED + decimal 123)
        assert command_data == "02FF447B", (
            f"Expected '02FF447B' but got: {command_data}"
        )

        # Verify the result
        assert result["manual_speed"] == 123


@pytest.mark.asyncio
async def test_direction_valid(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(
            api,
            "status",
            new=AsyncMock(return_value={"direction": DIRECTIONS[DIRECTION_FORWARD]}),
        ),
    ):
        result = await api.direction(DIRECTION_FORWARD)
        assert result["direction"] == DIRECTIONS[DIRECTION_FORWARD]


@pytest.mark.asyncio
async def test_direction_invalid(api):
    with pytest.raises(ValueError):
        await api.direction("invalid")


@pytest.mark.asyncio
async def test_direction_value_translation(api):
    # Test passing the value instead of the key
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(
            api,
            "status",
            new=AsyncMock(
                return_value={"direction": DIRECTIONS[DIRECTION_ALTERNATING]}
            ),
        ),
    ):
        result = await api.direction(DIRECTIONS[DIRECTION_ALTERNATING])
        assert result["direction"] == DIRECTIONS[DIRECTION_ALTERNATING]


@pytest.mark.asyncio
async def test_sleep(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(api, "status", new=AsyncMock(return_value={"mode": "sleep"})),
    ):
        result = await api.sleep()
        assert result["mode"] == "sleep"


@pytest.mark.asyncio
async def test_party(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(api, "status", new=AsyncMock(return_value={"mode": "party"})),
    ):
        result = await api.party()
        assert result["mode"] == "party"


@pytest.mark.asyncio
async def test_reset_filter_alarm(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        patch.object(api, "status", new=AsyncMock(return_value={"alarm": False})),
    ):
        result = await api.reset_filter_alarm()
        assert result["alarm"] is False


@pytest.mark.asyncio
async def test_send_command_timeout(api):
    with (
        patch.object(
            api._udp, "request", new=AsyncMock(side_effect=asyncio.TimeoutError)
        ),
        pytest.raises(TimeoutError),
    ):
        await api._send_command("01", "deadbeef")


@pytest.mark.asyncio
async def test_send_command_checksum_error(api):
    # Patch _verify_checksum to return False
    with (
        patch.object(api._udp, "request", new=AsyncMock(return_value=b"deadbeef")),
        patch.object(api, "_verify_checksum", return_value=False),
        pytest.raises(ValueError),
    ):
        await api._send_command("01", "deadbeef")


def test_checksum_and_hexlist(api):
    # Test _checksum and _hexlist helpers
    data = "AABBCCDD"
    hexlist = api._hexlist(data)
    assert hexlist == ["AA", "BB", "CC", "DD"]
    checksum = api._checksum(data)
    assert isinstance(checksum, str)
    assert len(checksum) == 4


def test_build_packet(api):
    # Test _build_packet helper
    packet = api._build_packet("01", "AABB")
    assert isinstance(packet, str)
    assert packet.startswith("FDFD")
    assert len(packet) > 10

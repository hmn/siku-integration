"""Tests for SikuV2Api."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.siku.api_v2 import SikuV2Api
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
    with patch("socket.socket") as mock_socket:
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.recvfrom.side_effect = TimeoutError
        with pytest.raises(TimeoutError):
            await api._send_command("01", "deadbeef")


@pytest.mark.asyncio
async def test_send_command_checksum_error(api):
    # Patch _verify_checksum to return False
    with (
        patch("socket.socket") as mock_socket,
        patch.object(api, "_verify_checksum", return_value=False),
    ):
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"deadbeef", ("127.0.0.1", 12345))
        with pytest.raises(ValueError):
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

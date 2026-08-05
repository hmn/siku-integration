"""Tests for SikuV2Api."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from custom_components.siku.api_v2 import (
    PRESET_SPEED_COMMANDS,
    SPEED_MANUAL_MAX,
    SPEED_MANUAL_MIN,
    SPEED_PRESET_MAX,
    SPEED_PRESET_MIN,
    SikuV2Api,
)
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
        assert result["filter_timer_minutes"] == 123347
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


# ---------------------------------------------------------------------------
# Filter timer tests
#
# Per Blauberg spec (parameter 0x64):
#   Byte 1: minutes (0…59)
#   Byte 2: hours   (0…23)
#   Byte 3: days    (0…181)
#   Byte size: 3  (spec), but devices may send a larger size with leading 0x00 padding
#
# _parse_response receives bytes via RETURN_VALUE_SIZE (0xFE) and reverses
# their byte order before storing them, so data["64"] is laid out as:
#
#   size=3 (spec):  [days][hours][minutes]               → 6 hex chars
#   size=4 (padded):[00][days][hours][minutes]            → 8 hex chars
#   size=5 (padded):[00][00][days][hours][minutes]        → 10 hex chars
#
# _translate_response uses negative indexing so minutes/hours/days are always
# the last 3 bytes regardless of leading padding:
#   minutes = raw[-2:]
#   hours   = raw[-4:-2]
#   days    = raw[-6:-4]
#
# _translate_response then computes:
#   filter_timer_minutes = days * 24 * 60 + hours * 60 + minutes
# ---------------------------------------------------------------------------

_HEADER = (
    ["FD", "FD", "02", "10"]
    + ["30"] * 16  # 16 id bytes (arbitrary)
    + ["08"]
    + ["34"] * 8  # 8 password bytes (arbitrary)
    + ["06"]  # FUNC_RESULT
)
_CHECKSUM = ["00", "00"]  # ignored by _parse_response iteration boundary


def _build_filter_timer_hexlist(
    minutes_val: int, hours_val: int, days_val: int, size: int = 4
) -> list[str]:
    """Build a minimal valid response hexlist containing only a filter timer field.

    The packet structure mirrors what _parse_response expects:
      FDFD + protocol(02) + id_size(10) + 16 id bytes + pass_size(08) +
      8 password bytes + FUNC_RESULT(06) + data bytes + 2 checksum bytes.

    The filter timer is sent as RETURN_VALUE_SIZE(FE) + size byte + cmd(64) +
    <size> data bytes on the wire: [minutes, hours, days, 00 * (size-3)].
    _parse_response reverses those bytes, producing data["64"] with the last
    3 bytes always being [days, hours, minutes].

    Args:
        minutes_val: 0…59
        hours_val:   0…23
        days_val:    0…181
        size:        total byte count sent by the device (spec=3, typical hardware=4)

    """
    if size < 3:
        raise ValueError("size must be >= 3 (spec minimum)")
    padding = ["00"] * (size - 3)
    data_bytes = (
        ["FE", f"{size:02X}", "64"]
        + [f"{minutes_val:02X}", f"{hours_val:02X}", f"{days_val:02X}"]
        + padding
    )
    return _HEADER + data_bytes + _CHECKSUM


# --- translate-only tests (feed data["64"] directly) -----------------------


@pytest.mark.asyncio
async def test_filter_timer_translate_missing_key(api):
    """filter_timer_minutes defaults to 0 when the key is absent from the response."""
    result = await api._translate_response({})
    assert result["filter_timer_minutes"] == 0


# size=3 (spec-exact, no padding) reversed layout: "DDHHMM"
@pytest.mark.asyncio
async def test_filter_timer_translate_size3_min(api):
    """size=3, all zeros → 0 minutes."""
    result = await api._translate_response({"64": "000000"})
    assert result["filter_timer_minutes"] == 0


@pytest.mark.asyncio
async def test_filter_timer_translate_size3_max(api):
    """size=3, spec max: 181d 23h 59m → 262079 minutes."""
    # reversed: B5 17 3B
    result = await api._translate_response({"64": "B5173B"})
    assert result["filter_timer_minutes"] == 181 * 24 * 60 + 23 * 60 + 59  # 262079


@pytest.mark.asyncio
async def test_filter_timer_translate_size3_only_minutes(api):
    """size=3, only minutes set (30 min)."""
    result = await api._translate_response({"64": "00001E"})
    assert result["filter_timer_minutes"] == 30


@pytest.mark.asyncio
async def test_filter_timer_translate_size3_only_hours(api):
    """size=3, only hours set (12 h = 720 min)."""
    result = await api._translate_response({"64": "000C00"})
    assert result["filter_timer_minutes"] == 12 * 60  # 720


@pytest.mark.asyncio
async def test_filter_timer_translate_size3_only_days(api):
    """size=3, only days set (100 days = 144 000 min)."""
    result = await api._translate_response({"64": "640000"})
    assert result["filter_timer_minutes"] == 100 * 24 * 60  # 144000


# size=4 (one padding byte, typical hardware) reversed layout: "00DDHHMM"
@pytest.mark.asyncio
async def test_filter_timer_translate_size4_min(api):
    """size=4 (1 padding byte), all zeros → 0 minutes."""
    result = await api._translate_response({"64": "00000000"})
    assert result["filter_timer_minutes"] == 0


@pytest.mark.asyncio
async def test_filter_timer_translate_size4_max(api):
    """size=4, spec max: 181d 23h 59m → 262079 minutes."""
    result = await api._translate_response({"64": "00B5173B"})
    assert result["filter_timer_minutes"] == 181 * 24 * 60 + 23 * 60 + 59  # 262079


@pytest.mark.asyncio
async def test_filter_timer_translate_size4_known_debug_value(api):
    """size=4, real debug capture: 23d 22h 20m → raw 00171614 → 34460 minutes."""
    result = await api._translate_response({"64": "00171614"})
    assert result["filter_timer_minutes"] == 23 * 24 * 60 + 22 * 60 + 20  # 34460


# size=5 (two padding bytes) reversed layout: "0000DDHHMM"
@pytest.mark.asyncio
async def test_filter_timer_translate_size5_min(api):
    """size=5 (2 padding bytes), all zeros → 0 minutes."""
    result = await api._translate_response({"64": "0000000000"})
    assert result["filter_timer_minutes"] == 0


@pytest.mark.asyncio
async def test_filter_timer_translate_size5_max(api):
    """size=5, spec max: 181d 23h 59m → 262079 minutes."""
    result = await api._translate_response({"64": "0000B5173B"})
    assert result["filter_timer_minutes"] == 181 * 24 * 60 + 23 * 60 + 59  # 262079


# --- parse + translate round-trip tests -------------------------------------


@pytest.mark.asyncio
async def test_filter_timer_parse_size3_min(api):
    """size=3 round-trip: all zeros → data["64"]='000000' → 0 minutes."""
    hexlist = _build_filter_timer_hexlist(0, 0, 0, size=3)
    data = await api._parse_response(hexlist)
    assert data["64"] == "000000"
    assert (await api._translate_response(data))["filter_timer_minutes"] == 0


@pytest.mark.asyncio
async def test_filter_timer_parse_size3_max(api):
    """size=3 round-trip: spec max 181d 23h 59m → data["64"]='B5173B' → 262079 min."""
    hexlist = _build_filter_timer_hexlist(59, 23, 181, size=3)
    data = await api._parse_response(hexlist)
    assert data["64"] == "B5173B"
    assert (await api._translate_response(data))[
        "filter_timer_minutes"
    ] == 181 * 24 * 60 + 23 * 60 + 59


@pytest.mark.asyncio
async def test_filter_timer_parse_size4_min(api):
    """size=4 (hardware default) round-trip: all zeros → data["64"]='00000000' → 0 min."""
    hexlist = _build_filter_timer_hexlist(0, 0, 0, size=4)
    data = await api._parse_response(hexlist)
    assert data["64"] == "00000000"
    assert (await api._translate_response(data))["filter_timer_minutes"] == 0


@pytest.mark.asyncio
async def test_filter_timer_parse_size4_max(api):
    """size=4 round-trip: spec max 181d 23h 59m → data["64"]='00B5173B' → 262079 min."""
    hexlist = _build_filter_timer_hexlist(59, 23, 181, size=4)
    data = await api._parse_response(hexlist)
    assert data["64"] == "00B5173B"
    assert (await api._translate_response(data))[
        "filter_timer_minutes"
    ] == 181 * 24 * 60 + 23 * 60 + 59


@pytest.mark.asyncio
async def test_filter_timer_parse_size4_known_debug(api):
    """size=4 round-trip: real debug capture 23d 22h 20m → data["64"]='00171614' → 34460 min."""
    hexlist = _build_filter_timer_hexlist(20, 22, 23, size=4)
    data = await api._parse_response(hexlist)
    assert data["64"] == "00171614"
    assert (await api._translate_response(data))[
        "filter_timer_minutes"
    ] == 23 * 24 * 60 + 22 * 60 + 20


@pytest.mark.asyncio
async def test_filter_timer_parse_size5_max(api):
    """size=5 round-trip: spec max 181d 23h 59m → data["64"]='0000B5173B' → 262079 min."""
    hexlist = _build_filter_timer_hexlist(59, 23, 181, size=5)
    data = await api._parse_response(hexlist)
    assert data["64"] == "0000B5173B"
    assert (await api._translate_response(data))[
        "filter_timer_minutes"
    ] == 181 * 24 * 60 + 23 * 60 + 59


# --- supply/exhaust fan speeds (the intake/exhaust balance) -----------------


@pytest.mark.asyncio
async def test_preset_speed(api):
    """The parameter byte is followed by the speed as hex."""
    with (
        patch.object(api, "_send_command", new=AsyncMock()) as mock_send,
        patch.object(
            api,
            "status",
            new=AsyncMock(return_value={"preset_speeds": {"exhaust_speed_1": 39}}),
        ),
    ):
        result = await api.preset_speed("exhaust_speed_1", 39)

        assert mock_send.call_args[0][1] == "3B27"
        assert result["preset_speeds"]["exhaust_speed_1"] == 39


@pytest.mark.asyncio
@pytest.mark.parametrize("speed", [SPEED_PRESET_MIN - 1, SPEED_PRESET_MAX + 1])
async def test_preset_speed_out_of_range(api, speed):
    with (
        patch.object(api, "_send_command", new=AsyncMock()),
        pytest.raises(ValueError),
    ):
        await api.preset_speed("supply_speed_1", speed)


@pytest.mark.asyncio
async def test_status_reads_preset_speeds(api):
    with (
        patch.object(api, "_send_command", new=AsyncMock()) as mock_send,
        patch.object(api, "_parse_response", new=AsyncMock(return_value={})),
    ):
        await api.status()

        for command in PRESET_SPEED_COMMANDS.values():
            assert command in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_preset_speeds_translate(api):
    """Parameters the fan did not answer are left out."""
    result = await api._translate_response({"3A": "33", "3B": "27"})

    assert result["preset_speeds"] == {"supply_speed_1": 51, "exhaust_speed_1": 39}
    assert (await api._translate_response({}))["preset_speeds"] == {}


@pytest.mark.asyncio
async def test_parse_response_supports_high_byte_page_switch(api):
    """The parser should support 0xFF high-byte commands used by newer app traffic."""
    hexlist = _HEADER + ["FF", "03", "10", "01", "11", "02", "20", "00"] + _CHECKSUM

    data = await api._parse_response(hexlist)

    assert data["0310"] == "01"
    assert data["0311"] == "02"
    assert data["0320"] == "00"


@pytest.mark.asyncio
async def test_parse_response_supports_change_func_special_command(api):
    """The parser should skip 0xFC function-change markers instead of failing."""
    hexlist = _HEADER + ["FC", "01", "01", "01"] + _CHECKSUM

    data = await api._parse_response(hexlist)

    assert data["01"] == "01"


@pytest.mark.asyncio
async def test_translate_response_uses_fan2_rpm_fallback(api):
    """If 0x4A is absent, use 0x4B for RPM."""
    result = await api._translate_response({"4B": "84"})
    assert result["rpm"] == 132


@pytest.mark.asyncio
async def test_parse_translate_app_traffic_replay_issue_171(api):
    """Replay-style packet with app-like ordering and page-3 parameters.

    Mirrors the DUKA S8 traffic pattern from issue #171 where the payload contains:
    - base-page fields (06/07/0B/25/4B/66/83/B9)
    - FF 03 page switch followed by low bytes 12/20/11/10
    """
    hexlist = (
        _HEADER
        + [
            "06",
            "00",  # boost off
            "07",
            "00",  # mode off/auto fallback
            "FE",
            "03",
            "0B",
            "00",
            "00",
            "00",  # timer countdown (sec/min/hour on wire)
            "FE",
            "02",
            "21",
            "F6",
            "00",  # room temperature=24.6C (0x00F6 / 10)
            "25",
            "33",  # humidity=51
            "FE",
            "02",
            "4B",
            "84",
            "03",  # fan2 rpm=900 (little-endian on wire)
            "66",
            "05",  # boost delay (not translated yet)
            "83",
            "00",  # no alarm
            "B9",
            "03",  # unit type
            "FF",
            "03",  # high-byte page switch
            "FE",
            "02",
            "02",
            "1E",
            "00",  # night mode timer setpoint: 00:30 => 30 min
            "FE",
            "02",
            "03",
            "0F",
            "01",  # party mode timer setpoint: 01:15 => 75 min
            "12",
            "01",
            "FE",
            "02",
            "20",
            "2E",
            "00",  # IAQ index=46 (0x002E)
            "11",
            "02",
            "10",
            "01",
        ]
        + _CHECKSUM
    )

    data = await api._parse_response(hexlist)
    translated = await api._translate_response(data)

    # page-3 commands are retained with full 16-bit command ids
    assert data["0312"] == "01"
    assert data["0320"] == "002E"
    assert data["0311"] == "02"
    assert data["0310"] == "01"

    # v2 translation remains backwards compatible while accepting this payload
    assert translated["boost"] is False
    assert translated["timer_mode"] == "off"
    assert translated["mode"] == "auto"
    assert translated["room_temperature"] == 24.6
    assert translated["humidity"] == 51
    assert translated["iaq_index"] == 46
    assert translated["rpm"] == 900
    assert translated["night_mode_timer"] == 30
    assert translated["party_mode_timer"] == 75
    assert translated["boost_delay_minutes"] == 5
    assert translated["device_type"] == 3
    assert translated["timer_countdown"] == 0
    assert translated["alarm"] is False


@pytest.mark.asyncio
async def test_translate_response_handles_unsupported_empty_values(api):
    """Unsupported parameters (FD xx) are parsed as empty strings and must not crash."""
    data = {
        "B9": "",
        "01": "",
        "02": "",
        "44": "",
        "B7": "",
        "06": "",
        "07": "",
        "0B": "",
        "25": "",
        "4A": "",
        "4B": "",
        "64": "",
        "83": "",
        "86": "",
        "3A": "",
        "3B": "",
        "3C": "",
        "3D": "",
        "3E": "",
        "3F": "",
    }

    translated = await api._translate_response(data)

    assert translated["is_on"] is False
    assert translated["speed"] == "255"
    assert translated["manual_speed"] == 0
    assert translated["boost"] is False
    assert translated["mode"] == "auto"
    assert translated["humidity"] is None
    assert translated["rpm"] == 0
    assert translated["filter_timer_minutes"] == 0
    assert translated["alarm"] is False


@pytest.mark.asyncio
async def test_translate_response_supports_s8_fallback_fields(api):
    """When base-page fields are absent, page-3 values are used as fallbacks."""
    translated = await api._translate_response(
        {
            "0310": "01",
            "0311": "03",
            "0312": "02",
        }
    )

    assert translated["is_on"] is True
    assert translated["speed"] == "03"
    assert translated["timer_mode"] == "party"
    assert translated["mode"] == "party"
    assert translated["boost"] is False


@pytest.mark.asyncio
async def test_translate_response_parses_room_temperature_and_iaq(api):
    translated = await api._translate_response(
        {
            "21": "00F6",  # 24.6C
            "0320": "002E",  # IAQ 46
        }
    )

    assert translated["room_temperature"] == 24.6
    assert translated["iaq_index"] == 46


@pytest.mark.asyncio
async def test_translate_response_parses_timer_mode_from_command_mode(api):
    translated = await api._translate_response({"07": "01"})
    assert translated["timer_mode"] == "night"


@pytest.mark.asyncio
async def test_translate_response_parses_night_and_party_mode_timer_setpoints(api):
    translated = await api._translate_response(
        {
            "0302": "001E",  # 00h 30m
            "0303": "010F",  # 01h 15m
        }
    )

    assert translated["night_mode_timer"] == 30
    assert translated["party_mode_timer"] == 75


@pytest.mark.asyncio
async def test_translate_response_parses_filter_replacement_timer_setup_days(api):
    translated = await api._translate_response(
        {
            "63": "016D",  # 365 days
        }
    )

    assert translated["filter_replacement_timer_setup_days"] == 365


@pytest.mark.asyncio
async def test_translate_response_reports_supported_optional_features(api):
    """Optional capability summary should include supported optional commands."""
    translated = await api._translate_response(
        {
            "012A": "01",
            "032A": "01",
            "032B": "00",
        }
    )

    assert translated["supported_features"] == (
        "restore_preset_speeds, passive_boost, passive_ventilation"
    )
    assert translated["max_rpm_protocol"] == 5000

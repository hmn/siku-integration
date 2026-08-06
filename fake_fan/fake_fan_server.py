#!/usr/bin/env python3
"""Fake Siku (Blauberg) Fan Controller Server for Testing.

This script simulates a Siku (Blauberg) Fan controller that responds to UDP commands
according to the protocol specification. It can be used for testing the
Home Assistant integration without requiring physical hardware.

Usage:
    python fake_fan_server.py [--host HOST] [--port PORT] [--id ID] [--password PASSWORD]

Example:
    python fake_fan_server.py --host 0.0.0.0 --port 4000 --id "1234567890123456" --password "1234"

"""

import argparse
import logging
import random
import socket
import time
from datetime import datetime

# Protocol constants
PACKET_PREFIX = "FDFD"
PACKET_PROTOCOL_TYPE = "02"

FUNC_READ = "01"
FUNC_WRITE = "02"
FUNC_READ_WRITE = "03"
FUNC_INC = "04"
FUNC_DEC = "05"
FUNC_RESULT = "06"

RETURN_CHANGE_FUNC = "FC"
RETURN_INVALID = "FD"
RETURN_VALUE_SIZE = "FE"
RETURN_HIGH_BYTE = "FF"

COMMAND_ON_OFF = "01"
COMMAND_SPEED = "02"
COMMAND_BOOST = "06"
COMMAND_MODE = "07"
COMMAND_TIMER_COUNTDOWN = "0B"
COMMAND_CURRENT_HUMIDITY = "25"
COMMAND_MANUAL_SPEED = "44"
COMMAND_FAN1RPM = "4A"
COMMAND_FAN2RPM = "4B"
COMMAND_FILTER_REPLACEMENT_TIMER_SETUP = "63"
COMMAND_FILTER_TIMER = "64"
COMMAND_BOOST_DELAY = "66"
COMMAND_RESET_FILTER_TIMER = "65"
COMMAND_SEARCH = "7C"
COMMAND_RUN_HOURS = "7E"
COMMAND_RESET_ALARMS = "80"
COMMAND_READ_ALARM = "83"
COMMAND_READ_FIRMWARE_VERSION = "86"
COMMAND_FILTER_ALARM = "88"
COMMAND_DIRECTION = "B7"
COMMAND_DEVICE_TYPE = "B9"

COMMAND_ROOM_TEMPERATURE = "21"
COMMAND_RESTORE_PRESET_SPEEDS = "012A"
COMMAND_NIGHT_MODE_TIMER = "0302"
COMMAND_PARTY_MODE_TIMER = "0303"
COMMAND_S8_POWER = "0310"
COMMAND_S8_SPEED = "0311"
COMMAND_S8_MODE = "0312"
COMMAND_IAQ_INDEX = "0320"
COMMAND_HUMIDITY_SENSOR_STATUS = "0304"
COMMAND_ZERO_TEN_V_SENSOR_STATUS = "0305"
COMMAND_ENABLE_BOOST_PASSIVE = "032A"
COMMAND_PASSIVE_VENT_MODE = "032B"

# Supply and exhaust fan speed per speed mode (1, 2, 3)
PRESET_SPEED_COMMANDS = {
    "supply_speed_1": "3A",
    "exhaust_speed_1": "3B",
    "supply_speed_2": "3C",
    "exhaust_speed_2": "3D",
    "supply_speed_3": "3E",
    "exhaust_speed_3": "3F",
}

POWER_OFF = "00"
POWER_ON = "01"
POWER_TOGGLE = "02"

MODE_OFF = "01"
MODE_SLEEP = "01"
MODE_PARTY = "02"

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)


class FakeFanController:
    """Simulates a Siku (Blauberg) Fan controller."""

    def __init__(self, device_id: str, password: str, slow_mode: bool = False):
        """Initialize the fake fan controller."""
        self.device_id = device_id
        self.password = password
        self.slow_mode = slow_mode

        # Fan state
        self.is_on = False
        self.speed = "01"  # Speed 1-3 (255 = manual)
        self.manual_speed = "80"  # Manual speed 0-255 (128 = ~50%)
        self.direction = "00"  # 00=forward, 01=reverse, 02=alternating
        self.boost = False
        self.mode = MODE_OFF  # 01=sleep, 02=party
        self.humidity = 45  # Current humidity percentage
        self.room_temperature_x10 = 239  # Room temperature in tenths (239 = 23.9°C)
        self.rpm = 1200  # Fan RPM
        self.filter_replacement_timer_setup_days = 120  # Param 0x63, 70..365 days
        self.filter_timer_minutes = (
            3 * 24 * 60 + 2 * 60 + 1
        )  # Minutes since filter change ( 3 days 2 hours 1 minute = 4441)
        self.timer_countdown_seconds = 0  # Countdown timer in seconds
        self.humidity_sensor_status = "00"  # 00=below setpoint, 01=over setpoint
        self.zero_ten_v_sensor_status = "00"  # 00=below setpoint, 01=over setpoint
        self.boost_delay_minutes = 0
        self.passive_boost_enabled = False
        self.passive_ventilation_mode = False
        self.alarm = False
        self.firmware_major = 2
        self.firmware_minor = 5
        self.device_type = "01"

        # Extended parameters
        self.night_mode_timer_minutes = 0  # Night mode timer in minutes (0x0302)
        self.party_mode_timer_minutes = 0  # Party mode timer in minutes (0x0303)
        self.iaq_index = 26  # Indoor air quality index (0x0320)

        # Preset speed settings for supply and exhaust fans
        self.preset_speeds = {
            "supply_speed_1": 60,  # 0x3A
            "exhaust_speed_1": 60,  # 0x3B
            "supply_speed_2": 120,  # 0x3C
            "exhaust_speed_2": 120,  # 0x3D
            "supply_speed_3": 200,  # 0x3E
            "exhaust_speed_3": 200,  # 0x3F
        }

        LOGGER.info("Fake fan controller initialized")
        LOGGER.info(f"  Device ID: {self.device_id}")
        LOGGER.info(f"  Password: {self.password}")
        if self.slow_mode:
            LOGGER.info("  Slow mode: ENABLED (1-7 second delays)")

    def _checksum(self, data: str) -> str:
        """Calculate checksum for packet."""
        hexlist = [data[i : i + 2] for i in range(0, len(data), 2)]
        checksum = 0
        for hexstr in hexlist[2:]:
            checksum += int(hexstr, 16)
        checksum_str = f"{checksum:04X}"
        return f"{checksum_str[2:4]}{checksum_str[0:2]}"

    def _verify_checksum(self, hexlist: list) -> bool:
        """Verify checksum of received packet."""
        data = "".join(hexlist[0:-2])
        checksum = self._checksum(data)
        received_checksum = hexlist[-2] + hexlist[-1]
        return checksum == received_checksum

    def _verify_auth(self, hexlist: list) -> bool:
        """Verify device ID and password in packet."""
        try:
            # Check prefix
            if hexlist[0] + hexlist[1] != PACKET_PREFIX:
                return False

            # Check protocol type
            if hexlist[2] != PACKET_PROTOCOL_TYPE:
                return False

            # Get ID length and ID
            id_length = int(hexlist[3], 16)
            id_hex = "".join(hexlist[4 : 4 + id_length])
            received_id = bytes.fromhex(id_hex).decode("utf-8")

            # Get password length and password
            pwd_start = 4 + id_length
            pwd_length = int(hexlist[pwd_start], 16)
            pwd_hex = "".join(hexlist[pwd_start + 1 : pwd_start + 1 + pwd_length])
            received_password = bytes.fromhex(pwd_hex).decode("utf-8")

            return received_id == self.device_id and received_password == self.password
        except (IndexError, ValueError) as e:
            LOGGER.error(f"Auth verification error: {e}")
            return False

    def _build_response_header(self) -> str:
        """Build response packet header with auth info."""
        id_hex = self.device_id.encode("utf-8").hex().upper()
        id_length = f"{len(self.device_id):02X}"
        password_hex = self.password.encode("utf-8").hex().upper()
        password_length = f"{len(self.password):02X}"

        header = (
            PACKET_PREFIX
            + PACKET_PROTOCOL_TYPE
            + id_length
            + id_hex
            + password_length
            + password_hex
            + FUNC_RESULT
        )
        return header

    def _full_command(self, command: str, page: str = "00") -> str:
        """Return command as a full 16-bit hex string."""
        if len(command) == 4:
            return command.upper()
        return f"{page}{command}".upper()

    def _split_command(self, command: str) -> tuple[str, str]:
        """Split full 16-bit command into (page, low byte)."""
        full = self._full_command(command)
        return full[:2], full[2:]

    def _encode_data_entry(
        self, current_page: str, full_cmd: str, value: str, is_multibyte: bool
    ) -> tuple[str, str]:
        """Encode one response data entry, adding page change marker when needed."""
        page, cmd = self._split_command(full_cmd)
        encoded = ""
        if page != current_page:
            encoded += RETURN_HIGH_BYTE + page
            current_page = page

        if is_multibyte:
            encoded += RETURN_VALUE_SIZE + value
        elif value.startswith(RETURN_INVALID):
            encoded += RETURN_INVALID + cmd
        else:
            encoded += cmd + value

        return encoded, current_page

    def _encode_minutes_value(self, low_cmd: str, total_minutes: int) -> str:
        """Encode total minutes as little-endian [minutes, hours] payload."""
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"02{low_cmd}{minutes:02X}{hours:02X}"

    def _decode_two_byte_le(self, value: str) -> int:
        """Decode one- or two-byte little-endian hex value."""
        if len(value) >= 4:
            return int(value[2:4] + value[0:2], 16)
        return int(value, 16)

    def _set_timer_minutes_from_value(self, attr_name: str, value: str) -> int:
        """Set minutes attribute from one- or two-byte little-endian value."""
        if len(value) >= 4:
            minutes = int(value[0:2], 16)
            hours = int(value[2:4], 16)
            setattr(self, attr_name, hours * 60 + minutes)
        else:
            setattr(self, attr_name, int(value, 16))
        return getattr(self, attr_name)

    def _get_full_command_state(
        self, full_cmd: str, low_cmd: str
    ) -> tuple[str, bool] | None:
        """Get values handled by full 16-bit command IDs."""
        full_handlers = {
            COMMAND_S8_POWER: lambda: (POWER_ON if self.is_on else POWER_OFF, False),
            COMMAND_S8_SPEED: lambda: (self.speed, False),
            COMMAND_S8_MODE: lambda: (self.mode, False),
            COMMAND_RESTORE_PRESET_SPEEDS: lambda: ("00", False),
            COMMAND_HUMIDITY_SENSOR_STATUS: lambda: ("00", False),
            COMMAND_ZERO_TEN_V_SENSOR_STATUS: lambda: ("00", False),
            COMMAND_ENABLE_BOOST_PASSIVE: lambda: (
                "01" if self.passive_boost_enabled else "00",
                False,
            ),
            COMMAND_PASSIVE_VENT_MODE: lambda: (
                "01" if self.passive_ventilation_mode else "00",
                False,
            ),
            COMMAND_NIGHT_MODE_TIMER: lambda: (
                self._encode_minutes_value(low_cmd, self.night_mode_timer_minutes),
                True,
            ),
            COMMAND_PARTY_MODE_TIMER: lambda: (
                self._encode_minutes_value(low_cmd, self.party_mode_timer_minutes),
                True,
            ),
            COMMAND_IAQ_INDEX: lambda: (
                f"02{low_cmd}{self.iaq_index & 0xFF:02X}{(self.iaq_index >> 8) & 0xFF:02X}",
                True,
            ),
        }
        handler = full_handlers.get(full_cmd)
        if handler is None:
            return None
        return handler()

    def _get_low_command_state(self, low_cmd: str) -> tuple[str, bool] | None:
        """Get values handled by low-byte command IDs."""
        single_byte_handlers = {
            COMMAND_ON_OFF: lambda: (POWER_ON if self.is_on else POWER_OFF, False),
            COMMAND_SPEED: lambda: (self.speed, False),
            COMMAND_MANUAL_SPEED: lambda: (self.manual_speed, False),
            COMMAND_DIRECTION: lambda: (self.direction, False),
            COMMAND_BOOST: lambda: ("01" if self.boost else "00", False),
            COMMAND_MODE: lambda: (self.mode, False),
            COMMAND_CURRENT_HUMIDITY: lambda: (f"{self.humidity:02X}", False),
            COMMAND_BOOST_DELAY: lambda: (f"{self.boost_delay_minutes:02X}", False),
            COMMAND_READ_ALARM: lambda: ("01" if self.alarm else "00", False),
            COMMAND_DEVICE_TYPE: lambda: (self.device_type, False),
        }
        handler = single_byte_handlers.get(low_cmd)
        if handler is not None:
            return handler()

        if low_cmd == COMMAND_ROOM_TEMPERATURE:
            return (
                f"02{low_cmd}{self.room_temperature_x10 & 0xFF:02X}{(self.room_temperature_x10 >> 8) & 0xFF:02X}",
                True,
            )

        if low_cmd in (COMMAND_FAN1RPM, COMMAND_FAN2RPM):
            if self.rpm > 255:
                return (
                    f"02{low_cmd}{(self.rpm & 0xFF):02X}{(self.rpm >> 8):02X}",
                    True,
                )
            return (f"{self.rpm:02X}", False)

        if low_cmd == COMMAND_FILTER_REPLACEMENT_TIMER_SETUP:
            days = self.filter_replacement_timer_setup_days
            return (f"02{low_cmd}{days & 0xFF:02X}{(days >> 8) & 0xFF:02X}", True)

        if low_cmd == COMMAND_FILTER_TIMER:
            days = self.filter_timer_minutes // (24 * 60)
            remaining = self.filter_timer_minutes % (24 * 60)
            hours = remaining // 60
            minutes = remaining % 60
            return (f"03{low_cmd}{minutes:02X}{hours:02X}{days:02X}", True)

        if low_cmd == COMMAND_TIMER_COUNTDOWN:
            hours = self.timer_countdown_seconds // 3600
            remaining = self.timer_countdown_seconds % 3600
            minutes = remaining // 60
            seconds = remaining % 60
            return (f"03{low_cmd}{seconds:02X}{minutes:02X}{hours:02X}", True)

        if low_cmd == COMMAND_READ_FIRMWARE_VERSION:
            now = datetime.now()
            value = (
                f"06{low_cmd}{self.firmware_major:02X}"
                f"{self.firmware_minor:02X}{now.day:02X}{now.month:02X}"
                f"{(now.year >> 8):02X}{(now.year & 0xFF):02X}"
            )
            return (value, True)

        for key, cmd_hex in PRESET_SPEED_COMMANDS.items():
            if low_cmd == cmd_hex:
                return (f"{self.preset_speeds[key]:02X}", False)

        return None

    def _set_full_command_state(self, full_cmd: str, value: str) -> bool:
        """Apply writes handled by full 16-bit command IDs."""
        if full_cmd == COMMAND_RESTORE_PRESET_SPEEDS:
            LOGGER.info("✓ Restore preset speed defaults requested")
            return True

        if full_cmd == COMMAND_ENABLE_BOOST_PASSIVE:
            self.passive_boost_enabled = value != "00"
            LOGGER.info(
                "✓ Passive ventilation boost %s",
                "enabled" if self.passive_boost_enabled else "disabled",
            )
            return True

        if full_cmd == COMMAND_PASSIVE_VENT_MODE:
            self.passive_ventilation_mode = value != "00"
            LOGGER.info(
                "✓ Passive ventilation mode %s",
                "enabled" if self.passive_ventilation_mode else "disabled",
            )
            return True

        if full_cmd == COMMAND_NIGHT_MODE_TIMER:
            minutes = self._set_timer_minutes_from_value(
                "night_mode_timer_minutes", value
            )
            LOGGER.info(f"✓ Night mode timer set to: {minutes} minutes")
            return True

        if full_cmd == COMMAND_PARTY_MODE_TIMER:
            minutes = self._set_timer_minutes_from_value(
                "party_mode_timer_minutes", value
            )
            LOGGER.info(f"✓ Party mode timer set to: {minutes} minutes")
            return True

        if full_cmd == COMMAND_IAQ_INDEX:
            self.iaq_index = self._decode_two_byte_le(value)
            LOGGER.info(f"✓ IAQ index set to: {self.iaq_index}")
            return True

        return False

    def _set_room_temperature(self, value: str):
        self.room_temperature_x10 = self._decode_two_byte_le(value)
        temp_c = self.room_temperature_x10 / 10.0
        LOGGER.info(f"✓ Room temperature set to: {temp_c}°C")

    def _set_boost_delay(self, value: str):
        self.boost_delay_minutes = int(value, 16)
        LOGGER.info("✓ Boost delay set to: %s minutes", self.boost_delay_minutes)

    def _set_filter_replacement_timer_setup(self, value: str):
        self.filter_replacement_timer_setup_days = self._decode_two_byte_le(value)
        LOGGER.info(
            "✓ Filter replacement timer setup set to: %s days",
            self.filter_replacement_timer_setup_days,
        )

    def _set_preset_speed(self, low_cmd: str, value: str):
        for key, cmd_hex in PRESET_SPEED_COMMANDS.items():
            if low_cmd == cmd_hex:
                self.preset_speeds[key] = int(value, 16)
                LOGGER.info(f"✓ {key} set to: {int(value, 16)}")
                return

    def _set_on_off(self, value: str):
        if value == POWER_ON:
            self.is_on = True
            LOGGER.info("✓ Fan turned ON")
        elif value == POWER_OFF:
            self.is_on = False
            LOGGER.info("✓ Fan turned OFF")
        elif value == POWER_TOGGLE:
            self.is_on = not self.is_on
            LOGGER.info(f"✓ Fan toggled to {'ON' if self.is_on else 'OFF'}")

    def _set_speed(self, value: str):
        self.speed = value
        LOGGER.info(f"✓ Speed set to: {int(value, 16)}")

    def _set_manual_speed(self, value: str):
        self.manual_speed = value
        percentage = (int(value, 16) / 255.0) * 100
        LOGGER.info(f"✓ Manual speed set to: {int(value, 16)} ({percentage:.1f}%)")

    def _set_direction(self, value: str):
        self.direction = value
        direction_names = {
            "00": "Forward (ventilation)",
            "01": "Alternating (heat recovery)",
            "02": "Reverse (supply)",
        }
        LOGGER.info(f"✓ Direction set to: {direction_names.get(value, value)}")

    def _set_boost(self, value: str):
        self.boost = value != "00"
        LOGGER.info(f"✓ Boost {'enabled' if self.boost else 'disabled'}")

    def _set_mode(self, value: str):
        self.mode = value
        mode_names = {"01": "Sleep", "02": "Party"}
        LOGGER.info(f"✓ Mode set to: {mode_names.get(value, value)}")

    def _set_reset_filter_timer(self, _value: str):
        self.filter_timer_minutes = 0
        LOGGER.info("✓ Filter timer reset")

    def _set_reset_alarms(self, _value: str):
        self.alarm = False
        LOGGER.info("✓ Alarms reset")

    def _get_state_value(self, command: str) -> tuple[str, bool]:
        """Get current state value for a command.

        Returns:
            tuple: (value_string, is_multibyte)

        """
        full_cmd = self._full_command(command)
        low_cmd = full_cmd[2:]

        state = self._get_full_command_state(full_cmd, low_cmd)
        if state is None:
            state = self._get_low_command_state(low_cmd)
        if state is not None:
            return state

        LOGGER.warning(f"Unknown command: {full_cmd}")
        return (RETURN_INVALID + low_cmd, False)

    def _set_state_value(self, command: str, value: str):
        """Set state value for a command."""
        full_cmd = self._full_command(command)
        low_cmd = full_cmd[2:]

        if self._set_full_command_state(full_cmd, value):
            return

        low_handlers = {
            COMMAND_ROOM_TEMPERATURE: self._set_room_temperature,
            COMMAND_BOOST_DELAY: self._set_boost_delay,
            COMMAND_FILTER_REPLACEMENT_TIMER_SETUP: self._set_filter_replacement_timer_setup,
        }
        low_handler = low_handlers.get(low_cmd)
        if low_handler is not None:
            low_handler(value)
            return

        if low_cmd in PRESET_SPEED_COMMANDS.values():
            self._set_preset_speed(low_cmd, value)
            return

        command_handlers = {
            COMMAND_ON_OFF: self._set_on_off,
            COMMAND_SPEED: self._set_speed,
            COMMAND_MANUAL_SPEED: self._set_manual_speed,
            COMMAND_DIRECTION: self._set_direction,
            COMMAND_BOOST: self._set_boost,
            COMMAND_MODE: self._set_mode,
            COMMAND_RESET_FILTER_TIMER: self._set_reset_filter_timer,
            COMMAND_RESET_ALARMS: self._set_reset_alarms,
        }
        command_handler = command_handlers.get(low_cmd)
        if command_handler is not None:
            command_handler(value)
            return

        LOGGER.warning(f"Unknown write command: {full_cmd} = {value}")

    def _parse_data_commands(self, hexlist, data_start, data_end, expect_values: bool):
        """Parse request DATA block with support for page/size special commands."""
        parsed: list[tuple[str, str | None]] = []
        i = data_start
        page = "00"

        while i < data_end:
            token = hexlist[i]

            if token == RETURN_CHANGE_FUNC:
                i += 2
                continue

            if token == RETURN_HIGH_BYTE:
                page = hexlist[i + 1]
                i += 2
                continue

            if token == RETURN_VALUE_SIZE:
                value_size = int(hexlist[i + 1], 16)
                cmd = self._full_command(hexlist[i + 2], page)
                if expect_values:
                    value = "".join(hexlist[i + 3 : i + 3 + value_size])
                    parsed.append((cmd, value))
                else:
                    parsed.append((cmd, None))
                i += 3 + value_size
                continue

            cmd = self._full_command(token, page)
            if expect_values:
                if i + 1 >= data_end:
                    break
                parsed.append((cmd, hexlist[i + 1]))
                i += 2
            else:
                parsed.append((cmd, None))
                i += 1

        return parsed

    def _handle_read(self, hexlist, data_start, data_end):
        response_data = ""
        current_page = "00"

        for full_cmd, _ in self._parse_data_commands(
            hexlist, data_start, data_end, expect_values=False
        ):
            value, is_multibyte = self._get_state_value(full_cmd)
            encoded, current_page = self._encode_data_entry(
                current_page, full_cmd, value, is_multibyte
            )
            response_data += encoded

        response = self._build_response_header() + response_data
        LOGGER.debug(f"Response before checksum: {response}")
        LOGGER.debug(f"Response data: {response_data}")
        response += self._checksum(response)
        LOGGER.debug(f"Response with checksum: {response}")
        response_bytes = bytes.fromhex(response)
        LOGGER.info(f"RESPONSE: {response}")
        LOGGER.info(f"Length: {len(response_bytes)} bytes")
        return response_bytes

    def _handle_write(self, hexlist, data_start, data_end):
        for full_cmd, raw_value in self._parse_data_commands(
            hexlist, data_start, data_end, expect_values=True
        ):
            if raw_value is None:
                continue

            # For multi-byte commands, pass the full value; for single-byte, take first 2 hex chars
            multi_byte_commands = [
                COMMAND_FILTER_REPLACEMENT_TIMER_SETUP,
                COMMAND_ROOM_TEMPERATURE,
                COMMAND_NIGHT_MODE_TIMER,
                COMMAND_PARTY_MODE_TIMER,
                COMMAND_IAQ_INDEX,
            ]

            if full_cmd in multi_byte_commands or full_cmd[2:] in multi_byte_commands:
                value = raw_value
            else:
                value = raw_value[:2]
            self._set_state_value(full_cmd, value)

        LOGGER.info("(No response for WRITE command)")
        return None

    def _handle_read_write(self, hexlist, data_start, data_end):
        response_data = ""
        current_page = "00"

        for full_cmd, raw_value in self._parse_data_commands(
            hexlist, data_start, data_end, expect_values=True
        ):
            if raw_value is None:
                continue

            # For multi-byte commands, pass the full value; for single-byte, take first 2 hex chars
            multi_byte_commands = [
                COMMAND_FILTER_REPLACEMENT_TIMER_SETUP,
                COMMAND_ROOM_TEMPERATURE,
                COMMAND_NIGHT_MODE_TIMER,
                COMMAND_PARTY_MODE_TIMER,
                COMMAND_IAQ_INDEX,
            ]

            if full_cmd in multi_byte_commands or full_cmd[2:] in multi_byte_commands:
                value = raw_value
            else:
                value = raw_value[:2]
            self._set_state_value(full_cmd, value)
            new_value, is_multibyte = self._get_state_value(full_cmd)
            encoded, current_page = self._encode_data_entry(
                current_page, full_cmd, new_value, is_multibyte
            )
            response_data += encoded

        response = self._build_response_header() + response_data
        response += self._checksum(response)
        response_bytes = bytes.fromhex(response)
        LOGGER.info(f"RESPONSE: {response}")
        LOGGER.info(f"Length: {len(response_bytes)} bytes")
        return response_bytes

    def _handle_inc(self, hexlist, data_start):
        cmd = hexlist[data_start]
        if cmd == COMMAND_SPEED:
            speed_int = int(self.speed, 16)
            if speed_int < 10:
                self.speed = f"{speed_int + 1:02X}"
                LOGGER.info(f"✓ Speed incremented to: {speed_int + 1}")
        elif cmd == COMMAND_MANUAL_SPEED:
            speed_int = int(self.manual_speed, 16)
            if speed_int < 255:
                self.manual_speed = f"{speed_int + 1:02X}"
                LOGGER.info(f"✓ Manual speed incremented to: {speed_int + 1}")
        value, is_multibyte = self._get_state_value(cmd)
        if is_multibyte:
            response_data = RETURN_VALUE_SIZE + value
        else:
            response_data = cmd + value
        response = self._build_response_header() + response_data
        response += self._checksum(response)
        response_bytes = bytes.fromhex(response)
        LOGGER.info(f"RESPONSE: {response}")
        return response_bytes

    def _handle_dec(self, hexlist, data_start):
        cmd = hexlist[data_start]
        if cmd == COMMAND_SPEED:
            speed_int = int(self.speed, 16)
            if speed_int > 1:
                self.speed = f"{speed_int - 1:02X}"
                LOGGER.info(f"✓ Speed decremented to: {speed_int - 1}")
        elif cmd == COMMAND_MANUAL_SPEED:
            speed_int = int(self.manual_speed, 16)
            if speed_int > 0:
                self.manual_speed = f"{speed_int - 1:02X}"
                LOGGER.info(f"✓ Manual speed decremented to: {speed_int - 1}")
        value, is_multibyte = self._get_state_value(cmd)
        if is_multibyte:
            response_data = RETURN_VALUE_SIZE + value
        else:
            response_data = cmd + value
        response = self._build_response_header() + response_data
        response += self._checksum(response)
        response_bytes = bytes.fromhex(response)
        LOGGER.info(f"RESPONSE: {response}")
        return response_bytes

    def process_packet(self, data: bytes) -> bytes | None:
        """Process received packet and return response."""
        # Apply random delay if slow mode is enabled
        if self.slow_mode:
            delay = random.uniform(1.0, 7.0)
            LOGGER.info(f"Slow mode: delaying response by {delay:.2f} seconds...")
            time.sleep(delay)

        hex_str = data.hex().upper()
        hexlist = [hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]

        LOGGER.info(f"\n{'=' * 60}")
        LOGGER.info(f"RECEIVED: {hex_str}")
        LOGGER.info(f"Length: {len(data)} bytes")

        # Verify checksum
        if not self._verify_checksum(hexlist):
            LOGGER.error("✗ Checksum verification failed!")
            return None
        LOGGER.info("✓ Checksum verified")

        # Verify authentication
        if not self._verify_auth(hexlist):
            LOGGER.error("✗ Authentication failed!")
            return None
        LOGGER.info("✓ Authentication successful")

        try:
            id_length = int(hexlist[3], 16)
            pwd_start = 4 + id_length
            pwd_length = int(hexlist[pwd_start], 16)
            func_pos = pwd_start + 1 + pwd_length

            func = hexlist[func_pos]
            data_start = func_pos + 1
            data_end = len(hexlist) - 2  # Exclude checksum

            LOGGER.info(f"Function: {func}")

            if func == FUNC_READ:
                LOGGER.info("Command: READ")
                return self._handle_read(hexlist, data_start, data_end)
            elif func == FUNC_WRITE:
                LOGGER.info("Command: WRITE")
                return self._handle_write(hexlist, data_start, data_end)
            elif func == FUNC_READ_WRITE:
                LOGGER.info("Command: READ_WRITE")
                return self._handle_read_write(hexlist, data_start, data_end)
            elif func == FUNC_INC:
                LOGGER.info("Command: INCREMENT")
                return self._handle_inc(hexlist, data_start)
            elif func == FUNC_DEC:
                LOGGER.info("Command: DECREMENT")
                return self._handle_dec(hexlist, data_start)
            else:
                LOGGER.error(f"Unknown function: {func}")
                return None

        except Exception as e:
            LOGGER.error(f"Error processing packet: {e}", exc_info=True)
            return None


def main():
    """Run the fake fan server."""
    parser = argparse.ArgumentParser(
        description="Fake Siku (Blauberg) Fan Controller Server for Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --host 0.0.0.0 --port 4000
  %(prog)s --id "mydevice123456789012" --password "secret"
        """,
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=4000, help="Port to listen on (default: 4000)"
    )
    parser.add_argument(
        "--id",
        dest="device_id",
        default="1234567890123456",
        help="Device ID (default: 1234567890123456)",
    )
    parser.add_argument(
        "--password", default="1234", help="Device password (default: 1234)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--slow",
        action="store_true",
        help="Enable slow mode (random 1-7 second delays in responses)",
    )

    args = parser.parse_args()

    if args.debug:
        LOGGER.setLevel(logging.DEBUG)

    # Create fake fan controller
    fan = FakeFanController(args.device_id, args.password, args.slow)

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((args.host, args.port))
        LOGGER.info("\n%s", "=" * 60)
        LOGGER.info("Fake Siku (Blauberg) Fan Server Started")
        LOGGER.info("Listening on %s:%s", args.host, args.port)
        LOGGER.info("%s\n", "=" * 60)
        LOGGER.info("Waiting for commands...\n")

        while True:
            data, addr = sock.recvfrom(4096)
            LOGGER.info("Connection from: %s:%s", addr[0], addr[1])

            response = fan.process_packet(data)

            if response:
                sock.sendto(response, addr)

            LOGGER.info("%s\n", "=" * 60)

    except KeyboardInterrupt:
        LOGGER.info("\n\nShutting down server...")
    except Exception as e:
        LOGGER.error(f"Server error: {e}", exc_info=True)
    finally:
        sock.close()
        LOGGER.info("Server stopped.")


if __name__ == "__main__":
    main()

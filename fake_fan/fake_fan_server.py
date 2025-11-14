#!/usr/bin/env python3
"""Fake Siku Fan Controller Server for Testing.

This script simulates a Siku fan controller that responds to UDP commands
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
COMMAND_FILTER_TIMER = "64"
COMMAND_RESET_FILTER_TIMER = "65"
COMMAND_SEARCH = "7C"
COMMAND_RUN_HOURS = "7E"
COMMAND_RESET_ALARMS = "80"
COMMAND_READ_ALARM = "83"
COMMAND_READ_FIRMWARE_VERSION = "86"
COMMAND_FILTER_ALARM = "88"
COMMAND_DIRECTION = "B7"
COMMAND_DEVICE_TYPE = "B9"

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
    """Simulates a Siku fan controller."""

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
        self.rpm = 1200  # Fan RPM
        self.filter_timer_minutes = 0  # Minutes since filter change
        self.timer_countdown_seconds = 0  # Countdown timer in seconds
        self.alarm = False
        self.firmware_major = 2
        self.firmware_minor = 5
        self.device_type = "01"

        LOGGER.info("Fake fan controller initialized")
        LOGGER.info(f"  Device ID: {self.device_id}")
        LOGGER.info(f"  Password: {self.password}")
        if self.slow_mode:
            LOGGER.info("  Slow mode: ENABLED (2-5 second delays)")

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

    def _get_state_value(self, command: str) -> tuple[str, bool]:
        """Get current state value for a command.

        Returns:
            tuple: (value_string, is_multibyte)

        """
        if command == COMMAND_ON_OFF:
            return (POWER_ON if self.is_on else POWER_OFF, False)
        elif command == COMMAND_SPEED:
            return (self.speed, False)
        elif command == COMMAND_MANUAL_SPEED:
            return (self.manual_speed, False)
        elif command == COMMAND_DIRECTION:
            return (self.direction, False)
        elif command == COMMAND_BOOST:
            return ("01" if self.boost else "00", False)
        elif command == COMMAND_MODE:
            return (self.mode, False)
        elif command == COMMAND_CURRENT_HUMIDITY:
            return (f"{self.humidity:02X}", False)
        elif command == COMMAND_FAN1RPM:
            # RPM can be larger than 255, so use multi-byte for values > 255
            if self.rpm > 255:
                # Multi-byte value: size + command + data (2 bytes for RPM, big-endian)
                return (
                    f"02{command}{(self.rpm >> 8):02X}{(self.rpm & 0xFF):02X}",
                    True,
                )
            else:
                return (f"{self.rpm:02X}", False)
        elif command == COMMAND_FILTER_TIMER:
            # Return as 3 bytes: days, hours, minutes
            days = self.filter_timer_minutes // (24 * 60)
            remaining = self.filter_timer_minutes % (24 * 60)
            hours = remaining // 60
            minutes = remaining % 60
            # Multi-byte value: FE + size + command + data
            return (f"03{command}{days:02X}{hours:02X}{minutes:02X}", True)
        elif command == COMMAND_TIMER_COUNTDOWN:
            # Return as 3 bytes: hours, minutes, seconds
            hours = self.timer_countdown_seconds // 3600
            remaining = self.timer_countdown_seconds % 3600
            minutes = remaining // 60
            seconds = remaining % 60
            # Multi-byte value: FE + size + command + data
            return (f"03{command}{hours:02X}{minutes:02X}{seconds:02X}", True)
        elif command == COMMAND_READ_ALARM:
            return ("01" if self.alarm else "00", False)
        elif command == COMMAND_READ_FIRMWARE_VERSION:
            # Return firmware version as multi-byte value
            now = datetime.now()
            value = (
                f"06{command}{self.firmware_major:02X}"
                f"{self.firmware_minor:02X}{now.day:02X}{now.month:02X}"
                f"{(now.year >> 8):02X}{(now.year & 0xFF):02X}"
            )
            return (value, True)
        elif command == COMMAND_DEVICE_TYPE:
            return (self.device_type, False)
        else:
            LOGGER.warning(f"Unknown command: {command}")
            return (RETURN_INVALID + command, False)

    def _set_state_value(self, command: str, value: str):
        """Set state value for a command."""
        if command == COMMAND_ON_OFF:
            if value == POWER_ON:
                self.is_on = True
                LOGGER.info("✓ Fan turned ON")
            elif value == POWER_OFF:
                self.is_on = False
                LOGGER.info("✓ Fan turned OFF")
            elif value == POWER_TOGGLE:
                self.is_on = not self.is_on
                LOGGER.info(f"✓ Fan toggled to {'ON' if self.is_on else 'OFF'}")
        elif command == COMMAND_SPEED:
            self.speed = value
            LOGGER.info(f"✓ Speed set to: {int(value, 16)}")
        elif command == COMMAND_MANUAL_SPEED:
            self.manual_speed = value
            percentage = (int(value, 16) / 255.0) * 100
            LOGGER.info(f"✓ Manual speed set to: {int(value, 16)} ({percentage:.1f}%)")
        elif command == COMMAND_DIRECTION:
            self.direction = value
            direction_names = {"00": "Forward", "01": "Reverse", "02": "Alternating"}
            LOGGER.info(f"✓ Direction set to: {direction_names.get(value, value)}")
        elif command == COMMAND_BOOST:
            self.boost = value != "00"
            LOGGER.info(f"✓ Boost {'enabled' if self.boost else 'disabled'}")
        elif command == COMMAND_MODE:
            self.mode = value
            mode_names = {"01": "Sleep", "02": "Party"}
            LOGGER.info(f"✓ Mode set to: {mode_names.get(value, value)}")
        elif command == COMMAND_RESET_FILTER_TIMER:
            self.filter_timer_minutes = 0
            LOGGER.info("✓ Filter timer reset")
        elif command == COMMAND_RESET_ALARMS:
            self.alarm = False
            LOGGER.info("✓ Alarms reset")
        else:
            LOGGER.warning(f"Unknown write command: {command} = {value}")

    def _handle_read(self, hexlist, data_start, data_end):
        response_data = ""
        i = data_start
        while i < data_end:
            cmd = hexlist[i]
            value, is_multibyte = self._get_state_value(cmd)
            if is_multibyte:
                response_data += RETURN_VALUE_SIZE + value
            else:
                response_data += cmd + value
            i += 1
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
        i = data_start
        while i < data_end:
            cmd = hexlist[i]
            if i + 1 < data_end:
                value = hexlist[i + 1]
                self._set_state_value(cmd, value)
                i += 2
            else:
                i += 1
        LOGGER.info("(No response for WRITE command)")
        return None

    def _handle_read_write(self, hexlist, data_start, data_end):
        response_data = ""
        i = data_start
        while i < data_end:
            cmd = hexlist[i]
            if i + 1 < data_end:
                value = hexlist[i + 1]
                self._set_state_value(cmd, value)
                new_value, is_multibyte = self._get_state_value(cmd)
                if is_multibyte:
                    response_data += RETURN_VALUE_SIZE + new_value
                else:
                    response_data += cmd + new_value
                i += 2
            else:
                i += 1
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
            delay = random.uniform(1.0, 5.0)
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
        description="Fake Siku Fan Controller Server for Testing",
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
        help="Enable slow mode (random 1-10 second delays in responses)",
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
        LOGGER.info("Fake Siku Fan Server Started")
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

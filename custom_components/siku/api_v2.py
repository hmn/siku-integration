"""Helper api function for sending commands to the fan controller."""

import time
import logging
import asyncio
import random
from homeassistant.util.percentage import percentage_to_ranged_value
from .udp import AsyncUdpClient

from .const import DIRECTION_ALTERNATING
from .const import DIRECTIONS
from .const import FAN_SPEEDS
from .const import PRESET_MODE_AUTO
from .const import PRESET_MODE_PARTY
from .const import PRESET_MODE_SLEEP

LOGGER = logging.getLogger(__name__)

RETRY_DELAYS = (0.2, 0.5, 1.0)
REQUEST_TIMEOUT = 8.0

# forward = pull air out of the room
# reverse = pull air into the room from outside
# alternating = change directions (used for oscilating option in fan)

PACKET_PREFIX = "FDFD"
PACKET_PROTOCOL_TYPE = "02"
PACKET_SIZE_ID = "10"

FUNC_READ = "01"
FUNC_WRITE = "02"
FUNC_READ_WRITE = "03"
FUNC_INC = "04"
FUNC_DEC = "05"
FUNC_RESULT = "06"  # result func (FUNC = 0x01, 0x03, 0x04, 0x05).

RETURN_CHANGE_FUNC = "FC"
RETURN_INVALID = "FD"
RETURN_VALUE_SIZE = "FE"
RETURN_HIGH_BYTE = "FF"

COMMAND_ON_OFF = "01"
COMMAND_SPEED = "02"
COMMAND_DIRECTION = "B7"
COMMAND_DEVICE_TYPE = "B9"
COMMAND_BOOST = "06"
COMMAND_MODE = "07"
COMMAND_TIMER_COUNTDOWN = "0B"
COMMAND_ROOM_TEMPERATURE = "21"
COMMAND_CURRENT_HUMIDITY = "25"
COMMAND_MANUAL_SPEED = "44"
COMMAND_FAN1RPM = "4A"
COMMAND_FAN2RPM = "4B"
COMMAND_BOOST_DELAY = "66"
COMMAND_FILTER_REPLACEMENT_TIMER_SETUP = "63"
# Byte 1: Minutes (0...59)
# Byte 2: Hours (0...23)
# Byte 3: Days (0...181)
COMMAND_FILTER_TIMER = "64"
COMMAND_RESET_FILTER_TIMER = "65"
COMMAND_SEARCH = "7C"
COMMAND_RUN_HOURS = "7E"
COMMAND_RESET_ALARMS = "80"
COMMAND_READ_ALARM = "83"
# Byte 1: Firmware-Version (major)
# Byte 2: Firmware-Version (minor)
# Byte 3: Day
# Byte 4: Month
# Byte 5 and 6: Year
COMMAND_READ_FIRMWARE_VERSION = "86"
COMMAND_FILTER_ALARM = "88"
COMMAND_FAN_TYPE = "B9"

COMMAND_RESTORE_PRESET_SPEEDS = "012A"
COMMAND_NIGHT_MODE_TIMER = "0302"
COMMAND_PARTY_MODE_TIMER = "0303"
COMMAND_S8_POWER = "0310"
COMMAND_S8_SPEED = "0311"
COMMAND_S8_MODE = "0312"
COMMAND_IAQ_INDEX = "0320"
COMMAND_ENABLE_BOOST_PASSIVE = "032A"
COMMAND_PASSIVE_VENT_MODE = "032B"

# Supply and exhaust fan speed per speed mode, the intake/exhaust balance.
# Manual speed mode drives both fans from one speed and ignores these.
PRESET_SPEED_COMMANDS = {
    "supply_speed_1": "3A",
    "exhaust_speed_1": "3B",
    "supply_speed_2": "3C",
    "exhaust_speed_2": "3D",
    "supply_speed_3": "3E",
    "exhaust_speed_3": "3F",
}

COMMAND_FUNCTION_R = "01"
COMMAND_FUNCTION_W = "02"
COMMAND_FUNCTION_RW = "03"
COMMAND_FUNCTION_INC = "04"
COMMAND_FUNCTION_DEC = "05"

POWER_OFF = "00"
POWER_ON = "01"
POWER_TOGGLE = "02"

MODE_OFF = "00"
MODE_SLEEP = "01"
MODE_PARTY = "02"
MODES = {
    MODE_OFF: PRESET_MODE_AUTO,
    MODE_SLEEP: PRESET_MODE_SLEEP,
    MODE_PARTY: PRESET_MODE_PARTY,
}
TIMER_MODES = {
    "00": "off",
    "01": "night",
    "02": "party",
}

EMPTY_VALUE = "00"

SPEED_MANUAL_MIN: int = 0
SPEED_MANUAL_MAX: int = 255

SPEED_PRESET_MIN: int = 10
SPEED_PRESET_MAX: int = 255
PROTOCOL_MAX_RPM: int = 5000


class SikuV2Api:
    """Handle requests to the fan controller."""

    def __init__(self, host: str, port: int, idnum: str, password: str) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self.idnum = idnum
        self.password = password
        self._udp = AsyncUdpClient(self.host, self.port)
        self._lock = asyncio.Lock()
        self._req_counter = 0

    def _new_request_id(self) -> str:
        """Return a request id for log correlation.

        Note: This method is not protected by self._lock since it's called
        before entering the lock context. The counter increment is not
        atomic, but collisions are unlikely and request IDs are for
        debugging only, not for correctness.
        """
        self._req_counter = (self._req_counter + 1) % 1_000_000
        return f"v2-{int(time.time() * 1000)}-{self._req_counter:06d}-{random.randint(0, 9999):04d}"

    async def status(self) -> dict:
        """Get status from fan controller."""
        commands = [
            COMMAND_DEVICE_TYPE,
            COMMAND_ON_OFF,
            COMMAND_SPEED,
            COMMAND_MANUAL_SPEED,
            COMMAND_DIRECTION,
            COMMAND_BOOST,
            COMMAND_MODE,
            COMMAND_TIMER_COUNTDOWN,
            COMMAND_ROOM_TEMPERATURE,
            COMMAND_CURRENT_HUMIDITY,
            COMMAND_FAN1RPM,
            COMMAND_FAN2RPM,
            COMMAND_BOOST_DELAY,
            COMMAND_FILTER_REPLACEMENT_TIMER_SETUP,
            COMMAND_FILTER_TIMER,
            COMMAND_READ_ALARM,
            COMMAND_READ_FIRMWARE_VERSION,
            *PRESET_SPEED_COMMANDS.values(),
            # Probe optional page 0x01 / 0x03 parameters used by newer devices.
            RETURN_HIGH_BYTE,
            "01",
            "2A",
            RETURN_HIGH_BYTE,
            "03",
            "02",
            "03",
            "10",
            "11",
            "12",
            "20",
            "2A",
            "2B",
        ]
        cmd = "".join(commands).upper()
        hexlist = await self._send_command(FUNC_READ, cmd)
        data = await self._parse_response(hexlist)
        return await self._translate_response(data)

    async def power_on(self) -> dict:
        """Power on fan."""
        cmd = f"{COMMAND_ON_OFF}{POWER_ON}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def power_off(self) -> dict:
        """Power off fan."""
        cmd = f"{COMMAND_ON_OFF}{POWER_OFF}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def speed(self, speed: str) -> dict:
        """Set fan speed."""
        if speed not in FAN_SPEEDS:
            raise ValueError(f"Invalid fan speed: {speed}")
        cmd = f"{COMMAND_SPEED}{speed}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def speed_manual(self, percentage: int) -> dict:
        """Set manual fan speed."""
        low_high_range = (float(SPEED_MANUAL_MIN), float(SPEED_MANUAL_MAX))
        speed: int = int(
            round(
                percentage_to_ranged_value(
                    low_high_range=low_high_range, percentage=float(percentage)
                )
            )
        )
        cmd = f"{COMMAND_SPEED}FF{COMMAND_MANUAL_SPEED}{speed:02X}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def preset_speed(self, key: str, speed: int) -> dict:
        """Set supply or exhaust fan speed for one of the 3 speed modes."""
        if not SPEED_PRESET_MIN <= speed <= SPEED_PRESET_MAX:
            raise ValueError(f"Invalid preset fan speed: {speed}")
        cmd = f"{PRESET_SPEED_COMMANDS[key]}{speed:02X}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def direction(self, direction: str) -> dict:
        """Set fan direction."""
        # if direction is in DIRECTIONS values translate it to the key value
        if direction in DIRECTIONS.values():
            direction = list(DIRECTIONS.keys())[
                list(DIRECTIONS.values()).index(direction)
            ]
        if direction not in DIRECTIONS:
            raise ValueError(f"Invalid fan direction: {direction}")
        cmd = f"{COMMAND_DIRECTION}{direction}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def sleep(self) -> dict:
        """Set fan to sleep mode."""
        cmd = f"{COMMAND_ON_OFF}{POWER_ON}{COMMAND_MODE}{MODE_SLEEP}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def party(self) -> dict:
        """Set fan to party mode."""
        cmd = f"{COMMAND_ON_OFF}{POWER_ON}{COMMAND_MODE}{MODE_PARTY}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    async def reset_filter_alarm(self) -> dict:
        """Reset filter alarm."""
        cmd = f"{COMMAND_RESET_ALARMS}{EMPTY_VALUE}{COMMAND_RESET_FILTER_TIMER}{EMPTY_VALUE}".upper()
        await self._send_command(FUNC_WRITE, cmd)
        return await self.status()

    async def filter_replacement_timer_setup(self, days: int) -> dict:
        """Set filter replacement timer setup (0x0063) in days."""
        if not 70 <= days <= 365:
            raise ValueError(f"Invalid filter replacement timer setup days: {days}")
        # 0x0063 is a 2-byte value. Use FE to provide explicit value size.
        cmd = f"{RETURN_VALUE_SIZE}02{COMMAND_FILTER_REPLACEMENT_TIMER_SETUP}{days & 0xFF:02X}{(days >> 8) & 0xFF:02X}".upper()
        await self._send_command(FUNC_READ_WRITE, cmd)
        return await self.status()

    def _checksum(self, data: str) -> str:
        """Calculate checksum for packet and return it as high order byte hex string."""
        hexlist = self._hexlist(data)

        checksum = 0
        for hexstr in hexlist[2:]:
            checksum += int(hexstr, 16)
        checksum_str = f"{checksum:04X}"
        return f"{checksum_str[2:4]:02}{checksum_str[0:2]:02}"

    def _verify_checksum(self, hexlist: list[str]) -> bool:
        """Verify checksum of packet."""
        checksum = self._checksum("".join(hexlist[0:-2]))
        LOGGER.debug("checksum: %s", checksum)
        LOGGER.debug("verify if %s == %s", checksum, hexlist[-2] + hexlist[-1])
        return checksum == hexlist[-2] + hexlist[-1]

    def _hexlist(self, hexstr: str) -> list[str]:
        """Convert hex string to list of hex strings."""
        return [hexstr[i : i + 2] for i in range(0, len(hexstr), 2)]

    def _login_packet(self) -> str:
        """Build initial login part of packet."""
        id_hex = self.idnum.encode("utf-8").hex()
        password_size = f"{len(self.password):02x}"
        password_hex = self.password.encode("utf-8").hex()
        packet_str = (
            PACKET_PREFIX
            + PACKET_PROTOCOL_TYPE
            + PACKET_SIZE_ID
            + id_hex
            + password_size
            + str(password_hex)
        ).upper()
        return packet_str

    def _build_packet(self, func: str, data: str) -> str:
        """Build packet for sending to fan controller."""
        packet_str = (self._login_packet() + func + data).upper()
        LOGGER.debug("packet string: %s", packet_str)
        packet_str += self._checksum(packet_str)
        LOGGER.debug("packet string: %s", packet_str)
        return packet_str

    async def _send_command(self, func: str, data: str) -> list[str]:
        """Send command to fan controller using asyncio UDP transport."""
        packet_str = self._build_packet(func, data)
        packet_data = bytes.fromhex(packet_str)

        # Map function codes to readable names for logging
        func_names = {
            FUNC_READ: "READ",
            FUNC_WRITE: "WRITE",
            FUNC_READ_WRITE: "READ_WRITE",
            FUNC_INC: "INCREMENT",
            FUNC_DEC: "DECREMENT",
        }
        func_name = func_names.get(func, f"UNKNOWN({func})")

        request_id = self._new_request_id()
        total_attempts = len(RETRY_DELAYS)
        overall_start_time = time.time()

        for attempt_index, delay in enumerate(RETRY_DELAYS):
            attempt_start_time = time.time()
            try:
                if func == FUNC_WRITE:
                    LOGGER.debug(
                        "[%s:%d req=%s] write command, no response expected",
                        self.host,
                        self.port,
                        request_id,
                    )
                    async with self._lock:
                        await self._udp.send_only(packet_data, request_id=request_id)
                    elapsed = time.time() - attempt_start_time
                    LOGGER.debug(
                        "[%s:%d req=%s] WRITE command completed in %.3f seconds",
                        self.host,
                        self.port,
                        request_id,
                        elapsed,
                    )
                    return []

                LOGGER.debug(
                    "[%s:%d req=%s] Sending %s request (attempt %d/%d)",
                    self.host,
                    self.port,
                    request_id,
                    func_name,
                    attempt_index + 1,
                    total_attempts,
                )
                async with self._lock:
                    result_data = await self._udp.request(
                        packet_data, timeout=REQUEST_TIMEOUT, request_id=request_id
                    )
                elapsed = time.time() - attempt_start_time
                LOGGER.debug(
                    "[%s:%d req=%s] %s request completed in %.3f seconds",
                    self.host,
                    self.port,
                    request_id,
                    func_name,
                    elapsed,
                )
                result_str = result_data.hex().upper()
                LOGGER.debug(
                    "[%s:%d req=%s] receive string: %s",
                    self.host,
                    self.port,
                    request_id,
                    result_str,
                )

                result_hexlist = ["".join(x) for x in zip(*[iter(result_str)] * 2)]
                if not self._verify_checksum(result_hexlist):
                    raise ValueError("Checksum error")
                LOGGER.debug(
                    "[%s:%d req=%s] returning hexlist %s",
                    self.host,
                    self.port,
                    request_id,
                    result_hexlist,
                )
                return result_hexlist
            except (asyncio.TimeoutError, TimeoutError) as ex:
                elapsed = time.time() - attempt_start_time
                total_elapsed = time.time() - overall_start_time
                LOGGER.warning(
                    "[%s:%d req=%s] %s request timed out after %.3f seconds (attempt %d/%d). "
                    "Packet: %s, Error: %s",
                    self.host,
                    self.port,
                    request_id,
                    func_name,
                    elapsed,
                    attempt_index + 1,
                    total_attempts,
                    packet_str,
                    type(ex).__name__,
                )
                if attempt_index == total_attempts - 1:
                    raise TimeoutError(
                        f"Failed to send {func_name} command to {self.host}:{self.port} "
                        f"after {total_attempts} attempts (total time: {total_elapsed:.3f}s, req={request_id})"
                    ) from ex
                sleep_for = delay + random.uniform(0, 0.15)
                await asyncio.sleep(sleep_for)
            except OSError as ex:
                # Treat network/socket errors as transient and retry, since the
                # underlying UDP client may have closed its socket on exception.
                elapsed = time.time() - attempt_start_time
                total_elapsed = time.time() - overall_start_time
                LOGGER.warning(
                    "[%s:%d req=%s] %s request failed with network error after %.3f seconds "
                    "(attempt %d/%d). Packet: %s, Error: %s",
                    self.host,
                    self.port,
                    request_id,
                    func_name,
                    elapsed,
                    attempt_index + 1,
                    total_attempts,
                    packet_str,
                    f"{type(ex).__name__}: {ex}",
                )
                if attempt_index == total_attempts - 1:
                    # On the final attempt, propagate the original network error.
                    raise
                # Close and re-create the UDP client in case the previous error closed the socket.
                async with self._lock:
                    await self._udp.close()
                    self._udp = AsyncUdpClient(self.host, self.port)
                sleep_for = delay + random.uniform(0, 0.15)
                await asyncio.sleep(sleep_for)

    def _parse_hex_int(
        self, data: dict, key: str, default: int | None = None
    ) -> int | None:
        """Parse one hex-encoded integer value from response data."""
        try:
            return int(data[key], 16)
        except (KeyError, ValueError, TypeError):
            return default

    def _parse_formatted_hex(
        self, data: dict, key: str, default: str, fallback_key: str | None = None
    ) -> str:
        """Parse a one-byte hex value and format as 2-char uppercase hex."""
        value = self._parse_hex_int(data, key)
        if value is not None:
            return f"{value:02}"
        if fallback_key is not None:
            fallback_value = self._parse_hex_int(data, fallback_key)
            if fallback_value is not None:
                return f"{fallback_value:02}"
        return default

    def _parse_bool_onoff(
        self, data: dict, key: str, fallback_key: str | None = None
    ) -> bool:
        """Parse a bool where only POWER_ON means true, optionally with fallback key."""
        raw = data.get(key)
        if raw is not None:
            return bool(raw == POWER_ON)
        if fallback_key is not None:
            return bool(data.get(fallback_key) == POWER_ON)
        return False

    def _parse_mapped_with_fallback(
        self,
        data: dict,
        key: str,
        mapping: dict[str, str],
        default: str | None,
        fallback_key: str | None = None,
    ) -> str | None:
        """Parse mapped value, using fallback only when primary is absent/empty."""
        raw = data.get(key)
        if raw in mapping:
            return mapping[raw]
        if raw in (None, "") and fallback_key is not None:
            fallback_raw = data.get(fallback_key)
            if fallback_raw in mapping:
                return mapping[fallback_raw]
        return default

    def _parse_bool_nonzero(self, data: dict, key: str, default: bool = False) -> bool:
        """Parse bool where any non-empty and non-zero value means true."""
        raw = data.get(key)
        if raw is None:
            return default
        return bool(raw and raw != "00")

    def _parse_direction_and_oscillating(self, data: dict) -> tuple[str | None, bool]:
        """Parse direction and derived oscillating state."""
        raw = data.get(COMMAND_DIRECTION)
        if raw in DIRECTIONS:
            direction = DIRECTIONS[raw]
            return direction, bool(direction == DIRECTION_ALTERNATING)
        return None, True

    def _parse_rpm(self, data: dict) -> int:
        """Parse RPM with fallback from 0x4A to 0x4B."""
        rpm = self._parse_hex_int(data, COMMAND_FAN1RPM)
        if rpm is None:
            rpm = self._parse_hex_int(data, COMMAND_FAN2RPM, 0)
        return int(rpm)

    def _parse_filter_timer_minutes(self, data: dict) -> int:
        """Parse filter timer (0x64) as total minutes."""
        raw = data.get(COMMAND_FILTER_TIMER)
        if not raw:
            return 0
        try:
            minutes = int(raw[-2:], 16)
            hours = int(raw[-4:-2], 16)
            days = int(raw[-6:-4], 16)
            return int(days * 24 * 60 + hours * 60 + minutes)
        except (ValueError, TypeError):
            return 0

    def _parse_timer_countdown_seconds(self, data: dict) -> int:
        """Parse timer countdown (0x0B) as total seconds."""
        raw = data.get(COMMAND_TIMER_COUNTDOWN)
        if not raw:
            return 0
        try:
            hours = int(raw[0:2], 16)
            minutes = int(raw[2:4], 16)
            seconds = int(raw[4:6], 16)
            return int(seconds + minutes * 60 + hours * 60 * 60)
        except (ValueError, TypeError):
            return 0

    def _parse_hhmm_minutes(self, data: dict, key: str) -> int | None:
        """Parse reversed FE multi-byte HHMM value as total minutes."""
        raw = data.get(key)
        if not raw:
            return None
        try:
            hours = int(raw[0:2], 16)
            minutes = int(raw[2:4], 16)
            return int(hours * 60 + minutes)
        except (ValueError, TypeError):
            return None

    def _parse_firmware_version(self, data: dict) -> str | None:
        """Parse firmware version string from 0x86 payload."""
        try:
            value = data[COMMAND_READ_FIRMWARE_VERSION]
            return f"{int(value[0], 16)}.{int(value[1], 16)}"
        except (KeyError, ValueError, TypeError, IndexError):
            return None

    def _parse_supported_capabilities(self, data: dict) -> list[str]:
        """Parse optional capability flags from known optional parameters."""
        capability_pairs = (
            (COMMAND_RESTORE_PRESET_SPEEDS, "restore_preset_speeds"),
            (COMMAND_ENABLE_BOOST_PASSIVE, "passive_boost"),
            (COMMAND_PASSIVE_VENT_MODE, "passive_ventilation"),
        )
        return [name for cmd, name in capability_pairs if data.get(cmd, "") != ""]

    async def _translate_response(self, data: dict) -> dict:
        """Translate response data to dict."""
        LOGGER.debug("translate response: %s", data)
        is_on = self._parse_bool_onoff(
            data, COMMAND_ON_OFF, fallback_key=COMMAND_S8_POWER
        )
        speed = self._parse_formatted_hex(
            data,
            COMMAND_SPEED,
            default="255",
            fallback_key=COMMAND_S8_SPEED,
        )
        manual_speed = self._parse_formatted_hex(
            data, COMMAND_MANUAL_SPEED, default="00"
        )
        direction, oscillating = self._parse_direction_and_oscillating(data)
        boost = self._parse_bool_nonzero(data, COMMAND_BOOST, default=False)
        timer_mode = self._parse_mapped_with_fallback(
            data,
            COMMAND_MODE,
            mapping=TIMER_MODES,
            default=None,
            fallback_key=COMMAND_S8_MODE,
        )
        mode = self._parse_mapped_with_fallback(
            data,
            COMMAND_MODE,
            mapping=MODES,
            default=PRESET_MODE_AUTO,
            fallback_key=COMMAND_S8_MODE,
        )

        humidity = self._parse_hex_int(data, COMMAND_CURRENT_HUMIDITY)
        room_temperature_raw = self._parse_hex_int(data, COMMAND_ROOM_TEMPERATURE)
        room_temperature = (
            room_temperature_raw / 10.0 if room_temperature_raw is not None else None
        )
        iaq_index = self._parse_hex_int(data, COMMAND_IAQ_INDEX)
        rpm = self._parse_rpm(data)
        filter_timer = self._parse_filter_timer_minutes(data)
        alarm = self._parse_bool_nonzero(data, COMMAND_READ_ALARM, default=False)
        firmware = self._parse_firmware_version(data)
        timer_countdown = self._parse_timer_countdown_seconds(data)
        night_mode_timer = self._parse_hhmm_minutes(data, COMMAND_NIGHT_MODE_TIMER)
        party_mode_timer = self._parse_hhmm_minutes(data, COMMAND_PARTY_MODE_TIMER)
        filter_replacement_timer_setup_days = self._parse_hex_int(
            data, COMMAND_FILTER_REPLACEMENT_TIMER_SETUP
        )
        boost_delay_minutes = self._parse_hex_int(data, COMMAND_BOOST_DELAY)
        device_type = self._parse_hex_int(data, COMMAND_DEVICE_TYPE)
        supported_capabilities = self._parse_supported_capabilities(data)

        preset_speeds = {
            key: int(data[cmd], 16)
            for key, cmd in PRESET_SPEED_COMMANDS.items()
            if data.get(cmd)
        }
        result = {
            "is_on": is_on,
            "preset_speeds": preset_speeds,
            "speed": speed,
            "speed_list": FAN_SPEEDS,
            "manual_speed_selected": bool(speed == "255"),
            "manual_speed": int(manual_speed),
            "manual_speed_low_high_range": (
                float(SPEED_MANUAL_MIN),
                float(SPEED_MANUAL_MAX),
            ),
            "oscillating": oscillating,
            "direction": direction,
            "boost": boost,
            "timer_mode": timer_mode,
            "mode": mode,
            "room_temperature": room_temperature,
            "humidity": humidity,
            "iaq_index": iaq_index,
            "rpm": rpm,
            "firmware": firmware,
            "filter_timer_minutes": filter_timer,
            "timer_countdown": timer_countdown,
            "alarm": alarm,
            "max_rpm_protocol": PROTOCOL_MAX_RPM,
            "version": "2",
        }

        optional_values = {
            "night_mode_timer": night_mode_timer,
            "party_mode_timer": party_mode_timer,
            "filter_replacement_timer_setup_days": filter_replacement_timer_setup_days,
            "boost_delay_minutes": boost_delay_minutes,
            "device_type": device_type,
        }
        for key, value in optional_values.items():
            if value is not None:
                result[key] = value

        if supported_capabilities:
            result["supported_features"] = ", ".join(supported_capabilities)

        return result

    async def _parse_response(self, hexlist: list[str]) -> dict:
        """Translate response from fan controller."""
        LOGGER.debug("parse response: %s", hexlist)
        data = {}
        try:
            start = 0
            page = "00"

            # prefix
            LOGGER.debug("start: %s", start)
            packet = "".join(hexlist[start:2])
            LOGGER.debug("hexlist: %s", packet)
            if packet != PACKET_PREFIX:
                LOGGER.error(
                    "Invalid packet prefix (%s) %s != %s : %s",
                    start,
                    packet,
                    PACKET_PREFIX,
                    hexlist,
                )
                raise ValueError(
                    f"Invalid packet prefix ({start}) {packet} != {PACKET_PREFIX}"
                )
            start += 2

            # protocol type
            LOGGER.debug("start: %s", start)
            packet = "".join(hexlist[start])
            LOGGER.debug("hexlist: %s", packet)
            if packet != PACKET_PROTOCOL_TYPE:
                LOGGER.error(
                    "Invalid packet protocol type (%s) %s != %s : %s",
                    start,
                    packet,
                    PACKET_PROTOCOL_TYPE,
                    hexlist,
                )
                raise ValueError(
                    f"Invalid packet protocol type ({start}) {packet} != {PACKET_PROTOCOL_TYPE}"
                )
            start += 1

            # id
            LOGGER.debug("start: %s", start)
            packet = "".join(hexlist[start])
            LOGGER.debug("hexlist: %s", packet)
            start += 1 + int(packet, 16)

            # password
            LOGGER.debug("start: %s", start)
            packet = "".join(hexlist[start])
            LOGGER.debug("hexlist: %s", packet)
            start += 1 + int(packet, 16)

            # function
            LOGGER.debug("start: %s", start)
            packet = "".join(hexlist[start])
            LOGGER.debug("hexlist: %s", packet)
            if packet != FUNC_RESULT:
                LOGGER.error(
                    "Invalid result function (%s) %s != %s : %s",
                    start,
                    packet,
                    FUNC_RESULT,
                    hexlist,
                )
                raise ValueError(
                    f"Invalid result function ({start}) {packet} != {FUNC_RESULT}"
                )
            start += 1

            # data
            LOGGER.debug("loop data %s %s", start, len(hexlist) - 2)
            i = start
            while i < (len(hexlist) - 2):
                LOGGER.debug("parse data %s : %s", i, hexlist[i])
                parameter = hexlist[i]
                cmd = ""
                value = ""

                if parameter == RETURN_CHANGE_FUNC:
                    # Mixed operations can appear in one response; not needed for
                    # value decoding, so skip and continue.
                    i += 1
                    LOGGER.debug(
                        "special function, change base function to %s", hexlist[i]
                    )
                    i += 1
                    continue

                if parameter == RETURN_HIGH_BYTE:
                    i += 1
                    page = hexlist[i]
                    LOGGER.debug("special function, high byte page set to %s", page)
                    i += 1
                    continue

                if parameter == RETURN_INVALID:
                    i += 1
                    cmd = hexlist[i]
                    if page != "00":
                        cmd = f"{page}{cmd}"
                    LOGGER.debug("special function, invalid cmd:%s", cmd)
                    data.update({cmd: ""})
                    i += 1
                    continue

                if parameter == RETURN_VALUE_SIZE:
                    i += 1
                    value_size = int(hexlist[i], 16)
                    LOGGER.debug("special function, value size %s", value_size)
                    i += 1
                    cmd = hexlist[i]
                    if page != "00":
                        cmd = f"{page}{cmd}"

                    value = "".join(hexlist[i + 1 : i + 1 + value_size])
                    # reverse byte order
                    value = "".join(
                        [value[idx : idx + 2] for idx in range(0, len(value), 2)][::-1]
                    )
                    data.update({cmd: value})
                    LOGGER.debug(
                        "return data cmd:%s value:%s",
                        cmd,
                        value,
                    )
                    i += 1 + value_size
                    continue

                cmd = parameter
                if page != "00":
                    cmd = f"{page}{cmd}"
                i += 1
                value = hexlist[i]
                LOGGER.debug("normal function, cmd:%s value:%s", cmd, value)

                data.update({cmd: value})
                LOGGER.debug(
                    "return data cmd:%s value:%s",
                    cmd,
                    value,
                )
                i += 1
        except IndexError as ex:
            raise ValueError(
                f"Error translating response from fan controller: {str(ex)}"
            ) from ex
        except KeyError as ex:
            raise ValueError(
                f"Error translating response from fan controller: {str(ex)}"
            ) from ex
        return data

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
COMMAND_CURRENT_HUMIDITY = "25"
COMMAND_MANUAL_SPEED = "44"
COMMAND_FAN1RPM = "4A"
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

COMMAND_FUNCTION_R = "01"
COMMAND_FUNCTION_W = "02"
COMMAND_FUNCTION_RW = "03"
COMMAND_FUNCTION_INC = "04"
COMMAND_FUNCTION_DEC = "05"

POWER_OFF = "00"
POWER_ON = "01"
POWER_TOGGLE = "02"

MODE_OFF = "01"
MODE_SLEEP = "01"
MODE_PARTY = "02"
MODES = {
    MODE_OFF: PRESET_MODE_AUTO,
    MODE_SLEEP: PRESET_MODE_SLEEP,
    MODE_PARTY: PRESET_MODE_PARTY,
}

EMPTY_VALUE = "00"

SPEED_MANUAL_MIN: int = 0
SPEED_MANUAL_MAX: int = 255


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
            COMMAND_CURRENT_HUMIDITY,
            COMMAND_FAN1RPM,
            COMMAND_FILTER_TIMER,
            COMMAND_READ_ALARM,
            COMMAND_READ_FIRMWARE_VERSION,
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

    async def _translate_response(self, data: dict) -> dict:
        """Translate response data to dict."""
        LOGGER.debug("translate response: %s", data)
        try:
            is_on = bool(data[COMMAND_ON_OFF] == POWER_ON)
        except KeyError:
            is_on = False
        try:
            speed = f"{int(data[COMMAND_SPEED], 16):02}"
        except KeyError:
            speed = "255"
        try:
            manual_speed = f"{int(data[COMMAND_MANUAL_SPEED], 16):02}"
        except KeyError:
            manual_speed = "00"
        try:
            direction = DIRECTIONS[data[COMMAND_DIRECTION]]
            oscillating = bool(direction == DIRECTION_ALTERNATING)
        except KeyError:
            direction = None
            oscillating = True
        try:
            boost = bool(data[COMMAND_BOOST] != "00")
        except KeyError:
            boost = False
        try:
            mode = MODES[data[COMMAND_MODE]]
        except KeyError:
            mode = PRESET_MODE_AUTO
        try:
            humidity = int(data[COMMAND_CURRENT_HUMIDITY], 16)
        except KeyError:
            humidity = None
        try:
            rpm = int(data[COMMAND_FAN1RPM], 16)
        except KeyError:
            rpm = 0
        try:
            # Byte 1: Minutes (0...59)
            # Byte 2: Hours (0...23)
            # Byte 3: Days (0...181)
            # days = int(data[COMMAND_FILTER_TIMER][0:2], 16)
            # hours = int(data[COMMAND_FILTER_TIMER][2:4], 16)
            # minutes = int(data[COMMAND_FILTER_TIMER][4:6], 16)
            # filter_timer = int(minutes + hours * 60 + days * 24 * 60)
            minutes = int(data[COMMAND_FILTER_TIMER][6:8], 16)
            hours = int(data[COMMAND_FILTER_TIMER][4:6], 16)
            days = int(data[COMMAND_FILTER_TIMER][2:4], 16)
            filter_timer = int(days * 24 * 60 + hours * 60 + minutes)
        except KeyError:
            filter_timer = 0
        try:
            alarm = bool(data[COMMAND_READ_ALARM] != "00")
        except KeyError:
            alarm = False
        try:
            # Byte 1: Firmware-Version (major)
            # Byte 2: Firmware-Version (minor)
            # Byte 3: Day
            # Byte 4: Month
            # Byte 5 and 6: Year
            firmware = f"{int(data[COMMAND_READ_FIRMWARE_VERSION][0], 16)}.{int(data[COMMAND_READ_FIRMWARE_VERSION][1], 16)}"
        except KeyError:
            firmware = None
        try:
            # Byte 1 – seconds (0…59)
            # Byte 2 – minutes (0…59)
            # Byte 3 – hours (0…23)
            hours = int(data[COMMAND_TIMER_COUNTDOWN][0:2], 16)
            minutes = int(data[COMMAND_TIMER_COUNTDOWN][2:4], 16)
            seconds = int(data[COMMAND_TIMER_COUNTDOWN][4:6], 16)
            timer_countdown = int(seconds + minutes * 60 + hours * 60 * 60)
        except KeyError:
            timer_countdown = 0
        return {
            "is_on": is_on,
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
            "mode": mode,
            "humidity": humidity,
            "rpm": rpm,
            "firmware": firmware,
            "filter_timer_days": filter_timer,
            "timer_countdown": timer_countdown,
            "alarm": alarm,
            "version": "2",
        }

    async def _parse_response(self, hexlist: list[str]) -> dict:
        """Translate response from fan controller."""
        LOGGER.debug("parse response: %s", hexlist)
        data = {}
        try:
            start = 0

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
                value_size = 1
                cmd = ""
                value = ""
                if parameter == RETURN_CHANGE_FUNC:
                    LOGGER.debug(
                        "special function, change base function not implemented %s",
                        parameter,
                    )
                    raise NotImplementedError(
                        f"special function, change base function not implemented {parameter}"
                    )
                if parameter == RETURN_HIGH_BYTE:
                    LOGGER.debug(
                        "special function, high byte not implemented %s", parameter
                    )
                    raise NotImplementedError(
                        f"special function, high byte not implemented {parameter}"
                    )
                if parameter == RETURN_INVALID:
                    i += 1
                    cmd = hexlist[i]
                    LOGGER.debug("special function, invalid cmd:%s", cmd)
                elif parameter == RETURN_VALUE_SIZE:
                    i += 1
                    value_size = int(hexlist[i], 16)
                    LOGGER.debug("special function, value size %s", value_size)
                    i += 1
                    cmd = hexlist[i]
                    value = "".join(hexlist[i + 1 : i + 1 + value_size])
                    # reverse byte order
                    value = "".join(
                        [value[idx : idx + 2] for idx in range(0, len(value), 2)][::-1]
                    )
                    i += value_size
                else:
                    cmd = parameter
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
        except KeyError as ex:
            raise ValueError(
                f"Error translating response from fan controller: {str(ex)}"
            ) from ex
        return data

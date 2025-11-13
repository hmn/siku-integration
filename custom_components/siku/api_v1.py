"""Helper api function for sending commands to the fan controller."""

from enum import IntEnum
import logging
import asyncio
from types import NoneType
from .udp import AsyncUdpClient
from homeassistant.util.percentage import percentage_to_ranged_value

from .const import DIRECTIONS

LOGGER = logging.getLogger(__name__)

COMMAND_PACKET_PREFIX = bytes.fromhex("6D6F62696C65")
COMMAND_PACKET_POSTFIX = bytes.fromhex("0D0A")
FEEDBACK_PACKET_PREFIX = bytes.fromhex("6D6173746572")


class SpeedSelection(IntEnum):
    """Speed selection for preset mode."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


SPEED_MANUAL_MIN: int = 22
SPEED_MANUAL_MAX: int = 255


class SpeedManual:
    """Manual speed selection."""

    def __init__(self, value: int):
        """Initialize checks for allowed values."""
        if SPEED_MANUAL_MIN < value > SPEED_MANUAL_MAX:
            raise ValueError("Value must be between 22 and 255")
        self.value = value

    def __int__(self):
        """Return the value."""
        return self.value


class Direction(IntEnum):
    """Direction selection for fan."""

    VENTILATION = 0  # push air out of the room
    HEAT_RECOVERY = 1  # alternate between pushing air out and pulling air in
    AIR_SUPPLY = 2  # pull air into the room


class Timer(IntEnum):
    """Timer selection for fan."""

    AUTO = 0
    NIGHT = 1
    PARTY = 2


class HumiditySensorThreshold:
    """Humidity sensor threshold setting, [RH%]."""

    def __init__(self, value: int):
        """Initialize checks for allowed values."""
        if 40 < value > 80:
            raise ValueError("Value must be between 40 and 80")
        self.value = value

    def __int__(self):
        """Return the value."""
        return self.value


class HumidityLevel:
    """Humidity sensor threshold setting, [RH%]."""

    def __init__(self, value: int):
        """Initialize checks for allowed values."""
        if 39 < value > 90:
            raise ValueError("Value must be between 40 and 80")
        self.value = value

    def __int__(self):
        """Return the value."""
        return self.value


class TimerSeconds:
    """Timer selection for fan."""

    def __init__(self, value: int):
        """Initialize checks for allowed values."""
        if 0 < value > 86400:
            raise ValueError(
                f"Invalid value {value}. Value must be between 0 and 86400."
            )
        self.value = value

    def __int__(self):
        """Return the value."""
        return self.value


class OffOn(IntEnum):
    """Device status (On/Off)."""

    OFF = 0
    ON = 1


class SpeedSelected(IntEnum):
    """Selected device speed."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    MANUAL = 4


class OperationMode(IntEnum):
    """Timer selection for fan."""

    REGULAR = 0
    NIGHT = 1
    PARTY = 2


class NoYes(IntEnum):
    """No/Yes response."""

    NO = 0
    YES = 1


class NoYesYes(IntEnum):
    """No/Yes response."""

    NO = 0
    YES = 1
    YES2 = 2


class ZeroTenVoltThreshold:
    """0 - 10 V sensor activation threshold, [%]."""

    def __init__(self, value: int):
        """Initialize checks for allowed values."""
        if 5 < value > 100:
            raise ValueError("Value must be between 0 and 255")
        self.value = value

    def __int__(self):
        """Return the value."""
        return self.value


CONTROL = {
    "status": {"cmd": 1, "size": 1, "value": NoneType},
    "activation": {"cmd": 2, "size": 1, "value": NoneType},
    "power": {"cmd": 3, "size": 1, "value": NoneType},
    "speed": {"cmd": 4, "size": 1, "value": SpeedSelection},
    "manual_speed": {"cmd": 5, "size": 1, "value": SpeedManual},
    "direction": {"cmd": 6, "size": 1, "value": Direction},
    "timer": {"cmd": 9, "size": 1, "value": Timer},
    "humidity_sensor_threshold": {
        "cmd": 11,
        "size": 1,
        "value": HumiditySensorThreshold,
    },
    "night_mode_timer": {"cmd": 15, "size": 3, "value": TimerSeconds},
    "party_mode_timer": {"cmd": 16, "size": 3, "value": TimerSeconds},
    "deactivation_delay_timer": {"cmd": 17, "size": 3, "value": TimerSeconds},
    "humidity_sensor": {"cmd": 21, "size": 1, "value": NoneType},
    "reset_filter_alarm": {"cmd": 30, "size": 1, "value": NoneType},
}

FEEDBACK = {
    "status": {
        "cmd": 3,
        "size": 1,
        "value": OffOn,
        "description": "Device status (On/Off)",
    },
    "speed": {
        "cmd": 4,
        "size": 1,
        "value": SpeedSelected,
        "description": "Selected speed",
    },
    "manual_speed": {
        "cmd": 5,
        "size": 1,
        "value": SpeedManual,
        "description": "Manual speed setting value ",
    },
    "direction": {
        "cmd": 6,
        "size": 1,
        "value": Direction,
        "description": "Air flow direction",
    },
    "humidity_level": {
        "cmd": 8,
        "size": 1,
        "value": HumidityLevel,
        "description": "Current humidity level, [RH%]",
    },
    "operation_mode": {
        "cmd": 9,
        "size": 1,
        "value": OperationMode,
        "description": "Operation mode",
    },
    "humidity_sensor_threshold": {
        "cmd": 11,
        "size": 1,
        "value": HumiditySensorThreshold,
        "description": "Humidity sensor activation threshold, [RH%] ",
    },
    "alarm_status": {
        "cmd": 12,
        "size": 1,
        "value": NoYes,
        "description": "Alarm status (emergency stop)(status bar) ",
    },
    "relay_sensor_status": {
        "cmd": 13,
        "size": 1,
        "value": NoYes,
        "description": "Relay sensor status (status bar)",
    },
    "timer_countdown": {
        "cmd": 14,
        "size": 3,
        "value": TimerSeconds,
        "description": "Party mode / night mode timer countdown, [sec]",
    },
    "night_mode_timer": {
        "cmd": 15,
        "size": 3,
        "value": TimerSeconds,
        "description": "Current night time mode timer setting, [sec]",
    },
    "party_mode_timer": {
        "cmd": 16,
        "size": 3,
        "value": TimerSeconds,
        "description": "Current party mode timer setting, [sec]",
    },
    "boost_mode_timer": {
        "cmd": 17,
        "size": 3,
        "value": TimerSeconds,
        "description": "Current deactivation delay timer setting (boost mode), [sec]",
    },
    "filter_end_of_life": {
        "cmd": 18,
        "size": 1,
        "value": NoYes,
        "description": "Filter end of life message (status bar)",
    },
    "humidity_sensor_status": {
        "cmd": 19,
        "size": 1,
        "value": NoYes,
        "description": "Humidity sensor status (status bar)",
    },
    "boost_mode_after_sensor": {
        "cmd": 20,
        "size": 1,
        "value": NoYesYes,
        "description": "BOOST mode after any sensor response (status bar)",
    },
    "humidity_sensor": {
        "cmd": 21,
        "size": 1,
        "value": OffOn,
        "description": "Humidity sensor",
    },
    "relay_sensor": {
        "cmd": 22,
        "size": 1,
        "value": OffOn,
        "description": "Relay sensor",
    },
    "zero_ten_volt_sensor": {
        "cmd": 23,
        "size": 1,
        "value": OffOn,
        "description": "0-10 V sensor",
    },
    "zero_ten_volt_threshold": {
        "cmd": 25,
        "size": 1,
        "value": ZeroTenVoltThreshold,
        "description": "0-10 V sensor activation threshold, [%]",
    },
    "zero_ten_volt_sensor_status": {
        "cmd": 26,
        "size": 1,
        "value": NoYes,
        "description": "0-10 V sensor status (status bar) ",
    },
    "slave_search": {
        "cmd": 27,
        "size": 32,
        "value": int,
        "description": "Slave search",
    },
    "slave_response": {
        "cmd": 28,
        "size": 4,
        "value": int,
        "description": "Response to «Slave device search» request",
    },
    "cloud_status": {
        "cmd": 31,
        "size": 1,
        "value": NoYes,
        "description": "Cloud server control activation status",
    },
    "zero_ten_volt_current": {
        "cmd": 37,
        "size": 1,
        "value": int,
        "description": "0-10 V sensor current status",
    },
}


class SikuV1Api:
    """Handle requests to the fan controller."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self._udp = AsyncUdpClient(self.host, self.port)
        self._lock = asyncio.Lock()

    async def status(self) -> dict:
        """Get status from fan controller."""
        data = await self._control_packet([("status", None)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        return await self._format_response(result)

    async def power_on(self) -> dict:
        """Power on fan."""
        data = await self._control_packet([("status", None)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        if result["status"] == OffOn.OFF:
            data = await self._control_packet([("power", None)])
            hexlist = await self._send_command(data)
            result = await self._translate_response(hexlist)
            LOGGER.info("Power ON fan : %s", result["operation_mode"])
        return await self._format_response(result)

    async def power_off(self) -> dict:
        """Power off fan."""
        data = await self._control_packet([("status", None)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        if result["status"] == OffOn.ON:
            data = await self._control_packet([("power", None)])
            hexlist = await self._send_command(data)
            result = await self._translate_response(hexlist)
            LOGGER.info("Power OFF fan : %s", result["operation_mode"])
        return await self._format_response(result)

    async def speed(self, speed: str | int) -> dict:
        """Set fan speed."""
        speed = SpeedSelection(int(speed))
        data = await self._control_packet([("speed", speed)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        LOGGER.info("Set speed to %s : %s", speed, result["speed"])
        return await self._format_response(result)

    async def speed_manual(self, percentage: int) -> dict:
        """Set fan speed."""
        low_high_range = (float(SPEED_MANUAL_MIN), float(SPEED_MANUAL_MAX))
        speed: int = int(
            percentage_to_ranged_value(
                low_high_range=low_high_range, percentage=float(percentage)
            )
        )
        data = await self._control_packet([("manual_speed", speed)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        LOGGER.info("Set manual speed to %s : %s", speed, result["manual_speed"])
        return await self._format_response(result)

    async def direction(self, direction: str | int) -> dict:
        """Set fan direction."""
        # if direction is in DIRECTIONS values translate it to the key value
        # NOTE: cleanup desired
        if direction in DIRECTIONS.values():
            direction = list(DIRECTIONS.keys())[
                list(DIRECTIONS.values()).index(str(direction))
            ]
        if direction not in DIRECTIONS:
            raise ValueError(f"Invalid fan direction: {direction}")
        direction = Direction(int(direction))
        data = await self._control_packet([("direction", direction)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        LOGGER.info("Set direction to %s : %s", direction, result["direction"])
        return await self._format_response(result)

    async def sleep(self) -> dict:
        """Set fan to sleep mode."""
        await self.power_on()
        data = await self._control_packet([("timer", Timer.NIGHT)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        LOGGER.info("Set sleep mode : %s", result["operation_mode"])
        return await self._format_response(result)

    async def party(self) -> dict:
        """Set fan to party mode."""
        await self.power_on()
        data = await self._control_packet([("timer", Timer.PARTY)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        LOGGER.info(
            "Set party mode : %s timer:%s",
            result["operation_mode"],
            result["timer_countdown"],
        )
        result["status"] = OffOn.ON
        result["speed"] = SpeedSelection.HIGH
        result["direction"] = Direction.VENTILATION
        LOGGER.info(
            "Overwrite party mode values : status:%s speed:%s direction:%s",
            result["status"],
            result["speed"],
            result["direction"],
        )
        return await self._format_response(result)

    async def reset_filter_alarm(self) -> dict:
        """Reset filter alarm."""
        await self.power_on()
        data = await self._control_packet([("reset_filter_alarm", None)])
        hexlist = await self._send_command(data)
        result = await self._translate_response(hexlist)
        LOGGER.info("Reset filter alarm : %s", result["filter_end_of_life"])
        return await self._format_response(result)

    async def _control_packet(self, commands: list[tuple]) -> bytes:
        """Generate packet data for fan control."""
        if not isinstance(commands, list):
            raise TypeError("Commands must be a list of tuples")
        if not all(isinstance(command, tuple) for command in commands):
            raise TypeError("Commands must be a list of tuples")
        packet_data_list = []
        for command, value in commands:
            if command not in CONTROL:
                raise ValueError(f"Invalid command: {command}")
            if not isinstance(value, CONTROL[command]["value"]):
                raise TypeError(
                    f"Invalid value for command {command}: {type(value)} must be of type {CONTROL[command]['value']}"
                )

            # packet_command = bytes.fromhex(command)
            packet_command = CONTROL[command]["cmd"].to_bytes(1, byteorder="big")
            packet_size = CONTROL[command]["size"]
            if isinstance(value, NoneType):
                value = 0
            # LOGGER.debug("value: %s (%s)", value, type(value))
            packet_value = value.to_bytes(packet_size, byteorder="big")
            # LOGGER.debug("packet_value: %s", packet_value)
            # LOGGER.debug("packet_command: %s", packet_command)
            packet_data_list.append(packet_command + packet_value)

        # LOGGER.debug("packet_data_list: %s", packet_data_list)
        packet_commands = b"".join(packet_data_list)
        # LOGGER.debug("packet_commands: %s", packet_commands)
        # LOGGER.debug("packet_commands: %s", packet_commands.hex())
        return packet_commands

    async def _send_command(self, data: bytes) -> list[str]:
        """Send command to fan controller using asyncio UDP transport."""
        packet_data = COMMAND_PACKET_PREFIX + data + COMMAND_PACKET_POSTFIX

        for attempt in range(3):
            try:
                async with self._lock:
                    data_bytes = await self._udp.request(packet_data, timeout=2.0)
                # Match feedback packet prefix and cut from the data
                if data_bytes.startswith(FEEDBACK_PACKET_PREFIX):
                    data_bytes = data_bytes[len(FEEDBACK_PACKET_PREFIX) :]
                hexstring = data_bytes.hex()
                hexlist = ["".join(x) for x in zip(*[iter(hexstring)] * 2)]
                LOGGER.debug("returning hexlist %s", hexlist)
                return hexlist
            except (asyncio.TimeoutError, TimeoutError) as ex:
                LOGGER.warning(
                    "Timeout occurred (%s), retrying... (%d/3)",
                    type(ex).__name__,
                    attempt + 1,
                )
                if attempt == 2:
                    raise TimeoutError(
                        "Failed to send command after 3 attempts"
                    ) from ex
        raise LookupError(f"Failed to send command to {self.host}:{self.port}")

    async def _translate_response(self, hexlist: list[str]) -> dict:
        """Translate response from fan controller."""
        data = {}
        # traverse hexlist response and match feedback params
        i = 0
        while i < len(hexlist):
            cmd = hexlist[i]
            cmd = int(hexlist[i], 16)
            # loop all of the feedback params to find a match
            for key, item in FEEDBACK.items():
                if cmd == item["cmd"]:
                    size = item["size"]
                    value_type = item["value"]
                    value_raw = hexlist[i + 1 : i + 1 + size]
                    # LOGGER.debug("value_raw:%s", value_raw)
                    if value_type is not NoneType:
                        value = int("".join(value_raw), 16)
                        # LOGGER.debug("value:%s", value)
                        value = value_type(value)
                        # LOGGER.debug("value:%s", value)
                    else:
                        value = None
                    data[key] = value
                    LOGGER.debug(
                        "index:%s/%s key:%s cmd:%s size:%s value_raw:%s value:%s",
                        i,
                        len(hexlist),
                        key,
                        cmd,
                        size,
                        value_raw,
                        value,
                    )
                    i += 1 + size
                    break
            else:
                LOGGER.debug("index:%s/%s No match for cmd:%s", i, len(hexlist), cmd)
                i += 2
        return data

    async def _format_response(self, data: dict) -> dict:
        """Format response for entities."""
        return {
            "is_on": bool(data["status"] == OffOn.ON),
            "speed": int(data["speed"]),
            "speed_list": list(map(int, SpeedSelection)),
            "manual_speed_selected": bool(data["speed"] == SpeedSelected.MANUAL),
            "manual_speed": int(data["manual_speed"]),
            "manual_speed_low_high_range": (SPEED_MANUAL_MIN, SPEED_MANUAL_MAX),
            "oscillating": bool(data["direction"] == Direction.HEAT_RECOVERY),
            "direction": (
                data["direction"]
                if data["direction"] == Direction.HEAT_RECOVERY
                else None
            ),
            "mode": data["operation_mode"],
            "humidity": int(data["humidity_level"]),
            "alarm": bool(data["filter_end_of_life"] == NoYes.YES),
            "timer_countdown": int(data["timer_countdown"]),
            "boost": bool(
                data["boost_mode_after_sensor"] == NoYesYes.YES
                or data["boost_mode_after_sensor"] == NoYesYes.YES2
            ),
            "boost_mode_timer": int(data["boost_mode_timer"])
            if "boost_mode_timer" in data
            else None,
            "night_mode_timer": int(data["night_mode_timer"])
            if "night_mode_timer" in data
            else None,
            "party_mode_timer": int(data["party_mode_timer"])
            if "party_mode_timer" in data
            else None,
            "version": "1",
        }

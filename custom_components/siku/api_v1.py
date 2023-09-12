"""Helper api function for sending commands to the fan controller."""
import logging
import socket

from .const import DIRECTION_ALTERNATING
from .const import DIRECTIONS
from .const import FAN_SPEEDS

LOGGER = logging.getLogger(__name__)

# forward = pull air out of the room
# reverse = pull air into the room from outside
# alternating = change directions (used for oscilating option in fan)
PACKET_PREFIX = bytes.fromhex("6d6f62696c65")
PACKET_POSTFIX = bytes.fromhex("0d0a")

COMMAND_STATUS = "01"
COMMAND_DIRECTION = "06"
COMMAND_SPEED = "04"
COMMAND_POWER = "03"
COMMAND_SLEEP = "0901"
COMMAND_PARTY = "0902"
HEX_KEY_POWER = 7
HEX_KEY_MODE = 9
HEX_KEY_SPEED = 19
HEX_KEY_DIRECTION = 23
RESULT_POWER_ON = "01"
RESULT_POWER_OFF = "00"


class SikuV1Api:
    """Handle requests to the fan controller."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize."""
        self.host = host
        self.port = port

    async def status(self) -> dict:
        """Get status from fan controller."""
        hexlist = await self._send_command(COMMAND_STATUS)
        return await self._translate_response(hexlist)

    async def power_on(self) -> None:
        """Power on fan."""
        hexlist = await self._send_command(COMMAND_STATUS)
        if hexlist[HEX_KEY_POWER] != RESULT_POWER_ON:
            hexlist = await self._send_command(COMMAND_POWER)
        return await self._translate_response(hexlist)

    async def power_off(self) -> None:
        """Power off fan."""
        hexlist = await self._send_command(COMMAND_STATUS)
        if hexlist[HEX_KEY_POWER] != RESULT_POWER_OFF:
            hexlist = await self._send_command(COMMAND_POWER)
        return await self._translate_response(hexlist)

    async def speed(self, speed: str) -> None:
        """Set fan speed."""
        if speed not in FAN_SPEEDS:
            raise ValueError(f"Invalid fan speed: {speed}")
        hexlist = await self._send_command(COMMAND_STATUS)
        if hexlist[HEX_KEY_SPEED] != speed:
            hexlist = await self._send_command(COMMAND_SPEED + speed)
        return await self._translate_response(hexlist)

    async def direction(self, direction: str) -> None:
        """Set fan direction."""
        # if direction is in DIRECTIONS values translate it to the key value
        if direction in DIRECTIONS.values():
            direction = list(DIRECTIONS.keys())[
                list(DIRECTIONS.values()).index(direction)
            ]
        if direction not in DIRECTIONS:
            raise ValueError(f"Invalid fan direction: {direction}")
        hexlist = await self._send_command(COMMAND_STATUS)
        if hexlist[HEX_KEY_DIRECTION] != direction:
            hexlist = await self._send_command(COMMAND_DIRECTION + direction)
        return await self._translate_response(hexlist)

    async def sleep(self) -> None:
        """Set fan to sleep mode."""
        await self.power_on()
        hexlist = await self._send_command(COMMAND_SLEEP)
        return await self._translate_response(hexlist)

    async def party(self) -> None:
        """Set fan to party mode."""
        await self.power_on()
        hexlist = await self._send_command(COMMAND_PARTY)
        return await self._translate_response(hexlist)

    async def _send_command(self, command: str) -> list[str]:
        """Send command to fan controller."""
        packet_command = bytes.fromhex(command)

        # enter the data content of the UDP packet as hex
        packet_data = PACKET_PREFIX + packet_command + PACKET_POSTFIX

        # initialize a socket, think of it as a cable
        # SOCK_DGRAM specifies that this is UDP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0) as s:
            s.settimeout(10)

            server_address = (self.host, self.port)
            LOGGER.debug('sending "%s" to %s', packet_data, server_address)
            s.sendto(packet_data, server_address)

            # Receive response
            data, server = s.recvfrom(4096)
            LOGGER.debug('received "%s" from %s', data, server)

            hexstring = data.hex()
            hexlist = ["".join(x) for x in zip(*[iter(hexstring)] * 2)]
            LOGGER.debug("returning hexlist %s", hexlist)
            return hexlist

    async def _translate_response(self, hexlist: list[str]) -> dict:
        """Translate response from fan controller."""
        try:
            power_value = hexlist[HEX_KEY_POWER]
            mode_value = hexlist[HEX_KEY_MODE]
            speed_value = hexlist[HEX_KEY_SPEED]
            direction_value = hexlist[HEX_KEY_DIRECTION]
        except KeyError as ex:
            raise ValueError(
                f"Error translating response from fan controller: {str(ex)}"
            ) from ex

        return {
            "is_on": bool(power_value == RESULT_POWER_ON),
            "speed": speed_value,
            "oscillating": bool(direction_value == DIRECTION_ALTERNATING),
            "direction": DIRECTIONS[direction_value]
            if direction_value != DIRECTION_ALTERNATING
            else None,
            "mode": mode_value,
        }

"""Data update coordinator for the Deluge integration."""
from __future__ import annotations

import logging
import socket
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api_v1 import SikuV1Api
from .api_v2 import SikuV2Api
from .const import CONF_ID
from .const import CONF_VERSION

LOGGER = logging.getLogger(__name__)


class SikuDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Deluge integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=30),
        )
        self.config_entry = entry
        if entry.data[CONF_VERSION] == 1:
            self.api = SikuV1Api(entry.data[CONF_IP_ADDRESS], entry.data[CONF_PORT])
        else:
            self.api = SikuV2Api(
                entry.data[CONF_IP_ADDRESS],
                entry.data[CONF_PORT],
                entry.data[CONF_ID],
                entry.data[CONF_PASSWORD],
            )

    async def _async_update_data(self) -> dict[Platform, dict[str, int | str]]:
        """Get the latest data from Siku fan and updates the state."""
        data = {}
        try:
            data = await self.api.status()
            # self.logger.debug(data)
        except (OSError, socket.timeout) as ex:
            raise UpdateFailed(f"Connection to Siku Fan failed: {ex}") from ex
        return data

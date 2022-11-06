"""Data update coordinator for the Deluge integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import socket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import SikuApi

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
        self.api = SikuApi(entry.data[CONF_HOST], entry.data[CONF_PORT])

    async def _async_update_data(self) -> dict[Platform, dict[str, int | str]]:
        """Get the latest data from Siku fan and updates the state."""
        data = {}
        try:
            data = await self.api.status()
            # self.logger.debug(data)
        except (socket.error, socket.timeout) as ex:
            raise UpdateFailed(f"Connection to Siku RV Fan failed: {ex}") from ex
        return data

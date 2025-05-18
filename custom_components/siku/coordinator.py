"""Data update coordinator for the Deluge integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api_v1 import SikuV1Api
from .api_v2 import SikuV2Api
from .const import (
    CONF_ID,
    DEFAULT_MODEL,
    DEFAULT_NAME,
)
from .const import CONF_VERSION
from .const import DOMAIN
from .const import DEFAULT_MANUFACTURER

LOGGER = logging.getLogger(__name__)


class SikuDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Deluge integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
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
        name = f"{DEFAULT_NAME} {entry.data[CONF_IP_ADDRESS]}"

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=name,
            update_interval=timedelta(seconds=30),
            update_method=self._update_method,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the DeviceInfo of this Siku fan using IP as identifier."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.api.host}:{self.api.port}")},
            model=DEFAULT_MODEL,
            manufacturer=DEFAULT_MANUFACTURER,
            name=self.name or f"{DEFAULT_NAME} {self.api.host}",
        )

    async def _update_method(self) -> dict[str, int | str]:
        """Get the latest data from Siku fan and updates the state."""
        data = {}
        try:
            data = await self.api.status()
            # self.logger.debug(data)
            # TODO: add better test options
            # TEST
            # data = {
            #     "is_on": False,
            #     "speed": "00",
            #     "oscillating": False,
            #     "direction": None,
            #     "mode": PRESET_MODE_PARTY,
            #     "humidity": 50 + randint(0, 50),
            #     "rpm": 1000 + randint(0, 1000),
            #     "firmware": "0.0",
            #     "filter_timer": 1440 * 30 + 65,
            #     "alarm": False,
            #     "version": "2",
            # }
        except (TimeoutError, OSError) as ex:
            raise UpdateFailed(f"Connection to Siku Fan failed: {ex}") from ex
        return data

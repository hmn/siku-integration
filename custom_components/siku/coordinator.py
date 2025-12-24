"""Data update coordinator for the Deluge integration."""

from __future__ import annotations

import logging
import time
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

        # Keep a stable reference to the config entry for unique_id generation.
        self.config_entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return the DeviceInfo of this Siku (Blauberg) Fan.

        Note: Identifiers must be stable across IP/port changes to avoid creating
        duplicate devices after reconfiguration.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            model=DEFAULT_MODEL,
            manufacturer=DEFAULT_MANUFACTURER,
            name=self.name or f"{DEFAULT_NAME} {self.api.host}",
        )

    async def _update_method(self) -> dict[str, int | str]:
        """Get the latest data from Siku (Blauberg) Fan and updates the state."""
        LOGGER.debug(
            "Updating Siku (Blauberg) Fan status from %s:%d",
            self.api.host,
            self.api.port,
        )
        start_time = time.time()
        try:
            data: dict = await self.api.status()
            elapsed = time.time() - start_time
            self.logger.debug(
                "Fetched status from %s:%d in %.3f seconds",
                self.api.host,
                self.api.port,
                elapsed,
            )
            return data
        except TimeoutError as ex:
            elapsed = time.time() - start_time
            error_msg = (
                f"Timeout connecting to Siku (Blauberg) Fan at {self.api.host}:{self.api.port} "
                f"after {elapsed:.3f}s: {ex}"
            )
            self.logger.error(error_msg)
            raise UpdateFailed(error_msg) from ex
        except (OSError, LookupError) as ex:
            elapsed = time.time() - start_time
            error_msg = (
                f"Connection to Siku (Blauberg) Fan at {self.api.host}:{self.api.port} failed "
                f"after {elapsed:.3f}s: {ex}"
            )
            self.logger.error(error_msg)
            raise UpdateFailed(error_msg) from ex

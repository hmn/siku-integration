"""The Siku Fan integration."""

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_NAME
from .coordinator import SikuDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Siku Fan from a config entry."""

    coordinator = SikuDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}

        if config_entry.minor_version < 1:
            host = config_entry.data[CONF_IP_ADDRESS]
            port = config_entry.data[CONF_PORT]
            unique_id = f"{host}:{port}"
            fix_names = [
                f"{DOMAIN} {host}:{port}",
                f"{DEFAULT_NAME} {host}:{port}",
                f"{DOMAIN} {host}",
                f"{host}:{port}",
            ]
            if config_entry.title in fix_names:
                title = f"{DEFAULT_NAME} {host}"
            else:
                title = config_entry.title
            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                unique_id=unique_id,
                title=title,
                version=1,
                minor_version=1,
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


class SikuEntity(CoordinatorEntity[SikuDataUpdateCoordinator]):
    """Representation of a siku entity."""

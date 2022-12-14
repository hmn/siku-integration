"""The Siku Fan integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MANUFACTURER
from .const import DEFAULT_MODEL
from .const import DEFAULT_NAME
from .const import DOMAIN
from .coordinator import SikuDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.FAN]


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


class SikuEntity(CoordinatorEntity[SikuDataUpdateCoordinator]):
    """Representation of a siku entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SikuDataUpdateCoordinator) -> None:
        """Initialize a siku entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            default_manufacturer=DEFAULT_MANUFACTURER,
            default_model=DEFAULT_MODEL,
            default_name=DEFAULT_NAME,
        )

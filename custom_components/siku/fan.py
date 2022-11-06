"""Demo fan platform that has a fake fan."""
from __future__ import annotations
import logging

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import SikuEntity
from .const import DOMAIN, DEFAULT_NAME
from .api import FAN_SPEEDS

# from .api import SikuApi
from .coordinator import SikuDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)

# percentage = ordered_list_item_to_percentage(FAN_SPEEDS, "01")
# named_speed = percentage_to_ordered_list_item(FAN_SPEEDS, 33)

PRESET_MODE_AUTO = "auto"

PRESET_MODE_AUTO = "auto"
PRESET_MODE_SMART = "smart"
PRESET_MODE_SLEEP = "sleep"
PRESET_MODE_ON = "on"

FULL_SUPPORT = (
    FanEntityFeature.SET_SPEED | FanEntityFeature.OSCILLATE | FanEntityFeature.DIRECTION
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku RV fan."""
    async_add_entities(
        [
            SikuFan(
                hass,
                hass.data[DOMAIN][entry.entry_id],
                f"{entry.entry_id}",
                DEFAULT_NAME,
                FULL_SUPPORT,
            )
        ]
    )


class SikuFan(SikuEntity, FanEntity):
    """Siku RV Fan"""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SikuDataUpdateCoordinator,
        unique_id: str,
        name: str,
        supported_features: int,
        preset_modes: list[str] | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.hass = hass
        self._unique_id = unique_id
        self._supported_features = supported_features
        self._percentage: int | None = None
        self._preset_modes = preset_modes
        self._preset_mode: str | None = None
        self._oscillating: bool | None = None
        self._direction: str | None = None
        self._attr_name = name or DEFAULT_NAME
        if supported_features & FanEntityFeature.OSCILLATE:
            self._oscillating = True
        if supported_features & FanEntityFeature.DIRECTION:
            self._direction = None

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def current_direction(self) -> str | None:
        """Fan direction."""
        return self._direction

    @property
    def oscillating(self) -> bool | None:
        """Oscillating."""
        return self._oscillating

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._percentage

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(FAN_SPEEDS)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self.coordinator.api.speed(
            percentage_to_ordered_list_item(FAN_SPEEDS, percentage)
        )
        self._percentage = percentage
        self._preset_mode = None
        self.async_write_ha_state()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        return self._preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return self._preset_modes

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            raise ValueError(
                f"{preset_mode} is not a valid preset_mode: {self.preset_modes}"
            )
        self._preset_mode = preset_mode
        self._percentage = None
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return

        if percentage is None:
            percentage = 33

        await self.coordinator.api.power_on()
        await self.async_set_percentage(percentage)
        await self.async_oscillate(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        await self.coordinator.api.power_off()
        await self.async_oscillate(False)
        await self.async_set_percentage(0)

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.coordinator.api.direction(direction)
        self._direction = direction
        self._oscillating = False
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        if oscillating:
            await self.coordinator.api.direction("alternating")
        else:
            await self.coordinator.api.direction("forward")
        self._oscillating = oscillating
        self._direction = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data["is_on"]
        self._percentage = ordered_list_item_to_percentage(
            FAN_SPEEDS, self.coordinator.data["speed"]
        )
        self._oscillating = self.coordinator.data["oscillating"]
        self._direction = self.coordinator.data["direction"]
        self.async_write_ha_state()

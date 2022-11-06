"""Demo fan platform that has a fake fan."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity
from homeassistant.components.fan import FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import ordered_list_item_to_percentage
from homeassistant.util.percentage import percentage_to_ordered_list_item

from . import SikuEntity
from .api import FAN_SPEEDS
from .const import DEFAULT_NAME
from .const import DOMAIN
from .coordinator import SikuDataUpdateCoordinator

# from .api import SikuApi

LOGGER = logging.getLogger(__name__)

# percentage = ordered_list_item_to_percentage(FAN_SPEEDS, "01")
# named_speed = percentage_to_ordered_list_item(FAN_SPEEDS, 33)

PRESET_MODE_AUTO = "auto"

PRESET_MODE_AUTO = "auto"
PRESET_MODE_SMART = "smart"
PRESET_MODE_SLEEP = "sleep"
PRESET_MODE_ON = "on"


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
            )
        ]
    )


class SikuFan(SikuEntity, FanEntity):
    """Siku RV Fan"""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.DIRECTION
    )
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SikuDataUpdateCoordinator,
        unique_id: str,
        name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.hass = hass
        self._unique_id = unique_id
        self._attr_name = name or DEFAULT_NAME

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(FAN_SPEEDS)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if hasattr(self, "_attr_percentage"):
            return self._attr_percentage
        return 0

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._attr_percentage = percentage

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            if not self.is_on:
                await self.async_turn_on()
            await self.coordinator.api.speed(
                percentage_to_ordered_list_item(FAN_SPEEDS, percentage)
            )
        await self.hass.async_add_executor_job(self.set_percentage, percentage)

    @property
    def oscillating(self) -> bool | None:
        """Oscillating."""
        return self._attr_oscillating

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        self._attr_oscillating = oscillating
        if oscillating:
            self.set_direction(None)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        self._attr_oscillating = oscillating
        if oscillating:
            if not self.is_on:
                await self.async_turn_on()
            await self.coordinator.api.direction("alternating")
        else:
            await self.coordinator.api.direction("forward")
        await self.hass.async_add_executor_job(self.oscillate, oscillating)
        self.async_write_ha_state()

    @property
    def current_direction(self) -> str | None:
        """Fan direction."""
        return self._attr_current_direction

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._attr_current_direction = direction

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.coordinator.api.direction(direction)
        self.set_direction(direction)
        if self.oscillating:
            self.oscillate(False)
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity."""
        if percentage is None:
            percentage = ordered_list_item_to_percentage(FAN_SPEEDS, FAN_SPEEDS[0])

        await self.coordinator.api.power_on()
        self.set_percentage(percentage)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        await self.coordinator.api.power_off()
        self.set_percentage(0)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Handling coordinator update %s", self.coordinator.data)
        if self.coordinator.data is None:
            return
        if self.coordinator.data["is_on"]:
            self.set_percentage(
                ordered_list_item_to_percentage(
                    FAN_SPEEDS, self.coordinator.data["speed"]
                )
            )
        else:
            self.set_percentage(0)
        if (
            not self.coordinator.data["oscillating"]
            and self.coordinator.data["direction"] != "alternating"
        ):
            self.oscillate(False)
            self.set_direction(self.coordinator.data["direction"])
        else:
            self.oscillate(True)

        super()._handle_coordinator_update()

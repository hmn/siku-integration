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
from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import FAN_SPEEDS
from .const import PRESET_MODE_AUTO
from .const import PRESET_MODE_ON
from .const import PRESET_MODE_PARTY
from .const import PRESET_MODE_SLEEP
from .coordinator import SikuDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)

# percentage = ordered_list_item_to_percentage(FAN_SPEEDS, "01")
# named_speed = percentage_to_ordered_list_item(FAN_SPEEDS, 33)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku fan."""
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
    """Siku Fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [
        PRESET_MODE_AUTO,
        PRESET_MODE_ON,
        PRESET_MODE_PARTY,
        PRESET_MODE_SLEEP,
    ]
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
        if name is None:
            name = {DEFAULT_NAME}
        self._attr_name = f"{name} {coordinator.api.host}"

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(FAN_SPEEDS)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._attr_percentage = percentage
        if percentage == 0:
            self.set_preset_mode(None)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.coordinator.api.power_off()
            await self.hass.async_add_executor_job(self.set_preset_mode, None)
        else:
            await self.coordinator.api.power_on()
            await self.coordinator.api.speed(
                percentage_to_ordered_list_item(FAN_SPEEDS, percentage)
            )
            if self.oscillating:
                await self.hass.async_add_executor_job(
                    self.set_preset_mode, PRESET_MODE_AUTO
                )
            else:
                await self.hass.async_add_executor_job(
                    self.set_preset_mode, PRESET_MODE_ON
                )
        await self.hass.async_add_executor_job(self.set_percentage, percentage)
        self.async_write_ha_state()

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
            await self.hass.async_add_executor_job(
                self.set_preset_mode, PRESET_MODE_AUTO
            )
        else:
            await self.coordinator.api.direction("forward")
            await self.hass.async_add_executor_job(self.set_preset_mode, PRESET_MODE_ON)
        await self.hass.async_add_executor_job(self.oscillate, oscillating)
        self.async_write_ha_state()

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._attr_current_direction = direction

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.coordinator.api.direction(direction)
        await self.hass.async_add_executor_job(self.set_direction, direction)
        if self.oscillating:
            await self.hass.async_add_executor_job(self.oscillate, False)
        await self.hass.async_add_executor_job(self.set_preset_mode, PRESET_MODE_ON)
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity."""
        if percentage is None:
            percentage = ordered_list_item_to_percentage(
                FAN_SPEEDS, FAN_SPEEDS[0])

        await self.async_set_percentage(percentage)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        await self.async_set_percentage(0)
        self.async_write_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        self._attr_preset_mode = preset_mode
        self.schedule_update_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_MODE_PARTY:
            await self.async_turn_on()
            await self.coordinator.api.party()
        elif preset_mode == PRESET_MODE_SLEEP:
            await self.async_turn_on()
            await self.coordinator.api.sleep()
        elif preset_mode == PRESET_MODE_AUTO:
            await self.async_turn_on()
            await self.async_oscillate(True)
        elif preset_mode == PRESET_MODE_ON:
            await self.async_turn_on()
            await self.async_set_direction("forward")
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)
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

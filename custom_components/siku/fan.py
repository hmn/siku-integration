"""Siku fan."""

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
from homeassistant.util.percentage import ranged_value_to_percentage

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku fan."""
    LOGGER.debug("Setting up Siku fan")
    LOGGER.debug("Entry: %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SikuFan(
                hass=hass,
                coordinator=coordinator,
                # entry=entry,
                # unique_id=f"{entry.entry_id}",
                # name=f"{DEFAULT_NAME} {entry.data[CONF_IP_ADDRESS]}",
            )
        ],
        True,
    )


class SikuFan(SikuEntity, FanEntity):
    """Siku Fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [
        PRESET_MODE_AUTO,
        PRESET_MODE_ON,
        PRESET_MODE_PARTY,
        PRESET_MODE_SLEEP,
    ]
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SikuDataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.hass = hass
        self._attr_name = f"{DEFAULT_NAME} {coordinator.api.host}"
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.api.host}-{coordinator.api.port}-fan"
        )

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
            if (
                self.coordinator.data["manual_speed_selected"]
                and self.coordinator.data["manual_speed"]
            ):
                await self.coordinator.api.speed_manual(percentage)
            elif self.coordinator.data["speed_list"]:
                await self.coordinator.api.speed(
                    percentage_to_ordered_list_item(
                        self.coordinator.data["speed_list"], percentage
                    )
                )
            else:
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
            percentage = ordered_list_item_to_percentage(FAN_SPEEDS, FAN_SPEEDS[0])

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
            response = await self.coordinator.api.party()
            if response:
                self.coordinator.async_set_updated_data(response)
        elif preset_mode == PRESET_MODE_SLEEP:
            await self.async_turn_on()
            response = await self.coordinator.api.sleep()
            if response:
                self.coordinator.async_set_updated_data(response)
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
            if (
                self.coordinator.data["manual_speed_selected"]
                and self.coordinator.data["manual_speed"]
            ):
                LOGGER.debug(
                    "Setting manual speed from %s",
                    self.coordinator.data["manual_speed"],
                )
                self.set_percentage(
                    ranged_value_to_percentage(
                        self.coordinator.data["manual_speed_low_high_range"],
                        self.coordinator.data["manual_speed"],
                    )
                )
                # self.set_percentage(self.coordinator.data["manual_speed"])
            elif self.coordinator.data["speed_list"]:
                LOGGER.debug(
                    "Setting percentage from speed %s", self.coordinator.data["speed"]
                )
                LOGGER.debug(
                    "Setting percentage from speed %s",
                    self.coordinator.data["speed_list"],
                )
                LOGGER.debug(
                    "Setting percentage from speed type %s",
                    type(self.coordinator.data["speed"]),
                )
                self.set_percentage(
                    ordered_list_item_to_percentage(
                        self.coordinator.data["speed_list"],
                        self.coordinator.data["speed"],
                    )
                )
            else:
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

"""Siku (Blauberg) Fan."""

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
from .const import DEFAULT_NAME, DIRECTION_FORWARD, DIRECTIONS
from .const import DOMAIN
from .const import FAN_SPEEDS
from .const import PRESET_MODE_AUTO
from .const import PRESET_MODE_MANUAL
from .const import PRESET_MODE_ON
from .const import PRESET_MODE_PARTY
from .const import PRESET_MODE_SLEEP
from .const import DIRECTION_ALTERNATING
from .coordinator import SikuDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku (Blauberg) Fan."""
    LOGGER.debug("Setting up Siku (Blauberg) Fan")
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
    """Siku (Blauberg) Fan."""

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
        PRESET_MODE_MANUAL,
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
        self._attr_unique_id = f"{DOMAIN}-{coordinator.config_entry.entry_id}-fan"

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if (
            self._attr_preset_mode == PRESET_MODE_MANUAL
            or self.coordinator.data["manual_speed_selected"]
        ):
            return 100  # Manual speed supports 1-100
        return len(FAN_SPEEDS)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        LOGGER.debug("Setting percentage to %s", percentage)
        self._attr_percentage = percentage
        if percentage == 0:
            self.set_preset_mode(None)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        LOGGER.debug(
            "Async setting percentage to %s preset mode %s %s",
            percentage,
            self._attr_preset_mode,
            self.coordinator.data["manual_speed_selected"],
        )
        if percentage == 0:
            await self.coordinator.api.power_off()
            if (
                self._attr_preset_mode != PRESET_MODE_MANUAL
                and self.coordinator.data["manual_speed_selected"]
            ):
                await self.hass.async_add_executor_job(self.set_preset_mode, None)
        else:
            await self.coordinator.api.power_on()
            if (
                self.coordinator.data["manual_speed_selected"]
                and self.coordinator.data["manual_speed"]
            ):
                await self.coordinator.api.speed_manual(percentage)
            elif self._attr_preset_mode == PRESET_MODE_MANUAL:
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
            # did any of the preset modes change?
            if (
                self.coordinator.data["manual_speed_selected"]
                or self._attr_preset_mode == PRESET_MODE_MANUAL
            ):
                await self.hass.async_add_executor_job(
                    self.set_preset_mode, PRESET_MODE_MANUAL
                )
            elif self.oscillating:
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
            await self.coordinator.api.direction(DIRECTION_ALTERNATING)
            preset_mode = PRESET_MODE_AUTO
        else:
            await self.coordinator.api.direction(DIRECTION_FORWARD)
            preset_mode = PRESET_MODE_ON
        if self.coordinator.data["manual_speed_selected"]:
            preset_mode = PRESET_MODE_MANUAL
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)
        await self.hass.async_add_executor_job(self.oscillate, oscillating)
        if not oscillating:
            await self.hass.async_add_executor_job(
                self.set_direction, DIRECTIONS[DIRECTION_FORWARD]
            )
        self.async_write_ha_state()

    def set_direction(self, direction: str | None) -> None:
        """Set the direction of the fan.

        direction -- one of the text strings in DIRECTIONS values or None for oscillating
        """
        self._attr_current_direction = direction

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan.

        direction -- one of the text strings in DIRECTIONS values
        """
        # make sure direction is valid and is one of the text strings in DIRECTIONS values
        if not isinstance(direction, str) or direction not in DIRECTIONS.values():
            LOGGER.error(
                "Invalid direction: %s expected one of %s",
                direction,
                list(DIRECTIONS.values()),
            )
            return
        # use the numeric value for the api's direction
        direction_key: str = next(
            (key for key, value in DIRECTIONS.items() if value == direction), ""
        )
        await self.coordinator.api.direction(direction_key)
        await self.hass.async_add_executor_job(self.set_direction, direction)
        if direction != DIRECTIONS[DIRECTION_ALTERNATING]:
            oscillate = False
        else:
            oscillate = True
        await self.hass.async_add_executor_job(self.oscillate, oscillate)
        if self.coordinator.data["manual_speed_selected"]:
            await self.hass.async_add_executor_job(
                self.set_preset_mode, PRESET_MODE_MANUAL
            )
        elif self.coordinator.data["speed"] in FAN_SPEEDS:
            if oscillate:
                await self.hass.async_add_executor_job(
                    self.set_preset_mode, PRESET_MODE_AUTO
                )
            else:
                await self.hass.async_add_executor_job(
                    self.set_preset_mode, PRESET_MODE_ON
                )
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity."""
        LOGGER.debug(
            "Turning on fan with percentage %s and preset mode %s : %s",
            percentage,
            preset_mode,
            kwargs,
        )
        if percentage is None:
            percentage = ordered_list_item_to_percentage(FAN_SPEEDS, FAN_SPEEDS[0])
        await self.async_set_percentage(percentage)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        await self.async_set_percentage(0)
        self.async_write_ha_state()

    def set_preset_mode(self, preset_mode: str | None) -> None:
        """Set the preset mode of the fan."""
        self._attr_preset_mode = preset_mode
        self.schedule_update_ha_state()

    async def async_set_preset_mode(self, preset_mode: str | None) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_MODE_PARTY:
            LOGGER.debug("Setting preset mode to party from %s", self._attr_preset_mode)
            await self.coordinator.api.power_on()
            response = await self.coordinator.api.party()
            if response:
                self.coordinator.async_set_updated_data(response)
        elif preset_mode == PRESET_MODE_SLEEP:
            LOGGER.debug("Setting preset mode to sleep from %s", self._attr_preset_mode)
            await self.coordinator.api.power_on()
            response = await self.coordinator.api.sleep()
            if response:
                self.coordinator.async_set_updated_data(response)
        elif preset_mode == PRESET_MODE_AUTO:
            LOGGER.debug("Setting preset mode to auto from %s", self._attr_preset_mode)
            await self.coordinator.api.power_on()
            response = await self.coordinator.api.speed(FAN_SPEEDS[0])
            if response:
                self.coordinator.async_set_updated_data(response)
            await self.async_oscillate(True)
        elif preset_mode == PRESET_MODE_ON:
            LOGGER.debug("Setting preset mode to on from %s", self._attr_preset_mode)
            await self.coordinator.api.power_on()
            response = await self.coordinator.api.speed(FAN_SPEEDS[0])
            if response:
                self.coordinator.async_set_updated_data(response)
            await self.async_set_direction(DIRECTIONS[DIRECTION_FORWARD])
        elif preset_mode == PRESET_MODE_MANUAL:
            LOGGER.debug(
                "Setting preset mode to manual from %s", self._attr_preset_mode
            )
            await self.coordinator.api.power_on()
            percentage = ordered_list_item_to_percentage(FAN_SPEEDS, FAN_SPEEDS[0])
            response = await self.coordinator.api.speed_manual(percentage)
            if response:
                self.coordinator.async_set_updated_data(response)
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
            LOGGER.debug("Fan is on")
            if self.coordinator.data["manual_speed_selected"]:
                LOGGER.debug(
                    "Setting manual speed from selection %s and speed %s",
                    self.coordinator.data["manual_speed_selected"],
                    self.coordinator.data["manual_speed"],
                )
                self.set_percentage(
                    ranged_value_to_percentage(
                        self.coordinator.data["manual_speed_low_high_range"],
                        self.coordinator.data["manual_speed"],
                    )
                )
                self.set_preset_mode(PRESET_MODE_MANUAL)
            elif self.coordinator.data["speed_list"]:
                LOGGER.debug(
                    "Setting speed preset from speed %s list %s type %s",
                    self.coordinator.data["speed"],
                    self.coordinator.data["speed_list"],
                    type(self.coordinator.data["speed"]),
                )
                self.set_percentage(
                    ordered_list_item_to_percentage(
                        self.coordinator.data["speed_list"],
                        self.coordinator.data["speed"],
                    )
                )
                if (
                    self.coordinator.data["oscillating"]
                    or self.coordinator.data["direction"] is None
                    or self.coordinator.data["direction"]
                    == DIRECTIONS[DIRECTION_ALTERNATING]
                ):
                    self.set_preset_mode(PRESET_MODE_AUTO)
                else:
                    self.set_preset_mode(PRESET_MODE_ON)
            else:
                LOGGER.debug(
                    "Setting speed from speed %s type %s",
                    self.coordinator.data["speed"],
                    type(self.coordinator.data["speed"]),
                )
                self.set_percentage(
                    ordered_list_item_to_percentage(
                        FAN_SPEEDS, self.coordinator.data["speed"]
                    )
                )
                if (
                    self.coordinator.data["oscillating"]
                    or self.coordinator.data["direction"] is None
                    or self.coordinator.data["direction"]
                    == DIRECTIONS[DIRECTION_ALTERNATING]
                ):
                    self.set_preset_mode(PRESET_MODE_AUTO)
                else:
                    self.set_preset_mode(PRESET_MODE_ON)
        else:
            LOGGER.debug("Fan is off")
            self.set_percentage(0)

        if (
            self.coordinator.data["oscillating"]
            or self.coordinator.data["direction"] is None
            or self.coordinator.data["direction"] == DIRECTIONS[DIRECTION_ALTERNATING]
        ):
            self.oscillate(True)
        else:
            self.oscillate(False)
            self.set_direction(self.coordinator.data["direction"])

        super()._handle_coordinator_update()

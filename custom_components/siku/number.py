"""Siku (Blauberg) Fan numbers."""

from __future__ import annotations

from typing import Protocol, cast

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import ranged_value_to_percentage

from . import SikuEntity
from .api_v2 import PRESET_SPEED_COMMANDS, SPEED_PRESET_MAX, SPEED_PRESET_MIN
from .const import DOMAIN
from .coordinator import SikuDataUpdateCoordinator

FILTER_REPLACEMENT_TIMER_SETUP_KEY = "filter_replacement_timer_setup_days"
MANUAL_SPEED_KEY = "manual_speed"

NUMBERS: tuple[NumberEntityDescription, ...] = tuple(
    NumberEntityDescription(
        key=key,
        name=key.replace("_", " ").capitalize(),
        entity_category=EntityCategory.CONFIG,
        native_min_value=SPEED_PRESET_MIN,
        native_max_value=SPEED_PRESET_MAX,
        native_step=1,
        mode=NumberMode.BOX,
    )
    for key in PRESET_SPEED_COMMANDS
)

FILTER_REPLACEMENT_TIMER_NUMBER = NumberEntityDescription(
    key="filter_replacement_timer_setup",
    name="Filter replacement timer setup",
    entity_category=EntityCategory.CONFIG,
    native_min_value=70,
    native_max_value=365,
    native_step=1,
    native_unit_of_measurement=UnitOfTime.DAYS,
    mode=NumberMode.BOX,
)

# Manual speed as a percentage; both v1 and v2 map it onto the raw 0-255 range.
MANUAL_SPEED_NUMBER = NumberEntityDescription(
    key=MANUAL_SPEED_KEY,
    name="Manual speed",
    native_min_value=1,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    mode=NumberMode.SLIDER,
)


class _NumberApiProtocol(Protocol):
    """API surface needed by number entities."""

    async def preset_speed(self, key: str, speed: int) -> dict: ...

    async def filter_replacement_timer_setup(self, days: int) -> dict: ...


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku (Blauberg) Fan numbers."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # Only the v2 protocol reports supply/exhaust speeds.
    data = coordinator.data or {}
    preset_speeds = data.get("preset_speeds", {})

    entities = [
        SikuNumber(coordinator, description)
        for description in NUMBERS
        if description.key in preset_speeds
    ]

    # 0x0063 is optional and should only surface when reported by the fan.
    if FILTER_REPLACEMENT_TIMER_SETUP_KEY in data:
        entities.append(SikuNumber(coordinator, FILTER_REPLACEMENT_TIMER_NUMBER))

    if MANUAL_SPEED_KEY in data:
        entities.append(SikuNumber(coordinator, MANUAL_SPEED_NUMBER))

    async_add_entities(entities, True)


class SikuNumber(SikuEntity, NumberEntity):
    """Representation of a Siku related Number."""

    def __init__(
        self,
        coordinator: SikuDataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator, context=description.key)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.config_entry.entry_id}-{description.key}"
        )

    @property
    def native_value(self) -> float | None:
        """Return the current speed."""
        if self.entity_description.key == FILTER_REPLACEMENT_TIMER_NUMBER.key:
            return self.coordinator.data.get(FILTER_REPLACEMENT_TIMER_SETUP_KEY)
        if self.entity_description.key == MANUAL_SPEED_NUMBER.key:
            return ranged_value_to_percentage(
                self.coordinator.data["manual_speed_low_high_range"],
                self.coordinator.data[MANUAL_SPEED_KEY],
            )
        return self.coordinator.data["preset_speeds"].get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new speed."""
        api = self.coordinator.api
        if self.entity_description.key == MANUAL_SPEED_NUMBER.key:
            # Mirror fan.async_set_percentage: speed_manual also switches the
            # fan into manual mode, but only takes effect while powered on.
            await api.power_on()
            response = await api.speed_manual(int(value))
            self.coordinator.async_set_updated_data(response)
            return
        if not hasattr(api, "preset_speed") or not hasattr(
            api, "filter_replacement_timer_setup"
        ):
            return
        number_api = cast(_NumberApiProtocol, api)

        if self.entity_description.key == FILTER_REPLACEMENT_TIMER_NUMBER.key:
            response = await number_api.filter_replacement_timer_setup(int(value))
        else:
            response = await number_api.preset_speed(
                self.entity_description.key, int(value)
            )
        self.coordinator.async_set_updated_data(response)

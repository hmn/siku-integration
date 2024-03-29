"""Support for MelCloud device sensors."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfTime,
    REVOLUTIONS_PER_MINUTE,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SikuEntity
from .const import DOMAIN
from .coordinator import SikuDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class SikuRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], float]
    enabled: Callable[[Any], bool]


@dataclasses.dataclass(frozen=True)
class SikuSensorEntityDescription(SensorEntityDescription, SikuRequiredKeysMixin):
    """Describes Siku fan sensor entity."""


SENSORS: tuple[SikuSensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="version",
        translation_key="version",
        icon="mdi:information",
        name="Version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rpm",
        name="RPM",
        icon="mdi:rotate-right",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="firmware",
        name="Firmware version",
        icon="mdi:information",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="alarm",
        name="Alarm",
        icon="mdi:alarm-light",
    ),
    SensorEntityDescription(
        key="filter_timer",
        name="Filter timer countdown",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku fan sensors."""
    LOGGER.debug("Setting up Siku fan sensors %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    available_resources: set[str] = {k.lower() for k, _ in coordinator.data.items()}

    entities: list[SikuSensor] = [
        SikuSensor(hass, coordinator, description)
        for description in SENSORS
        if description.key in available_resources
    ]

    async_add_entities(entities, True)


class SikuSensor(SikuEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SikuDataUpdateCoordinator,
        description: SensorEntityDescription,
        # entry: ConfigEntry,
        # unique_id: str,
        # name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator, context=description.key)
        self.hass = hass

        self.entity_description = description
        LOGGER.debug("Sensor description: %s", description)
        LOGGER.debug("Sensor coordinator: %s", coordinator)
        LOGGER.debug("Sensor device: %s", coordinator.device_info)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.api.host}-{coordinator.api.port}-{description.key}"
        )

        # Initial update of attributes.
        # self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        key = self.entity_description.key
        LOGGER.debug("Handling update for %s : %s", key, self.coordinator.data[key])
        self._attr_native_value = self.coordinator.data[key]

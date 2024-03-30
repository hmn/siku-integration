"""Support for MelCloud device sensors."""

from __future__ import annotations

import dataclasses
import logging

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
class SikuSensorEntityDescription(SensorEntityDescription):
    """Describes Siku fan sensor entity."""


SENSORS: tuple[SikuSensorEntityDescription, ...] = (
    SikuSensorEntityDescription(
        key="version",
        translation_key="version",
        icon="mdi:information",
        name="Version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SikuSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SikuSensorEntityDescription(
        key="rpm",
        name="RPM",
        icon="mdi:rotate-right",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SikuSensorEntityDescription(
        key="firmware",
        name="Firmware version",
        icon="mdi:information",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SikuSensorEntityDescription(
        key="alarm",
        name="Alarm",
        icon="mdi:alarm-light",
    ),
    SikuSensorEntityDescription(
        key="filter_timer",
        name="Filter timer countdown",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SikuSensorEntityDescription(
        key="boost",
        name="Boost mode",
        icon="msi:speedometer",
    ),
    SikuSensorEntityDescription(
        key="mode",
        name="Mode",
        icon="mdi:fan-auto",
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
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator, context=description.key)
        self.hass = hass

        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.api.host}-{coordinator.api.port}-{description.key}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        key = self.entity_description.key
        self._attr_native_value = self.coordinator.data[key]
        LOGGER.debug("Native value [%s]: %s", key, self._attr_native_value)

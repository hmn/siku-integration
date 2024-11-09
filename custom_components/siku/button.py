"""Siku fan buttons."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SikuEntity
from .const import DOMAIN
from .coordinator import SikuDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SikuButtonEntityDescription(ButtonEntityDescription):
    """Describes Siku fan button entity."""

    action: str


BUTTONS = [
    SikuButtonEntityDescription(
        key="reset_filter_alarm",
        name="Reset filter alarm",
        icon="mdi:alarm-light",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        action="reset_filter_alarm",
    ),
    SikuButtonEntityDescription(
        key="party",
        name="Party mode",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        action="party",
    ),
    SikuButtonEntityDescription(
        key="sleep",
        name="Sleep mode",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        action="sleep",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Siku fan buttons."""
    LOGGER.debug("Setting up Siku fan buttons %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SikuButton] = [
        SikuButton(hass, coordinator, description) for description in BUTTONS
    ]

    async_add_entities(entities, True)


class SikuButton(SikuEntity, ButtonEntity):
    """Representation of a Siku related Button."""

    entity_description: SikuButtonEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SikuDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator, context=description.key)
        self.hass = hass
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{DOMAIN}-{coordinator.api.host}-{coordinator.api.port}-{description.key}-button"
        LOGGER.debug("Add Siku button entity %s", self._attr_unique_id)

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        try:
            method = getattr(self.coordinator.api, self.entity_description.action)
            await method()
            self.async_write_ha_state()
        except AttributeError:
            LOGGER.warning("No such method: %s", self.entity_description.action)

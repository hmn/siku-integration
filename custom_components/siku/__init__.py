"""The Siku (Blauberg) Fan integration."""

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, DEFAULT_NAME
from .coordinator import SikuDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR, Platform.BUTTON]


def _legacy_entity_unique_id_to_stable(
    *, entry_id: str, legacy_unique_id: str
) -> str | None:
    """Convert legacy host:port-based unique_id to stable entry_id-based unique_id."""
    if not legacy_unique_id.startswith(f"{DOMAIN}-"):
        return None

    parts = legacy_unique_id.split("-")
    # Legacy formats:
    # - fan: siku-<host>-<port>-fan
    # - sensor: siku-<host>-<port>-<key>
    # - button: siku-<host>-<port>-<key>-button
    if len(parts) < 4:
        return None

    if parts[-1] == "fan":
        return f"{DOMAIN}-{entry_id}-fan"

    if parts[-1] == "button" and len(parts) >= 5:
        key = parts[-2]
        return f"{DOMAIN}-{entry_id}-{key}-button"

    key = parts[-1]
    return f"{DOMAIN}-{entry_id}-{key}"


async def _async_migrate_registries(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate legacy device/entity registry identifiers after IP/port reconfigure.

    Problem being fixed:
    - Device identifiers were based on IP:port, so changing IP created a *new* device
      ("unit") and left the old one behind.
    - Entity unique_ids were also based on IP:port, so changing IP created *new*
      entities and left the old ones orphaned.

    Fix:
    - Use stable identifiers (config entry id) going forward.
    - On setup, migrate existing registry entries and remove duplicates.
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    stable_device_identifier = (DOMAIN, entry.entry_id)

    # Find all devices linked to this config entry; if there are multiple, merge.
    linked_devices = [
        device
        for device in dev_reg.devices.values()
        if entry.entry_id in device.config_entries
    ]

    canonical_device = next(
        (d for d in linked_devices if stable_device_identifier in d.identifiers),
        linked_devices[0] if linked_devices else None,
    )

    canonical_device_id: str | None = None
    if canonical_device is not None:
        canonical_device_id = canonical_device.id
        new_identifiers = set(canonical_device.identifiers)
        new_identifiers.add(stable_device_identifier)
        dev_reg.async_update_device(
            canonical_device_id,
            new_identifiers=new_identifiers,
        )

    # Migrate entities:
    # - Move legacy host:port unique_ids to stable entry_id unique_ids.
    # - Re-point entities to the canonical device.
    entries_for_config = [
        e for e in ent_reg.entities.values() if e.config_entry_id == entry.entry_id
    ]
    for e in entries_for_config:
        if not e.unique_id:
            continue

        target_unique_id = _legacy_entity_unique_id_to_stable(
            entry_id=entry.entry_id,
            legacy_unique_id=e.unique_id,
        )
        if not target_unique_id or target_unique_id == e.unique_id:
            # Still re-link device_id if we already have a canonical device.
            if canonical_device_id is not None and e.device_id != canonical_device_id:
                ent_reg.async_update_entity(e.entity_id, device_id=canonical_device_id)
            continue

        # If a duplicate entity with the target unique_id exists (created after IP
        # change), remove it and keep the original entity_id.
        dup = next(
            (
                other
                for other in ent_reg.entities.values()
                if other.config_entry_id == entry.entry_id
                and other.unique_id == target_unique_id
                and other.entity_id != e.entity_id
            ),
            None,
        )
        if dup is not None:
            ent_reg.async_remove(dup.entity_id)

        ent_reg.async_update_entity(
            e.entity_id,
            new_unique_id=target_unique_id,
            device_id=canonical_device_id
            if canonical_device_id is not None
            else e.device_id,
        )

    # If multiple devices exist, re-point any entities and remove the extra devices.
    if canonical_device_id is not None and len(linked_devices) > 1:
        for device in linked_devices:
            if device.id == canonical_device_id:
                continue
            # Re-point entities that still reference the duplicate device.
            for e in ent_reg.entities.values():
                if e.device_id == device.id:
                    ent_reg.async_update_entity(
                        e.entity_id, device_id=canonical_device_id
                    )
            dev_reg.async_remove_device(device.id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Siku (Blauberg) Fan from a config entry."""

    coordinator = SikuDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await _async_migrate_registries(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}

        if config_entry.minor_version < 1:
            host = config_entry.data[CONF_IP_ADDRESS]
            port = config_entry.data[CONF_PORT]
            unique_id = f"{host}:{port}"
            fix_names = [
                f"{DOMAIN} {host}:{port}",
                f"{DEFAULT_NAME} {host}:{port}",
                f"{DOMAIN} {host}",
                f"{host}:{port}",
            ]
            if config_entry.title in fix_names:
                title = f"{DEFAULT_NAME} {host}"
            else:
                title = config_entry.title
            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                unique_id=unique_id,
                title=title,
                version=1,
                minor_version=1,
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


class SikuEntity(CoordinatorEntity[SikuDataUpdateCoordinator]):
    """Representation of a siku entity."""

"""Tests for SikuNumber entity."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
import custom_components.siku.number as number

# ruff: noqa: D103


def _coordinator(preset_speeds):
    coordinator = MagicMock()
    coordinator.data = {"preset_speeds": preset_speeds}
    coordinator.api.preset_speed = AsyncMock(return_value={"preset_speeds": {}})
    return coordinator


async def _setup(coordinator):
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    hass.data = {number.DOMAIN: {entry.entry_id: coordinator}}
    async_add_entities = Mock()

    await number.async_setup_entry(hass, entry, async_add_entities)
    return async_add_entities.call_args[0][0]


@pytest.mark.asyncio
async def test_async_setup_entry_adds_reported_speeds_only():
    """Parameters the fan did not answer, and v1 fans, get no entity."""
    entities = await _setup(_coordinator({"supply_speed_1": 51}))

    assert [entity.entity_description.key for entity in entities] == ["supply_speed_1"]
    assert isinstance(entities[0], number.SikuNumber)

    coordinator = MagicMock()
    coordinator.data = None
    assert await _setup(coordinator) == []


@pytest.mark.asyncio
async def test_native_value_and_set():
    coordinator = _coordinator({"exhaust_speed_2": 64})
    entity = (await _setup(coordinator))[0]

    assert entity.native_value == 64

    await entity.async_set_native_value(70.0)

    coordinator.api.preset_speed.assert_awaited_once_with("exhaust_speed_2", 70)
    coordinator.async_set_updated_data.assert_called_once_with({"preset_speeds": {}})

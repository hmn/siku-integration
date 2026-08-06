"""Tests for SikuSensor entity."""

import pytest
from unittest.mock import MagicMock, Mock

import custom_components.siku.sensor as sensor


# ruff: noqa: D103


async def _setup(coordinator):
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    hass.data = {sensor.DOMAIN: {entry.entry_id: coordinator}}
    async_add_entities = Mock()

    await sensor.async_setup_entry(hass, entry, async_add_entities)
    return async_add_entities.call_args[0][0]


@pytest.mark.asyncio
async def test_async_setup_entry_adds_optional_status_sensors_when_reported():
    coordinator = MagicMock()
    coordinator.data = {
        "version": "2",
        "humidity_sensor_status": "over setpoint",
        "zero_ten_v_sensor_status": "below setpoint",
    }

    entities = await _setup(coordinator)
    keys = {entity.entity_description.key for entity in entities}

    assert "humidity_sensor_status" in keys
    assert "zero_ten_v_sensor_status" in keys


@pytest.mark.asyncio
async def test_async_setup_entry_skips_optional_status_sensors_when_absent():
    coordinator = MagicMock()
    coordinator.data = {"version": "2"}

    entities = await _setup(coordinator)
    keys = {entity.entity_description.key for entity in entities}

    assert "humidity_sensor_status" not in keys
    assert "zero_ten_v_sensor_status" not in keys

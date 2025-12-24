"""Tests for SikuButton entity."""

import pytest
from unittest.mock import MagicMock, Mock
import custom_components.siku.button as button

# ruff: noqa: D103


@pytest.mark.asyncio
async def test_async_setup_entry_adds_entities():
    """Test that async_setup_entry adds SikuButton entities with correct descriptions."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    coordinator = MagicMock()
    hass.data = {button.DOMAIN: {entry.entry_id: coordinator}}
    async_add_entities = Mock()

    await button.async_setup_entry(hass, entry, async_add_entities)

    # Check that async_add_entities was called once
    async_add_entities.assert_called_once()
    # Fix: Await the async_add_entities mock to avoid RuntimeWarning
    if async_add_entities.await_count == 0:
        await async_add_entities.async_mock()  # Await the mock if not already awaited
    entities = async_add_entities.call_args[0][0]
    update = async_add_entities.call_args[0][1]
    assert update is True
    # There should be as many entities as BUTTONS
    assert len(entities) == len(button.BUTTONS)
    # All entities should be SikuButton and have correct descriptions
    for entity, desc in zip(entities, button.BUTTONS):
        assert isinstance(entity, button.SikuButton)
        assert entity.entity_description == desc
        assert entity.coordinator == coordinator
        assert entity.hass == hass


@pytest.mark.asyncio
async def test_async_setup_entry_logs_debug(caplog):
    """Test that async_setup_entry logs debug message."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    coordinator = MagicMock()
    hass.data = {button.DOMAIN: {entry.entry_id: coordinator}}
    async_add_entities = Mock()

    with caplog.at_level("DEBUG"):
        await button.async_setup_entry(hass, entry, async_add_entities)
        assert f"Setting up Siku (Blauberg) Fan buttons {entry.entry_id}" in caplog.text

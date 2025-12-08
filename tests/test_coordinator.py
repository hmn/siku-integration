"""Tests for the Siku Data Update Coordinator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.siku.coordinator import SikuDataUpdateCoordinator
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.siku.const import (
    CONF_ID,
    CONF_VERSION,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    DEFAULT_MANUFACTURER,
)

# ruff: noqa: D103


@pytest.fixture
def mock_hass():
    return MagicMock()


@pytest.fixture
def config_entry_v1():
    entry = MagicMock()
    entry.data = {
        CONF_IP_ADDRESS: "192.168.1.10",
        CONF_PORT: 1234,
        CONF_VERSION: 1,
    }
    return entry


@pytest.fixture
def config_entry_v2():
    entry = MagicMock()
    entry.data = {
        CONF_IP_ADDRESS: "192.168.1.20",
        CONF_PORT: 5678,
        CONF_VERSION: 2,
        CONF_ID: "1234567890ABCDEF",
        CONF_PASSWORD: "12345678",
    }
    return entry


@patch("custom_components.siku.coordinator.SikuV1Api")
def test_coordinator_init_v1(mock_v1api, mock_hass, config_entry_v1):
    coordinator = SikuDataUpdateCoordinator(mock_hass, config_entry_v1)
    mock_v1api.assert_called_once_with("192.168.1.10", 1234)
    assert coordinator.name == f"{DEFAULT_NAME} 192.168.1.10"
    assert coordinator.api == mock_v1api.return_value


@patch("custom_components.siku.coordinator.SikuV2Api")
def test_coordinator_init_v2(mock_v2api, mock_hass, config_entry_v2):
    coordinator = SikuDataUpdateCoordinator(mock_hass, config_entry_v2)
    mock_v2api.assert_called_once_with(
        "192.168.1.20", 5678, "1234567890ABCDEF", "12345678"
    )
    assert coordinator.name == f"{DEFAULT_NAME} 192.168.1.20"
    assert coordinator.api == mock_v2api.return_value


@patch("custom_components.siku.coordinator.SikuV1Api")
def test_device_info_v1(mock_v1api, mock_hass, config_entry_v1):
    mock_api = MagicMock()
    mock_api.host = "192.168.1.10"
    mock_api.port = 1234
    mock_v1api.return_value = mock_api
    coordinator = SikuDataUpdateCoordinator(mock_hass, config_entry_v1)
    info = coordinator.device_info
    assert info.get("identifiers") == {(DOMAIN, "192.168.1.10:1234")}
    assert info.get("model") == DEFAULT_MODEL
    assert info.get("manufacturer") == DEFAULT_MANUFACTURER
    assert info.get("name") == f"{DEFAULT_NAME} 192.168.1.10"


@pytest.mark.asyncio
@patch("custom_components.siku.coordinator.SikuV1Api")
async def test_update_method_success(mock_v1api, mock_hass, config_entry_v1):
    mock_api = MagicMock()
    mock_api.status = AsyncMock(return_value={"is_on": True, "speed": "01"})
    mock_v1api.return_value = mock_api
    coordinator = SikuDataUpdateCoordinator(mock_hass, config_entry_v1)
    data = await coordinator._update_method()
    assert data == {"is_on": True, "speed": "01"}


@pytest.mark.asyncio
@patch("custom_components.siku.coordinator.SikuV1Api")
async def test_update_method_failure(mock_v1api, mock_hass, config_entry_v1):
    mock_api = MagicMock()
    mock_api.host = "192.168.1.100"
    mock_api.port = 4000
    mock_api.status = AsyncMock(side_effect=TimeoutError("timeout"))
    mock_v1api.return_value = mock_api
    coordinator = SikuDataUpdateCoordinator(mock_hass, config_entry_v1)
    with pytest.raises(UpdateFailed) as exc:
        await coordinator._update_method()
    assert "Timeout connecting to Siku Fan" in str(exc.value)

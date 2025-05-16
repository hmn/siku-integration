"""Test the Siku Integration config flow."""

import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from custom_components.siku.const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_NAME,
    CONF_ID,
    CONF_VERSION,
)


"""Test the Siku Integration config flow."""


IP_ADDRESS = "192.168.1.100"
PORT = DEFAULT_PORT
IDNUM = "1234567890abcdef"
PASSWORD = "pass1234"


@pytest.mark.asyncio
async def test_show_user_form(hass: HomeAssistant):
    """Test that the user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_create_entry_v1(hass: HomeAssistant):
    """Test creating an entry for API v1."""
    user_input = {
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_PORT: PORT,
        CONF_VERSION: 1,
    }
    with patch("custom_components.siku.config_flow.SikuV1Api") as mock_api:
        mock_api.return_value.status = AsyncMock(return_value=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} {IP_ADDRESS}"
    assert result["data"] == user_input


@pytest.mark.asyncio
async def test_create_entry_v2(hass: HomeAssistant):
    """Test creating an entry for API v2."""
    user_input = {
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_PORT: PORT,
        CONF_VERSION: 2,
        CONF_ID: IDNUM,
        CONF_PASSWORD: PASSWORD,
    }
    with patch("custom_components.siku.config_flow.SikuV2Api") as mock_api:
        mock_api.return_value.status = AsyncMock(return_value=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} {IP_ADDRESS}"
    assert result["data"] == user_input


@pytest.mark.asyncio
async def test_invalid_idnum_length(hass: HomeAssistant):
    """Test error when idnum is not 16 chars."""
    user_input = {
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_PORT: PORT,
        CONF_VERSION: 2,
        CONF_ID: "shortid",
        CONF_PASSWORD: PASSWORD,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=user_input
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_idnum"


@pytest.mark.asyncio
async def test_invalid_password_length(hass: HomeAssistant):
    """Test error when password is too long."""
    user_input = {
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_PORT: PORT,
        CONF_VERSION: 2,
        CONF_ID: IDNUM,
        CONF_PASSWORD: "toolongpassword",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=user_input
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_password"
    assert result["errors"]["password"] == "invalid_password"


@pytest.mark.asyncio
async def test_cannot_connect(hass: HomeAssistant):
    """Test cannot connect error."""
    user_input = {
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_PORT: PORT,
        CONF_VERSION: 1,
    }
    with patch("custom_components.siku.config_flow.SikuV1Api") as mock_api:
        mock_api.return_value.status = AsyncMock(return_value=False)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_unknown_exception(hass: HomeAssistant):
    """Test unknown exception handling."""
    user_input = {
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_PORT: PORT,
        CONF_VERSION: 1,
    }
    with patch("custom_components.siku.config_flow.SikuV1Api") as mock_api:
        mock_api.return_value.status = AsyncMock(side_effect=Exception("fail"))
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"

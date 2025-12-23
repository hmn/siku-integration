"""Test the Siku Integration config flow."""

import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.siku.const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_NAME,
    CONF_ID,
    CONF_VERSION,
)

# ruff: noqa: D103

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
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"


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
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"{DEFAULT_NAME} {IP_ADDRESS}"
    assert result.get("data") == user_input


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
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"{DEFAULT_NAME} {IP_ADDRESS}"
    assert result.get("data") == user_input


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
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert errors.get("base") == "invalid_idnum"


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
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert errors.get("base") == "invalid_password"
    assert errors.get("password") == "invalid_password"


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
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert errors.get("base") == "cannot_connect"


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
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert errors.get("base") == "unknown"


@pytest.mark.asyncio
async def test_reconfigure_form_prefills_existing_entry(hass: HomeAssistant):
    """Test reconfigure form is prefilled from the existing config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{DEFAULT_NAME} {IP_ADDRESS}",
        data={
            CONF_IP_ADDRESS: IP_ADDRESS,
            CONF_PORT: PORT,
            CONF_VERSION: 1,
        },
        unique_id=f"{IP_ADDRESS}:{PORT}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reconfigure_confirm"

    schema = result.get("data_schema")
    assert schema is not None
    marker_to_suggested = {
        marker.schema: (getattr(marker, "description", None) or {}).get(
            "suggested_value"
        )
        for marker in schema.schema
    }
    assert marker_to_suggested.get(CONF_IP_ADDRESS) == IP_ADDRESS
    assert marker_to_suggested.get(CONF_PORT) == PORT
    assert marker_to_suggested.get(CONF_VERSION) == 1


@pytest.mark.asyncio
async def test_reconfigure_updates_entry_and_migrates_unique_id(hass: HomeAssistant):
    """Test reconfigure updates the entry and migrates unique_id when host/port changes."""
    old_ip = IP_ADDRESS
    old_port = PORT
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{DEFAULT_NAME} {old_ip}",
        data={
            CONF_IP_ADDRESS: old_ip,
            CONF_PORT: old_port,
            CONF_VERSION: 1,
        },
        unique_id=f"{old_ip}:{old_port}",
    )
    entry.add_to_hass(hass)

    new_ip = "192.168.1.101"
    new_port = 4001
    user_input = {
        CONF_IP_ADDRESS: new_ip,
        CONF_PORT: new_port,
        CONF_VERSION: 1,
    }

    with patch("custom_components.siku.config_flow.SikuV1Api") as mock_api:
        mock_api.return_value.status = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        assert result.get("type") == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result2.get("type") == FlowResultType.ABORT
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_IP_ADDRESS] == new_ip
    assert updated_entry.data[CONF_PORT] == new_port
    assert updated_entry.unique_id == f"{new_ip}:{new_port}"

"""Config flow for Siku Fan integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api_v1 import SikuV1Api
from .api_v2 import SikuV2Api
from .const import CONF_ID
from .const import CONF_VERSION
from .const import DEFAULT_PORT
from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_VERSION, default=2): vol.In([1, 2]),
        vol.Optional(CONF_ID): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)

LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    if data[CONF_VERSION] == 1:
        api = SikuV1Api(data[CONF_IP_ADDRESS], data[CONF_PORT])
    else:
        api = SikuV2Api(
            data[CONF_IP_ADDRESS], data[CONF_PORT], data[CONF_ID], data[CONF_PASSWORD]
        )
    if not await api.status():
        raise CannotConnect

    # Return info that you want to store in the config entry.
    title = f"{data[CONF_IP_ADDRESS]}:{data[CONF_PORT]}"
    return {"title": title}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siku Fan."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        try:
            info = await validate_input(self.hass, user_input)
        except (ValueError, KeyError):
            errors["base"] = "value_error"
        except TimeoutError:
            errors["base"] = "timeout_error"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

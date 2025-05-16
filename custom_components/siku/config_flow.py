"""Config flow for Siku Fan integration."""

from __future__ import annotations

import logging
from typing import Any
from collections.abc import Mapping

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api_v1 import SikuV1Api
from .api_v2 import SikuV2Api
from .const import CONF_ID, CONF_VERSION, DEFAULT_PORT, DOMAIN, DEFAULT_NAME

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_VERSION, default=2): vol.In([1, 2]),
        vol.Optional(CONF_ID): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)

LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect.

    Data has the keys from USER_SCHEMA with values provided by the user.
    """
    if data[CONF_VERSION] == 1:
        api = SikuV1Api(data[CONF_IP_ADDRESS], data[CONF_PORT])
    elif data[CONF_VERSION] == 2:
        if CONF_ID not in data or CONF_PASSWORD not in data:
            raise ValueError("Invalid input")
        if len(data[CONF_ID]) != 16:
            raise InvalidInputFanId("Invalid idnum length must be 16 chars")
        if len(data[CONF_PASSWORD]) > 8:
            raise InvalidInputPassword("Invalid password max length 8 chars")
        api = SikuV2Api(
            data[CONF_IP_ADDRESS], data[CONF_PORT], data[CONF_ID], data[CONF_PASSWORD]
        )
    else:
        raise ValueError("Invalid API version")
    if not await api.status():
        raise CannotConnect


class SikuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siku Fan."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_IP_ADDRESS]
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                await validate_input(self.hass, user_input)
                title = f"{DEFAULT_NAME} {host}"
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )
            except (ValueError, KeyError):
                errors["base"] = "value_error"
            except TimeoutError:
                errors["base"] = "timeout_error"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidInputFanId:
                errors["base"] = "invalid_idnum"
            except InvalidInputPassword:
                errors["base"] = "invalid_password"
                errors["password"] = "invalid_password"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_user(dict(entry_data))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle integration reconfiguration."""
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle integration reconfiguration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except (ValueError, KeyError):
                errors["base"] = "value_error"
            except TimeoutError:
                errors["base"] = "timeout_error"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidInputFanId:
                errors["base"] = "invalid_idnum"
            except InvalidInputPassword:
                errors["base"] = "invalid_password"
                errors["password"] = "invalid_password"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                host = user_input[CONF_IP_ADDRESS]
                port = user_input[CONF_PORT]
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                # Find the existing entry to update
                entry = next(
                    (
                        e
                        for e in self._async_current_entries()
                        if e.unique_id == f"{host}:{port}"
                    ),
                    None,
                )
                if entry is None:
                    errors["base"] = "entry_not_found"
                else:
                    return self.async_update_reload_and_abort(
                        entry=entry,
                        title=f"{DEFAULT_NAME} {host}",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidInputFanId(HomeAssistantError):
    """Error to indicate there is invalid fan id defined."""


class InvalidInputPassword(HomeAssistantError):
    """Error to indicate there is invalid fan password defined."""

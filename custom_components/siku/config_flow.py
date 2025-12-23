"""Config flow for Siku Fan integration."""

from __future__ import annotations

import logging
from typing import Any
from collections.abc import Mapping

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
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
            raise InvalidInputV2Required(
                "Invalid input, idnum and password required for v2"
            )
        if len(data[CONF_ID]) != 16:
            raise InvalidInputFanId("Invalid idnum length must be 16 chars")
        if len(data[CONF_PASSWORD]) > 8:
            raise InvalidInputPassword("Invalid password max length 8 chars")
        api = SikuV2Api(
            data[CONF_IP_ADDRESS], data[CONF_PORT], data[CONF_ID], data[CONF_PASSWORD]
        )
    else:
        raise ValueError("Invalid API version")

    try:
        if not await api.status():
            raise CannotConnect
    except (ConnectionRefusedError, OSError) as err:
        raise CannotConnect from err


class SikuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siku Fan."""

    VERSION = 1
    MINOR_VERSION = 1

    _reconfigure_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
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
            except (ValueError, KeyError) as exc:
                errors["base"] = "value_error"
                description_placeholders = {"exception": f"{str(exc)}"}
            except TimeoutError as exc:
                errors["base"] = "timeout_error"
                errors["ip_address"] = "invalid"
                errors["port"] = "invalid"
                description_placeholders = {"exception": f"{str(exc)}"}
            except CannotConnect as exc:
                errors["base"] = "cannot_connect"
                errors["ip_address"] = "invalid"
                errors["port"] = "invalid"
                description_placeholders = {"exception": f"{str(exc)}"}
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                errors["idnum"] = "invalid_idnum"
                errors["password"] = "invalid_password"
            except InvalidInputV2Required:
                errors["base"] = "invalid_v2_required"
                errors["idnum"] = "invalid_idnum"
                errors["password"] = "invalid_password"
            except InvalidInputFanId:
                errors["base"] = "invalid_idnum"
                errors["idnum"] = "invalid_idnum"
            except InvalidInputPassword:
                errors["base"] = "invalid_password"
                errors["password"] = "invalid_password"
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Unexpected exception during reconfiguration, {str(exc)}"
                )
                errors["base"] = "unknown"
                description_placeholders = {"exception": f"{str(exc)}"}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
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
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="entry_not_found")

        self._reconfigure_entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle integration reconfiguration."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        entry = self._reconfigure_entry
        if entry is None:
            entry_id = self.context.get("entry_id")
            if entry_id is not None:
                entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        suggested_values = dict(entry.data)
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except (ValueError, KeyError) as exc:
                errors["base"] = "value_error"
                description_placeholders = {"exception": f"{str(exc)}"}
            except TimeoutError as exc:
                errors["base"] = "timeout_error"
                errors["ip_address"] = "invalid"
                errors["port"] = "invalid"
                description_placeholders = {"exception": f"{str(exc)}"}
            except CannotConnect as exc:
                errors["base"] = "cannot_connect"
                errors["ip_address"] = "invalid"
                errors["port"] = "invalid"
                description_placeholders = {"exception": f"{str(exc)}"}
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                errors["idnum"] = "invalid_idnum"
                errors["password"] = "invalid_password"
            except InvalidInputV2Required:
                errors["base"] = "invalid_v2_required"
                errors["idnum"] = "invalid_idnum"
                errors["password"] = "invalid_password"
            except InvalidInputFanId:
                errors["base"] = "invalid_idnum"
                errors["idnum"] = "invalid_idnum"
            except InvalidInputPassword:
                errors["base"] = "invalid_password"
                errors["password"] = "invalid_password"
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception(
                    f"Unexpected exception during reconfiguration, {str(exc)}"
                )
                errors["base"] = "unknown"
                description_placeholders = {"exception": f"{str(exc)}"}
            else:
                host = user_input[CONF_IP_ADDRESS]
                port = user_input[CONF_PORT]

                old_unique_id = entry.unique_id
                if not old_unique_id:
                    old_unique_id = (
                        f"{entry.data.get(CONF_IP_ADDRESS)}:{entry.data.get(CONF_PORT)}"
                    )

                new_unique_id = f"{host}:{port}"

                # Prevent collisions with other entries.
                other_entry = next(
                    (
                        e
                        for e in self._async_current_entries()
                        if e.unique_id == new_unique_id and e.entry_id != entry.entry_id
                    ),
                    None,
                )
                if other_entry is not None:
                    errors["base"] = "already_configured"
                    errors["ip_address"] = "invalid"
                    errors["port"] = "invalid"
                    description_placeholders = {"unique_id": new_unique_id}
                else:
                    # If unique_id is host:port, migrate it when user changes host/port.
                    if new_unique_id != old_unique_id:
                        self.hass.config_entries.async_update_entry(
                            entry,
                            unique_id=new_unique_id,
                        )

                    return self.async_update_reload_and_abort(
                        entry=entry,
                        title=f"{DEFAULT_NAME} {host}",
                        data=user_input,
                    )

            suggested_values = user_input

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, suggested_values
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidInputFanId(HomeAssistantError):
    """Error to indicate there is invalid fan id defined."""


class InvalidInputPassword(HomeAssistantError):
    """Error to indicate there is invalid fan password defined."""


class InvalidInputV2Required(HomeAssistantError):
    """Error to indicate v2 input is required."""

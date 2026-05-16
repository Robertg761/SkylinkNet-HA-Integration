"""Config flow for SkylinkNet."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DEFAULT_DEVICE_CLASS,
    CONF_HUB_ID,
    CONF_HUB_KEY,
    DEFAULT_DEVICE_CLASS,
    DEVICE_CLASS_NONE,
    DOMAIN,
)
from .hub import SkylinkNetAuthError, SkylinkNetConnectionError, SkylinkNetHub

DEVICE_CLASS_OPTIONS = [
    DEVICE_CLASS_NONE,
    BinarySensorDeviceClass.MOTION.value,
    BinarySensorDeviceClass.OPENING.value,
    BinarySensorDeviceClass.DOOR.value,
    BinarySensorDeviceClass.WINDOW.value,
    BinarySensorDeviceClass.MOISTURE.value,
]


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input by connecting to the cloud WebSocket."""
    hub = SkylinkNetHub(
        hub_id=data[CONF_HUB_ID],
        hub_key=data[CONF_HUB_KEY],
        session=async_get_clientsession(hass),
    )
    await hub.async_validate()


class SkylinkNetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SkylinkNet config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HUB_ID])
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, user_input)
            except SkylinkNetAuthError:
                errors["base"] = "invalid_auth"
            except SkylinkNetConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                options = {
                    CONF_DEFAULT_DEVICE_CLASS: user_input.get(
                        CONF_DEFAULT_DEVICE_CLASS, DEFAULT_DEVICE_CLASS
                    )
                }
                return self.async_create_entry(
                    title=f"SkylinkNet {user_input[CONF_HUB_ID]}",
                    data={
                        CONF_HUB_ID: user_input[CONF_HUB_ID],
                        CONF_HUB_KEY: user_input[CONF_HUB_KEY],
                    },
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return SkylinkNetOptionsFlow(config_entry)


class SkylinkNetOptionsFlow(config_entries.OptionsFlow):
    """Handle SkylinkNet options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEFAULT_DEVICE_CLASS,
                        default=self._config_entry.options.get(
                            CONF_DEFAULT_DEVICE_CLASS, DEFAULT_DEVICE_CLASS
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=DEVICE_CLASS_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )


def _data_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    values = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_HUB_ID, default=values.get(CONF_HUB_ID, "")): TextSelector(),
            vol.Required(CONF_HUB_KEY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_DEFAULT_DEVICE_CLASS,
                default=values.get(CONF_DEFAULT_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=DEVICE_CLASS_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )

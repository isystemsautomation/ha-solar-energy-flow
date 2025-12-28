from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_SETPOINT_ENTITY,
    CONF_OUTPUT_ENTITY,
    CONF_ENABLED,
    CONF_KP,
    CONF_KI,
    CONF_KD,
    CONF_MIN_OUTPUT,
    CONF_MAX_OUTPUT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_ENABLED,
    DEFAULT_KP,
    DEFAULT_KI,
    DEFAULT_KD,
    DEFAULT_MIN_OUTPUT,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_UPDATE_INTERVAL,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_PROCESS_VALUE_ENTITY): str,
                vol.Required(CONF_SETPOINT_ENTITY): str,
                vol.Required(CONF_OUTPUT_ENTITY): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SolarEnergyFlowOptionsFlowHandler(config_entry)


class SolarEnergyFlowOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow (PID tuning) shown when user clicks Configure."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # config_entry is read-only in your HA version
        self._config_entry = config_entry

    @staticmethod
    def _validate_output_range(data: dict) -> dict:
        min_out = data.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT)
        max_out = data.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT)
        if min_out > max_out:
            raise vol.Invalid("min_output must be less than or equal to max_output")
        return data

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        o = self._config_entry.options
        default_min_output = o.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT)
        default_max_output = o.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT)
        if default_max_output < default_min_output:
            default_max_output = default_min_output
        default_interval = max(o.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL), 1)

        schema = vol.All(
            vol.Schema(
                {
                    vol.Optional(CONF_ENABLED, default=o.get(CONF_ENABLED, DEFAULT_ENABLED)): bool,
                    vol.Optional(CONF_KP, default=o.get(CONF_KP, DEFAULT_KP)): vol.Coerce(float),
                    vol.Optional(CONF_KI, default=o.get(CONF_KI, DEFAULT_KI)): vol.Coerce(float),
                    vol.Optional(CONF_KD, default=o.get(CONF_KD, DEFAULT_KD)): vol.Coerce(float),
                    vol.Optional(CONF_MIN_OUTPUT, default=default_min_output): vol.Coerce(float),
                    vol.Optional(CONF_MAX_OUTPUT, default=default_max_output): vol.Coerce(float),
                    vol.Optional(CONF_UPDATE_INTERVAL, default=default_interval): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            self._validate_output_range,
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

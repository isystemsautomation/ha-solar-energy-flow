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
    DEFAULT_ENABLED,
    DEFAULT_KP,
    DEFAULT_KI,
    DEFAULT_KD,
    DEFAULT_MIN_OUTPUT,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_UPDATE_INTERVAL,
    CONF_INVERT_PV,
    CONF_INVERT_SP,
    CONF_PID_MODE,
    DEFAULT_INVERT_PV,
    DEFAULT_INVERT_SP,
    DEFAULT_PID_MODE,
    PID_MODE_DIRECT,
    PID_MODE_REVERSE,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            unique_id = f"{user_input[CONF_PROCESS_VALUE_ENTITY]}::{user_input[CONF_SETPOINT_ENTITY]}::{user_input[CONF_OUTPUT_ENTITY]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
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
    """Options flow for wiring and PID behavior shown when user clicks Configure."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # config_entry is read-only in your HA version
        self._config_entry = config_entry

    @staticmethod
    def _coerce_int(value, default, min_value=1):
        try:
            int_val = int(value)
        except (TypeError, ValueError):
            return default
        return max(min_value, int_val)

    @staticmethod
    def _normalize_pid_mode(value: str | None) -> str:
        if value in (PID_MODE_DIRECT, PID_MODE_REVERSE):
            return value
        return DEFAULT_PID_MODE

    @staticmethod
    def _build_schema(defaults: dict) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_PROCESS_VALUE_ENTITY, default=defaults[CONF_PROCESS_VALUE_ENTITY]): str,
                vol.Required(CONF_SETPOINT_ENTITY, default=defaults[CONF_SETPOINT_ENTITY]): str,
                vol.Required(CONF_OUTPUT_ENTITY, default=defaults[CONF_OUTPUT_ENTITY]): str,
                vol.Optional(CONF_INVERT_PV, default=defaults.get(CONF_INVERT_PV, DEFAULT_INVERT_PV)): bool,
                vol.Optional(CONF_INVERT_SP, default=defaults.get(CONF_INVERT_SP, DEFAULT_INVERT_SP)): bool,
                vol.Optional(
                    CONF_PID_MODE,
                    default=defaults.get(CONF_PID_MODE, DEFAULT_PID_MODE),
                ): vol.In([PID_MODE_DIRECT, PID_MODE_REVERSE]),
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

    async def async_step_init(self, user_input=None):
        o = self._config_entry.options
        errors: dict[str, str] = {}

        # Keep previously stored tuning values even though they are no longer exposed in the form.
        preserved = {
            CONF_ENABLED: o.get(CONF_ENABLED, DEFAULT_ENABLED),
            CONF_KP: o.get(CONF_KP, DEFAULT_KP),
            CONF_KI: o.get(CONF_KI, DEFAULT_KI),
            CONF_KD: o.get(CONF_KD, DEFAULT_KD),
            CONF_MIN_OUTPUT: o.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT),
            CONF_MAX_OUTPUT: o.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT),
        }

        defaults = {
            CONF_PROCESS_VALUE_ENTITY: o.get(CONF_PROCESS_VALUE_ENTITY, self._config_entry.data[CONF_PROCESS_VALUE_ENTITY]),
            CONF_SETPOINT_ENTITY: o.get(CONF_SETPOINT_ENTITY, self._config_entry.data[CONF_SETPOINT_ENTITY]),
            CONF_OUTPUT_ENTITY: o.get(CONF_OUTPUT_ENTITY, self._config_entry.data[CONF_OUTPUT_ENTITY]),
            CONF_INVERT_PV: o.get(CONF_INVERT_PV, DEFAULT_INVERT_PV),
            CONF_INVERT_SP: o.get(CONF_INVERT_SP, DEFAULT_INVERT_SP),
            CONF_PID_MODE: self._normalize_pid_mode(o.get(CONF_PID_MODE)),
            CONF_UPDATE_INTERVAL: self._coerce_int(
                o.get(CONF_UPDATE_INTERVAL),
                DEFAULT_UPDATE_INTERVAL,
                min_value=1,
            ),
        }

        if user_input is not None:
            cleaned = {
                CONF_PROCESS_VALUE_ENTITY: user_input.get(CONF_PROCESS_VALUE_ENTITY, defaults[CONF_PROCESS_VALUE_ENTITY]),
                CONF_SETPOINT_ENTITY: user_input.get(CONF_SETPOINT_ENTITY, defaults[CONF_SETPOINT_ENTITY]),
                CONF_OUTPUT_ENTITY: user_input.get(CONF_OUTPUT_ENTITY, defaults[CONF_OUTPUT_ENTITY]),
                CONF_INVERT_PV: user_input.get(CONF_INVERT_PV, defaults[CONF_INVERT_PV]),
                CONF_INVERT_SP: user_input.get(CONF_INVERT_SP, defaults[CONF_INVERT_SP]),
                CONF_PID_MODE: user_input.get(CONF_PID_MODE, defaults[CONF_PID_MODE]),
                CONF_UPDATE_INTERVAL: self._coerce_int(
                    user_input.get(CONF_UPDATE_INTERVAL),
                    defaults[CONF_UPDATE_INTERVAL],
                    min_value=1,
                ),
            }

            return self.async_create_entry(title="", data={**preserved, **cleaned})

            defaults = cleaned

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_schema(defaults),
            errors=errors,
        )

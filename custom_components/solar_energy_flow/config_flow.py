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
    """Options flow (PID tuning) shown when user clicks Configure."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # config_entry is read-only in your HA version
        self._config_entry = config_entry

    @staticmethod
    def _coerce_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_int(value, default, min_value=1):
        try:
            int_val = int(value)
        except (TypeError, ValueError):
            return default
        return max(min_value, int_val)

    @staticmethod
    def _build_schema(defaults: dict) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_PROCESS_VALUE_ENTITY, default=defaults[CONF_PROCESS_VALUE_ENTITY]): str,
                vol.Required(CONF_SETPOINT_ENTITY, default=defaults[CONF_SETPOINT_ENTITY]): str,
                vol.Required(CONF_OUTPUT_ENTITY, default=defaults[CONF_OUTPUT_ENTITY]): str,
                vol.Optional(CONF_ENABLED, default=defaults.get(CONF_ENABLED, DEFAULT_ENABLED)): bool,
                vol.Optional(CONF_KP, default=defaults.get(CONF_KP, DEFAULT_KP)): vol.Coerce(float),
                vol.Optional(CONF_KI, default=defaults.get(CONF_KI, DEFAULT_KI)): vol.Coerce(float),
                vol.Optional(CONF_KD, default=defaults.get(CONF_KD, DEFAULT_KD)): vol.Coerce(float),
                vol.Optional(CONF_MIN_OUTPUT, default=defaults.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT)): vol.Coerce(float),
                vol.Optional(CONF_MAX_OUTPUT, default=defaults.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT)): vol.Coerce(float),
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

    async def async_step_init(self, user_input=None):
        o = self._config_entry.options
        errors: dict[str, str] = {}

        defaults = {
            CONF_PROCESS_VALUE_ENTITY: o.get(CONF_PROCESS_VALUE_ENTITY, self._config_entry.data[CONF_PROCESS_VALUE_ENTITY]),
            CONF_SETPOINT_ENTITY: o.get(CONF_SETPOINT_ENTITY, self._config_entry.data[CONF_SETPOINT_ENTITY]),
            CONF_OUTPUT_ENTITY: o.get(CONF_OUTPUT_ENTITY, self._config_entry.data[CONF_OUTPUT_ENTITY]),
            CONF_ENABLED: o.get(CONF_ENABLED, DEFAULT_ENABLED),
            CONF_KP: self._coerce_float(o.get(CONF_KP), DEFAULT_KP),
            CONF_KI: self._coerce_float(o.get(CONF_KI), DEFAULT_KI),
            CONF_KD: self._coerce_float(o.get(CONF_KD), DEFAULT_KD),
            CONF_MIN_OUTPUT: self._coerce_float(o.get(CONF_MIN_OUTPUT), DEFAULT_MIN_OUTPUT),
            CONF_MAX_OUTPUT: self._coerce_float(o.get(CONF_MAX_OUTPUT), DEFAULT_MAX_OUTPUT),
            CONF_UPDATE_INTERVAL: self._coerce_int(
                o.get(CONF_UPDATE_INTERVAL),
                DEFAULT_UPDATE_INTERVAL,
                min_value=1,
            ),
        }

        if defaults[CONF_MAX_OUTPUT] < defaults[CONF_MIN_OUTPUT]:
            defaults[CONF_MAX_OUTPUT] = defaults[CONF_MIN_OUTPUT]

        if user_input is not None:
            cleaned = {
                CONF_PROCESS_VALUE_ENTITY: user_input.get(CONF_PROCESS_VALUE_ENTITY, defaults[CONF_PROCESS_VALUE_ENTITY]),
                CONF_SETPOINT_ENTITY: user_input.get(CONF_SETPOINT_ENTITY, defaults[CONF_SETPOINT_ENTITY]),
                CONF_OUTPUT_ENTITY: user_input.get(CONF_OUTPUT_ENTITY, defaults[CONF_OUTPUT_ENTITY]),
                CONF_ENABLED: user_input.get(CONF_ENABLED, DEFAULT_ENABLED),
                CONF_KP: self._coerce_float(user_input.get(CONF_KP), defaults[CONF_KP]),
                CONF_KI: self._coerce_float(user_input.get(CONF_KI), defaults[CONF_KI]),
                CONF_KD: self._coerce_float(user_input.get(CONF_KD), defaults[CONF_KD]),
                CONF_MIN_OUTPUT: self._coerce_float(user_input.get(CONF_MIN_OUTPUT), defaults[CONF_MIN_OUTPUT]),
                CONF_MAX_OUTPUT: self._coerce_float(user_input.get(CONF_MAX_OUTPUT), defaults[CONF_MAX_OUTPUT]),
                CONF_UPDATE_INTERVAL: self._coerce_int(
                    user_input.get(CONF_UPDATE_INTERVAL),
                    defaults[CONF_UPDATE_INTERVAL],
                    min_value=1,
                ),
            }

            if cleaned[CONF_MIN_OUTPUT] > cleaned[CONF_MAX_OUTPUT]:
                errors["base"] = "min_output_gt_max"
            else:
                return self.async_create_entry(title="", data=cleaned)

            defaults = cleaned

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_schema(defaults),
            errors=errors,
        )

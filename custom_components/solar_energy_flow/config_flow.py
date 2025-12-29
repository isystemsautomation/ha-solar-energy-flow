from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_SETPOINT_ENTITY,
    CONF_OUTPUT_ENTITY,
    CONF_GRID_POWER_ENTITY,
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
    CONF_GRID_POWER_INVERT,
    CONF_PID_MODE,
    CONF_GRID_LIMITER_ENABLED,
    CONF_GRID_LIMITER_TYPE,
    CONF_GRID_LIMITER_LIMIT_W,
    CONF_GRID_LIMITER_DEADBAND_W,
    CONF_PID_DEADBAND,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMITER_ENABLED,
    CONF_MAX_OUTPUT_STEP,
    CONF_OUTPUT_EPSILON,
    CONF_PV_MIN,
    CONF_PV_MAX,
    CONF_SP_MIN,
    CONF_SP_MAX,
    CONF_GRID_MIN,
    CONF_GRID_MAX,
    DEFAULT_INVERT_PV,
    DEFAULT_INVERT_SP,
    DEFAULT_GRID_POWER_INVERT,
    DEFAULT_PID_MODE,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_GRID_LIMITER_TYPE,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_PID_DEADBAND,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_LIMITER_ENABLED,
    DEFAULT_MAX_OUTPUT_STEP,
    DEFAULT_OUTPUT_EPSILON,
    DEFAULT_PV_MIN,
    DEFAULT_PV_MAX,
    DEFAULT_SP_MIN,
    DEFAULT_SP_MAX,
    DEFAULT_GRID_MIN,
    DEFAULT_GRID_MAX,
    PID_MODE_DIRECT,
    PID_MODE_REVERSE,
    CONF_ENERGY_DIVIDER_ENABLED,
    CONF_ENERGY_DIVIDER_STRATEGY,
    DEFAULT_ENERGY_DIVIDER_ENABLED,
    DEFAULT_ENERGY_DIVIDER_STRATEGY,
    ENERGY_DIVIDER_STRATEGIES,
)

_PV_DOMAINS = {"sensor", "number", "input_number"}
_SETPOINT_DOMAINS = {"number", "input_number"}
_OUTPUT_DOMAINS = {"number", "input_number"}
_GRID_DOMAINS = {"sensor", "number", "input_number"}


def _extract_domain(entity_id: str | None) -> str | None:
    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            pv_domain = _extract_domain(user_input[CONF_PROCESS_VALUE_ENTITY])
            sp_domain = _extract_domain(user_input[CONF_SETPOINT_ENTITY])
            output_domain = _extract_domain(user_input[CONF_OUTPUT_ENTITY])
            grid_domain = _extract_domain(user_input[CONF_GRID_POWER_ENTITY])

            if pv_domain not in _PV_DOMAINS:
                errors[CONF_PROCESS_VALUE_ENTITY] = "invalid_pv_domain"
            if sp_domain not in _SETPOINT_DOMAINS:
                errors[CONF_SETPOINT_ENTITY] = "invalid_setpoint_domain"
            if output_domain not in _OUTPUT_DOMAINS:
                errors[CONF_OUTPUT_ENTITY] = "invalid_output_domain"
            if grid_domain not in _GRID_DOMAINS:
                errors[CONF_GRID_POWER_ENTITY] = "invalid_grid_domain"
            if user_input.get(
                CONF_ENERGY_DIVIDER_STRATEGY, DEFAULT_ENERGY_DIVIDER_STRATEGY
            ) not in ENERGY_DIVIDER_STRATEGIES:
                errors[CONF_ENERGY_DIVIDER_STRATEGY] = "invalid_energy_divider_strategy"

            range_valid = True
            try:
                pv_min = float(user_input[CONF_PV_MIN])
                pv_max = float(user_input[CONF_PV_MAX])
                sp_min = float(user_input[CONF_SP_MIN])
                sp_max = float(user_input[CONF_SP_MAX])
                grid_min = float(user_input[CONF_GRID_MIN])
                grid_max = float(user_input[CONF_GRID_MAX])
            except (TypeError, ValueError):
                range_valid = False
            else:
                if pv_max <= pv_min or sp_max <= sp_min or grid_max <= grid_min:
                    range_valid = False

            if not range_valid:
                errors["base"] = "invalid_range"

            if errors:
                return self.async_show_form(step_id="user", data_schema=self._build_user_schema(), errors=errors)

            unique_id = (
                f"{user_input[CONF_PROCESS_VALUE_ENTITY]}::{user_input[CONF_SETPOINT_ENTITY]}::{user_input[CONF_OUTPUT_ENTITY]}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data=user_input)

        return self.async_show_form(step_id="user", data_schema=self._build_user_schema(), errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SolarEnergyFlowOptionsFlowHandler(config_entry)

    @staticmethod
    def _build_user_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_PROCESS_VALUE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_PV_DOMAINS))
                ),
                vol.Required(CONF_SETPOINT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_SETPOINT_DOMAINS))
                ),
                vol.Required(CONF_OUTPUT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_OUTPUT_DOMAINS))
                ),
                vol.Required(CONF_GRID_POWER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_GRID_DOMAINS))
                ),
                vol.Required(CONF_PV_MIN, default=DEFAULT_PV_MIN): vol.Coerce(float),
                vol.Required(CONF_PV_MAX, default=DEFAULT_PV_MAX): vol.Coerce(float),
                vol.Required(CONF_SP_MIN, default=DEFAULT_SP_MIN): vol.Coerce(float),
                vol.Required(CONF_SP_MAX, default=DEFAULT_SP_MAX): vol.Coerce(float),
                vol.Required(CONF_GRID_MIN, default=DEFAULT_GRID_MIN): vol.Coerce(float),
                vol.Required(CONF_GRID_MAX, default=DEFAULT_GRID_MAX): vol.Coerce(float),
                vol.Optional(
                    CONF_ENERGY_DIVIDER_ENABLED, default=DEFAULT_ENERGY_DIVIDER_ENABLED
                ): bool,
                vol.Optional(
                    CONF_ENERGY_DIVIDER_STRATEGY, default=DEFAULT_ENERGY_DIVIDER_STRATEGY
                ): vol.In(ENERGY_DIVIDER_STRATEGIES),
            }
        )


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
    def _validate_range(min_val, max_val) -> bool:
        try:
            min_f = float(min_val)
            max_f = float(max_val)
        except (TypeError, ValueError):
            return False
        return max_f > min_f

    @staticmethod
    def _build_schema(defaults: dict) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_PROCESS_VALUE_ENTITY, default=defaults[CONF_PROCESS_VALUE_ENTITY]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_PV_DOMAINS))
                ),
                vol.Required(CONF_SETPOINT_ENTITY, default=defaults[CONF_SETPOINT_ENTITY]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_SETPOINT_DOMAINS))
                ),
                vol.Required(CONF_OUTPUT_ENTITY, default=defaults[CONF_OUTPUT_ENTITY]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_OUTPUT_DOMAINS))
                ),
                vol.Required(CONF_GRID_POWER_ENTITY, default=defaults[CONF_GRID_POWER_ENTITY]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_GRID_DOMAINS))
                ),
                vol.Optional(CONF_INVERT_PV, default=defaults.get(CONF_INVERT_PV, DEFAULT_INVERT_PV)): bool,
                vol.Optional(CONF_INVERT_SP, default=defaults.get(CONF_INVERT_SP, DEFAULT_INVERT_SP)): bool,
                vol.Optional(
                    CONF_GRID_POWER_INVERT,
                    default=defaults.get(CONF_GRID_POWER_INVERT, DEFAULT_GRID_POWER_INVERT),
                ): bool,
                vol.Optional(
                    CONF_PID_MODE,
                    default=defaults.get(CONF_PID_MODE, DEFAULT_PID_MODE),
                ): vol.In([PID_MODE_DIRECT, PID_MODE_REVERSE]),
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_PV_MIN, default=defaults[CONF_PV_MIN]): vol.Coerce(float),
                vol.Required(CONF_PV_MAX, default=defaults[CONF_PV_MAX]): vol.Coerce(float),
                vol.Required(CONF_SP_MIN, default=defaults[CONF_SP_MIN]): vol.Coerce(float),
                vol.Required(CONF_SP_MAX, default=defaults[CONF_SP_MAX]): vol.Coerce(float),
                vol.Required(CONF_GRID_MIN, default=defaults[CONF_GRID_MIN]): vol.Coerce(float),
                vol.Required(CONF_GRID_MAX, default=defaults[CONF_GRID_MAX]): vol.Coerce(float),
                vol.Optional(
                    CONF_ENERGY_DIVIDER_ENABLED,
                    default=defaults.get(CONF_ENERGY_DIVIDER_ENABLED, DEFAULT_ENERGY_DIVIDER_ENABLED),
                ): bool,
                vol.Optional(
                    CONF_ENERGY_DIVIDER_STRATEGY,
                    default=defaults.get(CONF_ENERGY_DIVIDER_STRATEGY, DEFAULT_ENERGY_DIVIDER_STRATEGY),
                ): vol.In(ENERGY_DIVIDER_STRATEGIES),
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
            CONF_GRID_LIMITER_ENABLED: o.get(CONF_GRID_LIMITER_ENABLED, DEFAULT_GRID_LIMITER_ENABLED),
            CONF_GRID_LIMITER_TYPE: o.get(CONF_GRID_LIMITER_TYPE, DEFAULT_GRID_LIMITER_TYPE),
            CONF_GRID_LIMITER_LIMIT_W: o.get(CONF_GRID_LIMITER_LIMIT_W, DEFAULT_GRID_LIMITER_LIMIT_W),
            CONF_GRID_LIMITER_DEADBAND_W: o.get(
                CONF_GRID_LIMITER_DEADBAND_W, DEFAULT_GRID_LIMITER_DEADBAND_W
            ),
            CONF_PID_DEADBAND: o.get(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND),
            CONF_RATE_LIMITER_ENABLED: o.get(CONF_RATE_LIMITER_ENABLED, DEFAULT_RATE_LIMITER_ENABLED),
            CONF_RATE_LIMIT: o.get(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT),
            CONF_MAX_OUTPUT_STEP: o.get(CONF_MAX_OUTPUT_STEP, DEFAULT_MAX_OUTPUT_STEP),
            CONF_OUTPUT_EPSILON: o.get(CONF_OUTPUT_EPSILON, DEFAULT_OUTPUT_EPSILON),
            CONF_GRID_POWER_ENTITY: o.get(
                CONF_GRID_POWER_ENTITY, self._config_entry.data.get(CONF_GRID_POWER_ENTITY, "")
            ),
            CONF_ENERGY_DIVIDER_ENABLED: o.get(CONF_ENERGY_DIVIDER_ENABLED, DEFAULT_ENERGY_DIVIDER_ENABLED),
            CONF_ENERGY_DIVIDER_STRATEGY: o.get(CONF_ENERGY_DIVIDER_STRATEGY, DEFAULT_ENERGY_DIVIDER_STRATEGY),
        }

        defaults = {
            CONF_PROCESS_VALUE_ENTITY: o.get(
                CONF_PROCESS_VALUE_ENTITY, self._config_entry.data.get(CONF_PROCESS_VALUE_ENTITY, "")
            ),
            CONF_SETPOINT_ENTITY: o.get(
                CONF_SETPOINT_ENTITY, self._config_entry.data.get(CONF_SETPOINT_ENTITY, "")
            ),
            CONF_OUTPUT_ENTITY: o.get(CONF_OUTPUT_ENTITY, self._config_entry.data.get(CONF_OUTPUT_ENTITY, "")),
            CONF_GRID_POWER_ENTITY: o.get(
                CONF_GRID_POWER_ENTITY, self._config_entry.data.get(CONF_GRID_POWER_ENTITY, "")
            ),
            CONF_INVERT_PV: o.get(CONF_INVERT_PV, DEFAULT_INVERT_PV),
            CONF_INVERT_SP: o.get(CONF_INVERT_SP, DEFAULT_INVERT_SP),
            CONF_GRID_POWER_INVERT: o.get(CONF_GRID_POWER_INVERT, DEFAULT_GRID_POWER_INVERT),
            CONF_PID_MODE: self._normalize_pid_mode(o.get(CONF_PID_MODE)),
            CONF_UPDATE_INTERVAL: self._coerce_int(
                o.get(CONF_UPDATE_INTERVAL),
                DEFAULT_UPDATE_INTERVAL,
                min_value=1,
            ),
            CONF_PV_MIN: o.get(CONF_PV_MIN, self._config_entry.data.get(CONF_PV_MIN, DEFAULT_PV_MIN)),
            CONF_PV_MAX: o.get(CONF_PV_MAX, self._config_entry.data.get(CONF_PV_MAX, DEFAULT_PV_MAX)),
            CONF_SP_MIN: o.get(CONF_SP_MIN, self._config_entry.data.get(CONF_SP_MIN, DEFAULT_SP_MIN)),
            CONF_SP_MAX: o.get(CONF_SP_MAX, self._config_entry.data.get(CONF_SP_MAX, DEFAULT_SP_MAX)),
            CONF_GRID_MIN: o.get(CONF_GRID_MIN, self._config_entry.data.get(CONF_GRID_MIN, DEFAULT_GRID_MIN)),
            CONF_GRID_MAX: o.get(CONF_GRID_MAX, self._config_entry.data.get(CONF_GRID_MAX, DEFAULT_GRID_MAX)),
            CONF_ENERGY_DIVIDER_ENABLED: o.get(CONF_ENERGY_DIVIDER_ENABLED, DEFAULT_ENERGY_DIVIDER_ENABLED),
            CONF_ENERGY_DIVIDER_STRATEGY: o.get(CONF_ENERGY_DIVIDER_STRATEGY, DEFAULT_ENERGY_DIVIDER_STRATEGY),
        }

        if user_input is not None:
            cleaned = {
                CONF_PROCESS_VALUE_ENTITY: user_input.get(CONF_PROCESS_VALUE_ENTITY, defaults[CONF_PROCESS_VALUE_ENTITY]),
                CONF_SETPOINT_ENTITY: user_input.get(CONF_SETPOINT_ENTITY, defaults[CONF_SETPOINT_ENTITY]),
                CONF_OUTPUT_ENTITY: user_input.get(CONF_OUTPUT_ENTITY, defaults[CONF_OUTPUT_ENTITY]),
                CONF_GRID_POWER_ENTITY: user_input.get(CONF_GRID_POWER_ENTITY, defaults[CONF_GRID_POWER_ENTITY]),
                CONF_INVERT_PV: user_input.get(CONF_INVERT_PV, defaults[CONF_INVERT_PV]),
                CONF_INVERT_SP: user_input.get(CONF_INVERT_SP, defaults[CONF_INVERT_SP]),
                CONF_GRID_POWER_INVERT: user_input.get(CONF_GRID_POWER_INVERT, defaults[CONF_GRID_POWER_INVERT]),
                CONF_PID_MODE: user_input.get(CONF_PID_MODE, defaults[CONF_PID_MODE]),
                CONF_UPDATE_INTERVAL: self._coerce_int(
                    user_input.get(CONF_UPDATE_INTERVAL),
                    defaults[CONF_UPDATE_INTERVAL],
                    min_value=1,
                ),
                CONF_PV_MIN: user_input.get(CONF_PV_MIN, defaults[CONF_PV_MIN]),
                CONF_PV_MAX: user_input.get(CONF_PV_MAX, defaults[CONF_PV_MAX]),
                CONF_SP_MIN: user_input.get(CONF_SP_MIN, defaults[CONF_SP_MIN]),
                CONF_SP_MAX: user_input.get(CONF_SP_MAX, defaults[CONF_SP_MAX]),
                CONF_GRID_MIN: user_input.get(CONF_GRID_MIN, defaults[CONF_GRID_MIN]),
                CONF_GRID_MAX: user_input.get(CONF_GRID_MAX, defaults[CONF_GRID_MAX]),
                CONF_ENERGY_DIVIDER_ENABLED: user_input.get(
                    CONF_ENERGY_DIVIDER_ENABLED, defaults[CONF_ENERGY_DIVIDER_ENABLED]
                ),
                CONF_ENERGY_DIVIDER_STRATEGY: user_input.get(
                    CONF_ENERGY_DIVIDER_STRATEGY, defaults[CONF_ENERGY_DIVIDER_STRATEGY]
                ),
            }

            pv_domain = _extract_domain(cleaned[CONF_PROCESS_VALUE_ENTITY])
            sp_domain = _extract_domain(cleaned[CONF_SETPOINT_ENTITY])
            output_domain = _extract_domain(cleaned[CONF_OUTPUT_ENTITY])
            grid_domain = _extract_domain(cleaned[CONF_GRID_POWER_ENTITY])

            if pv_domain not in _PV_DOMAINS:
                errors[CONF_PROCESS_VALUE_ENTITY] = "invalid_pv_domain"
            if sp_domain not in _SETPOINT_DOMAINS:
                errors[CONF_SETPOINT_ENTITY] = "invalid_setpoint_domain"
            if output_domain not in _OUTPUT_DOMAINS:
                errors[CONF_OUTPUT_ENTITY] = "invalid_output_domain"
            if grid_domain not in _GRID_DOMAINS:
                errors[CONF_GRID_POWER_ENTITY] = "invalid_grid_domain"

            max_output_step = preserved.get(CONF_MAX_OUTPUT_STEP, DEFAULT_MAX_OUTPUT_STEP)
            output_epsilon = preserved.get(CONF_OUTPUT_EPSILON, DEFAULT_OUTPUT_EPSILON)

            try:
                max_output_step_val = float(max_output_step)
            except (TypeError, ValueError):
                errors["base"] = "invalid_max_output_step"
            else:
                if max_output_step_val < 0:
                    errors["base"] = "invalid_max_output_step"

            if "base" not in errors:
                try:
                    output_epsilon_val = float(output_epsilon)
                except (TypeError, ValueError):
                    errors["base"] = "invalid_output_epsilon"
                else:
                    if output_epsilon_val < 0:
                        errors["base"] = "invalid_output_epsilon"

            if "base" not in errors:
                if not self._validate_range(cleaned[CONF_PV_MIN], cleaned[CONF_PV_MAX]):
                    errors["base"] = "invalid_pv_range"
                elif not self._validate_range(cleaned[CONF_SP_MIN], cleaned[CONF_SP_MAX]):
                    errors["base"] = "invalid_sp_range"
                elif not self._validate_range(cleaned[CONF_GRID_MIN], cleaned[CONF_GRID_MAX]):
                    errors["base"] = "invalid_grid_range"

            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_schema(defaults),
                    errors=errors,
                )

            return self.async_create_entry(title="", data={**preserved, **cleaned})

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_schema(defaults),
            errors=errors,
        )

from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_BATTERY_SOC_ENTITY,
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
    CONF_CONSUMERS,
    CONSUMER_ID,
    CONSUMER_NAME,
    CONSUMER_TYPE,
    CONSUMER_ENABLE_CONTROL_MODE,
    CONSUMER_ENABLE_TARGET_ENTITY_ID,
    CONSUMER_STATE_ENTITY_ID,
    CONSUMER_POWER_TARGET_ENTITY_ID,
    CONSUMER_CONTROL_MODE_ONOFF,
    CONSUMER_CONTROL_MODE_PRESS,
    CONSUMER_PRIORITY,
    CONSUMER_MAX_POWER_W,
    CONSUMER_MIN_POWER_W,
    CONSUMER_ON_THRESHOLD_W,
    CONSUMER_OFF_THRESHOLD_W,
    CONSUMER_TYPE_BINARY,
    CONSUMER_TYPE_CONTROLLED,
    CONSUMER_STEP_W,
    CONSUMER_PID_DEADBAND_PCT,
    CONSUMER_ASSUMED_POWER_W,
    CONSUMER_DEFAULT_STEP_W,
    CONSUMER_MIN_STEP_W,
    CONSUMER_MAX_STEP_W,
    CONSUMER_DEFAULT_PID_DEADBAND_PCT,
    CONSUMER_MIN_PID_DEADBAND_PCT,
    CONSUMER_MAX_PID_DEADBAND_PCT,
    CONSUMER_DEFAULT_ASSUMED_POWER_W,
    CONSUMER_MIN_ASSUMED_POWER_W,
    CONSUMER_MAX_ASSUMED_POWER_W,
)

_PV_DOMAINS = {"sensor", "number", "input_number"}
_SETPOINT_DOMAINS = {"number", "input_number"}
_OUTPUT_DOMAINS = {"number", "input_number"}
_GRID_DOMAINS = {"sensor", "number", "input_number"}
_BATTERY_SOC_DOMAINS = {"sensor"}


def _extract_domain(entity_id: str | None) -> str | None:
    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


def _normalize_battery_soc_entity(value: str | None) -> str | None:
    """Normalize battery_soc_entity value - return None if empty/None, otherwise return trimmed string."""
    if not value:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value == "None":
            return None
        return value
    return None


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
            
            # Only validate battery_soc_entity if it's provided and not empty
            battery_soc_entity_value = _normalize_battery_soc_entity(user_input.get(CONF_BATTERY_SOC_ENTITY))
            if battery_soc_entity_value:
                battery_soc_domain = _extract_domain(battery_soc_entity_value)
                if battery_soc_domain and battery_soc_domain not in _BATTERY_SOC_DOMAINS:
                    errors[CONF_BATTERY_SOC_ENTITY] = "invalid_battery_soc_domain"

            range_valid = True
            try:
                pv_min = round(float(user_input[CONF_PV_MIN]), 1)
                pv_max = round(float(user_input[CONF_PV_MAX]), 1)
                sp_min = round(float(user_input[CONF_SP_MIN]), 1)
                sp_max = round(float(user_input[CONF_SP_MAX]), 1)
                grid_min = round(float(user_input[CONF_GRID_MIN]), 1)
                grid_max = round(float(user_input[CONF_GRID_MAX]), 1)
            except (TypeError, ValueError):
                range_valid = False
            else:
                if pv_max <= pv_min or sp_max <= sp_min or grid_max <= grid_min:
                    range_valid = False
                else:
                    # Update user_input with rounded values
                    user_input[CONF_PV_MIN] = pv_min
                    user_input[CONF_PV_MAX] = pv_max
                    user_input[CONF_SP_MIN] = sp_min
                    user_input[CONF_SP_MAX] = sp_max
                    user_input[CONF_GRID_MIN] = grid_min
                    user_input[CONF_GRID_MAX] = grid_max

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
            # Normalize battery_soc_entity - remove if empty/None
            battery_soc_value = _normalize_battery_soc_entity(user_input.get(CONF_BATTERY_SOC_ENTITY))
            if battery_soc_value:
                user_input[CONF_BATTERY_SOC_ENTITY] = battery_soc_value
            else:
                user_input.pop(CONF_BATTERY_SOC_ENTITY, None)
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
                vol.Optional(CONF_BATTERY_SOC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(_BATTERY_SOC_DOMAINS))
                ),
                vol.Required(CONF_PV_MIN, default=DEFAULT_PV_MIN): vol.Coerce(float),
                vol.Required(CONF_PV_MAX, default=DEFAULT_PV_MAX): vol.Coerce(float),
                vol.Required(CONF_SP_MIN, default=DEFAULT_SP_MIN): vol.Coerce(float),
                vol.Required(CONF_SP_MAX, default=DEFAULT_SP_MAX): vol.Coerce(float),
                vol.Required(CONF_GRID_MIN, default=DEFAULT_GRID_MIN): vol.Coerce(float),
                vol.Required(CONF_GRID_MAX, default=DEFAULT_GRID_MAX): vol.Coerce(float),
            }
        )


class SolarEnergyFlowOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for wiring and PID behavior shown when user clicks Configure."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # config_entry is read-only in your HA version
        self._config_entry = config_entry
        self._consumers: list[dict] = list(config_entry.options.get(CONF_CONSUMERS, []))
        self._selected_consumer_id: str | None = None
        self._pending_consumer_type: str | None = None

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
        schema_dict = {
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
        }
        
        # Only add default for battery_soc_entity if we have a valid value
        battery_soc_default = defaults.get(CONF_BATTERY_SOC_ENTITY)
        if battery_soc_default:
            schema_dict[CONF_BATTERY_SOC_ENTITY] = vol.Optional(
                CONF_BATTERY_SOC_ENTITY, default=battery_soc_default
            )(selector.EntitySelector(selector.EntitySelectorConfig(domain=list(_BATTERY_SOC_DOMAINS))))
        else:
            schema_dict[CONF_BATTERY_SOC_ENTITY] = vol.Optional(CONF_BATTERY_SOC_ENTITY)(
                selector.EntitySelector(selector.EntitySelectorConfig(domain=list(_BATTERY_SOC_DOMAINS)))
            )
        
        schema_dict.update({
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
        })
        return vol.Schema(schema_dict)

    async def async_step_init_settings(self, user_input=None):
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
            CONF_BATTERY_SOC_ENTITY: _normalize_battery_soc_entity(
                o.get(CONF_BATTERY_SOC_ENTITY, self._config_entry.data.get(CONF_BATTERY_SOC_ENTITY))
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
            CONF_PV_MIN: round(float(o.get(CONF_PV_MIN, self._config_entry.data.get(CONF_PV_MIN, DEFAULT_PV_MIN))), 1),
            CONF_PV_MAX: round(float(o.get(CONF_PV_MAX, self._config_entry.data.get(CONF_PV_MAX, DEFAULT_PV_MAX))), 1),
            CONF_SP_MIN: round(float(o.get(CONF_SP_MIN, self._config_entry.data.get(CONF_SP_MIN, DEFAULT_SP_MIN))), 1),
            CONF_SP_MAX: round(float(o.get(CONF_SP_MAX, self._config_entry.data.get(CONF_SP_MAX, DEFAULT_SP_MAX))), 1),
            CONF_GRID_MIN: round(float(o.get(CONF_GRID_MIN, self._config_entry.data.get(CONF_GRID_MIN, DEFAULT_GRID_MIN))), 1),
            CONF_GRID_MAX: round(float(o.get(CONF_GRID_MAX, self._config_entry.data.get(CONF_GRID_MAX, DEFAULT_GRID_MAX))), 1),
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
                CONF_PV_MIN: round(float(user_input.get(CONF_PV_MIN, defaults[CONF_PV_MIN])), 1),
                CONF_PV_MAX: round(float(user_input.get(CONF_PV_MAX, defaults[CONF_PV_MAX])), 1),
                CONF_SP_MIN: round(float(user_input.get(CONF_SP_MIN, defaults[CONF_SP_MIN])), 1),
                CONF_SP_MAX: round(float(user_input.get(CONF_SP_MAX, defaults[CONF_SP_MAX])), 1),
                CONF_GRID_MIN: round(float(user_input.get(CONF_GRID_MIN, defaults[CONF_GRID_MIN])), 1),
                CONF_GRID_MAX: round(float(user_input.get(CONF_GRID_MAX, defaults[CONF_GRID_MAX])), 1),
            }
            
            # Handle battery_soc_entity separately - it's optional, so only include if it has a valid non-empty value
            battery_soc_value = _normalize_battery_soc_entity(
                user_input.get(CONF_BATTERY_SOC_ENTITY, defaults.get(CONF_BATTERY_SOC_ENTITY))
            )
            if battery_soc_value:
                cleaned[CONF_BATTERY_SOC_ENTITY] = battery_soc_value
                # Validate the domain
                battery_soc_domain = _extract_domain(battery_soc_value)
                if battery_soc_domain and battery_soc_domain not in _BATTERY_SOC_DOMAINS:
                    errors[CONF_BATTERY_SOC_ENTITY] = "invalid_battery_soc_domain"

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
                    step_id="init_settings",
                    data_schema=self._build_schema(defaults),
                    errors=errors,
                )

            options = {**preserved, **cleaned}
            # Normalize battery_soc_entity - remove if empty/None
            battery_soc_in_options = _normalize_battery_soc_entity(options.get(CONF_BATTERY_SOC_ENTITY))
            if battery_soc_in_options:
                options[CONF_BATTERY_SOC_ENTITY] = battery_soc_in_options
            else:
                options.pop(CONF_BATTERY_SOC_ENTITY, None)
            options[CONF_CONSUMERS] = self._consumers
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init_settings",
            data_schema=self._build_schema(defaults),
            errors=errors,
        )

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "configure": "configure",
                "add_consumer": "add_consumer",
                "edit_consumer": "edit_consumer",
                "remove_consumer": "remove_consumer",
            },
        )

    async def async_step_configure(self, user_input=None):
        return await self.async_step_init_settings(user_input)

    async def async_step_add_consumer(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            consumer_type = user_input[CONSUMER_TYPE]
            if consumer_type not in (CONSUMER_TYPE_CONTROLLED, CONSUMER_TYPE_BINARY):
                errors["base"] = "invalid_consumer_type"
            else:
                self._pending_consumer_type = consumer_type
                return await self.async_step_add_consumer_details()

        return self.async_show_form(
            step_id="add_consumer",
            data_schema=vol.Schema(
                {
                    vol.Required(CONSUMER_TYPE): vol.In(
                        {CONSUMER_TYPE_CONTROLLED: "Controlled", CONSUMER_TYPE_BINARY: "Binary"}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_add_consumer_details(self, user_input=None):
        consumer_type = self._pending_consumer_type
        if consumer_type is None:
            return await self.async_step_add_consumer()

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_consumer_input(user_input, consumer_type)
            if not errors:
                # Generate new consumer ID and check for duplicates
                new_consumer_id = uuid.uuid4().hex
                existing_ids = {c.get(CONSUMER_ID) for c in self._consumers}
                # Ensure uniqueness (shouldn't happen with UUID, but safety check)
                while new_consumer_id in existing_ids:
                    new_consumer_id = uuid.uuid4().hex
                consumer = self._build_consumer(user_input, consumer_type, new_consumer_id)
                self._consumers.append(consumer)
                return self._create_entry_with_consumers()

        return self.async_show_form(
            step_id="add_consumer_details",
            data_schema=self._consumer_schema(consumer_type, user_input or {}),
            errors=errors,
        )

    async def async_step_edit_consumer(self, user_input=None):
        if not self._consumers:
            return self.async_abort(reason="no_consumers")

        consumer_map = {c[CONSUMER_ID]: c[CONSUMER_NAME] for c in self._consumers}
        if user_input is not None:
            consumer_id = user_input.get("consumer")
            if consumer_id in consumer_map:
                self._selected_consumer_id = consumer_id
                return await self.async_step_edit_consumer_details()

        return self.async_show_form(
            step_id="edit_consumer",
            data_schema=vol.Schema({vol.Required("consumer"): vol.In(consumer_map)}),
        )

    async def async_step_edit_consumer_details(self, user_input=None):
        if not self._selected_consumer_id:
            return await self.async_step_edit_consumer()

        consumer = next((c for c in self._consumers if c[CONSUMER_ID] == self._selected_consumer_id), None)
        if consumer is None:
            return await self.async_step_edit_consumer()

        consumer_type = consumer[CONSUMER_TYPE]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_consumer_input(user_input, consumer_type)
            if not errors:
                updated = self._build_consumer(user_input, consumer_type, consumer[CONSUMER_ID])
                self._consumers = [
                    updated if c[CONSUMER_ID] == self._selected_consumer_id else c for c in self._consumers
                ]
                return self._create_entry_with_consumers()

        return self.async_show_form(
            step_id="edit_consumer_details",
            data_schema=self._consumer_schema(consumer_type, consumer),
            errors=errors,
        )

    async def async_step_remove_consumer(self, user_input=None):
        if not self._consumers:
            return self.async_abort(reason="no_consumers")

        consumer_map = {c[CONSUMER_ID]: c[CONSUMER_NAME] for c in self._consumers}
        if user_input is not None:
            consumer_id = user_input.get("consumer")
            if consumer_id in consumer_map:
                self._consumers = [c for c in self._consumers if c[CONSUMER_ID] != consumer_id]
                return self._create_entry_with_consumers()

        return self.async_show_form(
            step_id="remove_consumer",
            data_schema=vol.Schema({vol.Required("consumer"): vol.In(consumer_map)}),
        )

    def _consumer_schema(self, consumer_type: str, defaults: dict) -> vol.Schema:
        control_mode_default = defaults.get(CONSUMER_ENABLE_CONTROL_MODE, CONSUMER_CONTROL_MODE_ONOFF)
        if control_mode_default not in (CONSUMER_CONTROL_MODE_ONOFF, CONSUMER_CONTROL_MODE_PRESS):
            control_mode_default = CONSUMER_CONTROL_MODE_ONOFF

        enable_target_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["button"] if control_mode_default == CONSUMER_CONTROL_MODE_PRESS else ["switch"]
            )
        )

        base = {
            vol.Required(CONSUMER_NAME, default=defaults.get(CONSUMER_NAME, "")): str,
            vol.Required(CONSUMER_PRIORITY, default=defaults.get(CONSUMER_PRIORITY, 1)): vol.Coerce(int),
            vol.Required(
                CONSUMER_ENABLE_CONTROL_MODE, default=control_mode_default
            ): vol.In({CONSUMER_CONTROL_MODE_ONOFF: "On/Off", CONSUMER_CONTROL_MODE_PRESS: "Button press"}),
            vol.Required(
                CONSUMER_ENABLE_TARGET_ENTITY_ID, default=defaults.get(CONSUMER_ENABLE_TARGET_ENTITY_ID, "")
            ): enable_target_selector,
            vol.Optional(
                CONSUMER_STATE_ENTITY_ID, default=defaults.get(CONSUMER_STATE_ENTITY_ID)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["switch", "binary_sensor", "sensor"])),
        }
        if consumer_type == CONSUMER_TYPE_CONTROLLED:
            base.update(
                {
                    vol.Required(CONSUMER_MIN_POWER_W, default=defaults.get(CONSUMER_MIN_POWER_W, 0.0)): vol.Coerce(
                        float
                    ),
                    vol.Required(
                        CONSUMER_MAX_POWER_W, default=defaults.get(CONSUMER_MAX_POWER_W, 0.0)
                    ): vol.Coerce(float),
                    vol.Required(
                        CONSUMER_POWER_TARGET_ENTITY_ID, default=defaults.get(CONSUMER_POWER_TARGET_ENTITY_ID, "")
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["number", "input_number"])),
                    vol.Required(
                        CONSUMER_STEP_W,
                        default=defaults.get(CONSUMER_STEP_W, CONSUMER_DEFAULT_STEP_W),
                    ): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=CONSUMER_MIN_STEP_W, max=CONSUMER_MAX_STEP_W),
                    ),
                    vol.Required(
                        CONSUMER_PID_DEADBAND_PCT,
                        default=defaults.get(CONSUMER_PID_DEADBAND_PCT, CONSUMER_DEFAULT_PID_DEADBAND_PCT),
                    ): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=CONSUMER_MIN_PID_DEADBAND_PCT, max=CONSUMER_MAX_PID_DEADBAND_PCT),
                    ),
                }
            )
        else:
            base.update(
                {
                    vol.Required(
                        CONSUMER_ON_THRESHOLD_W, default=defaults.get(CONSUMER_ON_THRESHOLD_W, 0.0)
                    ): vol.Coerce(float),
                    vol.Required(
                        CONSUMER_OFF_THRESHOLD_W, default=defaults.get(CONSUMER_OFF_THRESHOLD_W, 0.0)
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONSUMER_ASSUMED_POWER_W,
                        default=defaults.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W),
                    ): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=CONSUMER_MIN_ASSUMED_POWER_W, max=CONSUMER_MAX_ASSUMED_POWER_W),
                    ),
                }
            )

        return vol.Schema(base)

    def _validate_consumer_input(self, user_input: dict, consumer_type: str) -> dict[str, str]:
        errors: dict[str, str] = {}
        control_mode = user_input.get(CONSUMER_ENABLE_CONTROL_MODE, CONSUMER_CONTROL_MODE_ONOFF)
        if control_mode not in (CONSUMER_CONTROL_MODE_ONOFF, CONSUMER_CONTROL_MODE_PRESS):
            errors[CONSUMER_ENABLE_CONTROL_MODE] = "invalid_enable_control_mode"

        enable_target_domain = _extract_domain(user_input.get(CONSUMER_ENABLE_TARGET_ENTITY_ID))
        if control_mode == CONSUMER_CONTROL_MODE_PRESS:
            if enable_target_domain != "button":
                errors[CONSUMER_ENABLE_TARGET_ENTITY_ID] = "invalid_enable_target"
        elif control_mode == CONSUMER_CONTROL_MODE_ONOFF:
            if enable_target_domain != "switch":
                errors[CONSUMER_ENABLE_TARGET_ENTITY_ID] = "invalid_enable_target"

        state_domain = _extract_domain(user_input.get(CONSUMER_STATE_ENTITY_ID))
        if state_domain and state_domain not in {"switch", "binary_sensor", "sensor"}:
            errors[CONSUMER_STATE_ENTITY_ID] = "invalid_state_entity_domain"

        try:
            min_power = float(user_input.get(CONSUMER_MIN_POWER_W, 0.0))
            max_power = float(user_input.get(CONSUMER_MAX_POWER_W, 0.0))
        except (TypeError, ValueError):
            min_power = max_power = 0.0

        if consumer_type == CONSUMER_TYPE_CONTROLLED and max_power <= min_power:
            errors["base"] = "invalid_power_range"
        if consumer_type == CONSUMER_TYPE_CONTROLLED:
            power_target_domain = _extract_domain(user_input.get(CONSUMER_POWER_TARGET_ENTITY_ID))
            if power_target_domain and power_target_domain not in {"number", "input_number"}:
                errors[CONSUMER_POWER_TARGET_ENTITY_ID] = "invalid_power_target_domain"
            try:
                step_w = float(user_input.get(CONSUMER_STEP_W, CONSUMER_DEFAULT_STEP_W))
                pid_deadband_pct = float(
                    user_input.get(CONSUMER_PID_DEADBAND_PCT, CONSUMER_DEFAULT_PID_DEADBAND_PCT)
                )
                if not (
                    CONSUMER_MIN_STEP_W <= step_w <= CONSUMER_MAX_STEP_W
                    and CONSUMER_MIN_PID_DEADBAND_PCT <= pid_deadband_pct <= CONSUMER_MAX_PID_DEADBAND_PCT
                ):
                    errors["base"] = "invalid_consumer_settings"
            except (TypeError, ValueError):
                errors["base"] = "invalid_consumer_settings"

        if consumer_type == CONSUMER_TYPE_BINARY:
            try:
                on_threshold = float(user_input.get(CONSUMER_ON_THRESHOLD_W, 0.0))
                off_threshold = float(user_input.get(CONSUMER_OFF_THRESHOLD_W, 0.0))
                if on_threshold < off_threshold:
                    errors["base"] = "invalid_threshold_range"
                assumed_power = float(
                    user_input.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W)
                )
                if not (CONSUMER_MIN_ASSUMED_POWER_W <= assumed_power <= CONSUMER_MAX_ASSUMED_POWER_W):
                    errors["base"] = "invalid_consumer_settings"
            except (TypeError, ValueError):
                errors["base"] = "invalid_threshold_range"
        return errors

    def _build_consumer(self, user_input: dict, consumer_type: str, consumer_id: str) -> dict:
        consumer = {
            CONSUMER_ID: consumer_id,
            CONSUMER_NAME: user_input[CONSUMER_NAME],
            CONSUMER_TYPE: consumer_type,
            CONSUMER_PRIORITY: int(user_input[CONSUMER_PRIORITY]),
            CONSUMER_ENABLE_CONTROL_MODE: user_input.get(
                CONSUMER_ENABLE_CONTROL_MODE, CONSUMER_CONTROL_MODE_ONOFF
            ),
            CONSUMER_ENABLE_TARGET_ENTITY_ID: user_input.get(CONSUMER_ENABLE_TARGET_ENTITY_ID),
            CONSUMER_STATE_ENTITY_ID: user_input.get(CONSUMER_STATE_ENTITY_ID),
        }
        if consumer_type == CONSUMER_TYPE_CONTROLLED:
            consumer[CONSUMER_MIN_POWER_W] = float(user_input[CONSUMER_MIN_POWER_W])
            consumer[CONSUMER_MAX_POWER_W] = float(user_input[CONSUMER_MAX_POWER_W])
            consumer[CONSUMER_POWER_TARGET_ENTITY_ID] = user_input.get(CONSUMER_POWER_TARGET_ENTITY_ID, "")
            consumer[CONSUMER_STEP_W] = float(user_input.get(CONSUMER_STEP_W, CONSUMER_DEFAULT_STEP_W))
            consumer[CONSUMER_PID_DEADBAND_PCT] = float(
                user_input.get(CONSUMER_PID_DEADBAND_PCT, CONSUMER_DEFAULT_PID_DEADBAND_PCT)
            )
        else:
            consumer[CONSUMER_ON_THRESHOLD_W] = float(user_input[CONSUMER_ON_THRESHOLD_W])
            consumer[CONSUMER_OFF_THRESHOLD_W] = float(user_input[CONSUMER_OFF_THRESHOLD_W])
            consumer[CONSUMER_ASSUMED_POWER_W] = float(
                user_input.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W)
            )
        return consumer

    def _create_entry_with_consumers(self):
        options = dict(self._config_entry.options)
        options[CONF_CONSUMERS] = self._consumers
        return self.async_create_entry(title="", data=options)

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLED,
    CONF_KD,
    CONF_KI,
    CONF_KP,
    CONF_MAX_OUTPUT,
    CONF_MIN_OUTPUT,
    CONF_GRID_LIMITER_LIMIT_W,
    CONF_GRID_LIMITER_DEADBAND_W,
    CONF_PID_DEADBAND,
    CONF_RATE_LIMIT,
    CONF_RUNTIME_MODE,
    CONF_MANUAL_SP_VALUE,
    CONF_MANUAL_OUT_VALUE,
    DEFAULT_ENABLED,
    DEFAULT_KD,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_MIN_OUTPUT,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_PID_DEADBAND,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RUNTIME_MODE,
    DEFAULT_MANUAL_SP_VALUE,
    DEFAULT_MANUAL_OUT_VALUE,
    DOMAIN,
    RUNTIME_MODE_AUTO_SP,
    RUNTIME_MODE_HOLD,
    RUNTIME_MODE_MANUAL_OUT,
    RUNTIME_MODE_MANUAL_SP,
    HUB_DEVICE_SUFFIX,
    PID_DEVICE_SUFFIX,
    DIVIDER_DEVICE_SUFFIX,
    CONF_CONSUMERS,
    CONSUMER_TYPE,
    CONSUMER_TYPE_CONTROLLED,
    CONSUMER_DEVICE_SUFFIX,
    CONSUMER_ID,
    CONSUMER_NAME,
    CONSUMER_MIN_POWER_W,
    CONSUMER_MAX_POWER_W,
    CONSUMER_POWER_TARGET_ENTITY_ID,
)
from .consumer_bindings import ConsumerBinding, get_consumer_binding
from .coordinator import SolarEnergyFlowCoordinator
from .helpers import (
    RUNTIME_FIELD_CMD_W,
    RUNTIME_FIELD_START_TIMER_S,
    RUNTIME_FIELD_STOP_TIMER_S,
    async_dispatch_consumer_runtime_update,
    get_consumer_runtime,
    get_entry_coordinator,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = get_entry_coordinator(hass, entry.entry_id)

    entities: list[NumberEntity] = [
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_KP,
            "Kp",
            DEFAULT_KP,
            0.001,
            0.0,
            1000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_KI,
            "Ki",
            DEFAULT_KI,
            0.001,
            0.0,
            1000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_KD,
            "Kd",
            DEFAULT_KD,
            0.001,
            0.0,
            1000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_MIN_OUTPUT,
            "Min output",
            DEFAULT_MIN_OUTPUT,
            1.0,
            -20000.0,
            20000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_MAX_OUTPUT,
            "Max output",
            DEFAULT_MAX_OUTPUT,
            1.0,
            -20000.0,
            20000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_GRID_LIMITER_LIMIT_W,
            "Grid limiter limit",
            DEFAULT_GRID_LIMITER_LIMIT_W,
            10.0,
            0.0,
            20000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_GRID_LIMITER_DEADBAND_W,
            "Grid limiter deadband",
            DEFAULT_GRID_LIMITER_DEADBAND_W,
            10.0,
            0.0,
            20000.0,
            EntityCategory.CONFIG,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_PID_DEADBAND,
            "PID deadband",
            DEFAULT_PID_DEADBAND,
            1.0,
            0.0,
            2000.0,
            None,
        ),
        SolarEnergyFlowNumber(
            coordinator,
            entry,
            CONF_RATE_LIMIT,
            "Rate limit",
            DEFAULT_RATE_LIMIT,
            0.1,
            0.0,
            10000.0,
            EntityCategory.CONFIG,
            "points/s",
        ),
        SolarEnergyFlowManualNumber(
            coordinator,
            entry,
            CONF_MANUAL_SP_VALUE,
            "Manual SP",
            DEFAULT_MANUAL_SP_VALUE,
            1.0,
            -20000.0,
            20000.0,
        ),
        SolarEnergyFlowManualNumber(
            coordinator,
            entry,
            CONF_MANUAL_OUT_VALUE,
            "Manual OUT",
            DEFAULT_MANUAL_OUT_VALUE,
            1.0,
            -20000.0,
            20000.0,
        ),
    ]

    consumers = entry.options.get(CONF_CONSUMERS, [])
    for consumer in consumers:
        if consumer.get(CONSUMER_TYPE) != CONSUMER_TYPE_CONTROLLED:
            continue
        entities.append(SolarEnergyFlowConsumerNumber(entry, consumer))
        entities.append(SolarEnergyFlowConsumerDelayNumber(entry, consumer, True))
        entities.append(SolarEnergyFlowConsumerDelayNumber(entry, consumer, False))

    async_add_entities(entities)


class SolarEnergyFlowNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        default: float,
        step: float,
        min_value: float | None,
        max_value: float | None,
        entity_category: EntityCategory | None,
        native_unit: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._option_key = option_key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{option_key}"
        self._attr_native_step = step
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_entity_category = entity_category
        self._attr_native_unit_of_measurement = native_unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def native_value(self) -> float:
        try:
            return float(self._entry.options.get(self._option_key, self._default))
        except (TypeError, ValueError):
            return self._default

    async def async_set_native_value(self, value: float) -> None:
        options = dict(self._entry.options)

        # Keep existing values intact if they were never set before.
        options.setdefault(CONF_ENABLED, DEFAULT_ENABLED)
        options.setdefault(CONF_KP, DEFAULT_KP)
        options.setdefault(CONF_KI, DEFAULT_KI)
        options.setdefault(CONF_KD, DEFAULT_KD)
        options.setdefault(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT)
        options.setdefault(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT)
        options.setdefault(CONF_GRID_LIMITER_LIMIT_W, DEFAULT_GRID_LIMITER_LIMIT_W)
        options.setdefault(CONF_GRID_LIMITER_DEADBAND_W, DEFAULT_GRID_LIMITER_DEADBAND_W)
        options.setdefault(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND)
        options.setdefault(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT)

        options[self._option_key] = value

        # Enforce predictable min/max relationship by auto-adjusting the paired value.
        if self._option_key == CONF_MIN_OUTPUT:
            max_val = float(options.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT))
            if value > max_val:
                options[CONF_MAX_OUTPUT] = value
        elif self._option_key == CONF_MAX_OUTPUT:
            min_val = float(options.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT))
            if value < min_val:
                options[CONF_MIN_OUTPUT] = value

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()


class SolarEnergyFlowConsumerNumber(RestoreNumber):
    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "W"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, consumer: dict[str, Any]) -> None:
        self._entry = entry
        self._consumer = consumer
        self._consumer_id = consumer[CONSUMER_ID]
        self._binding: ConsumerBinding | None = None
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{consumer[CONSUMER_ID]}_power"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{self._consumer_id}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}"),
            name=consumer.get(CONSUMER_NAME, "Consumer"),
            manufacturer="Solar Energy Flow",
            model="Energy Divider Consumer",
        )
        self._attr_native_min_value = float(consumer.get(CONSUMER_MIN_POWER_W, 0.0))
        self._attr_native_max_value = float(consumer.get(CONSUMER_MAX_POWER_W, 0.0))
        self._current_value: float = self._attr_native_min_value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._binding = get_consumer_binding(self.hass, self._entry.entry_id, self._consumer)
        if self._binding is not None:
            self._binding.set_desired_power(self._current_value)
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._current_value = float(last.native_value)
            if self._binding is not None:
                self._binding.set_desired_power(self._current_value)
        if self._binding is not None and self._consumer.get(CONSUMER_POWER_TARGET_ENTITY_ID):
            await self._binding.async_push_power(self.hass)
        self._update_consumer_runtime()

    @property
    def native_value(self) -> float | None:
        return self._current_value

    def _update_consumer_runtime(self) -> None:
        if self.hass is None:
            return
        runtime = get_consumer_runtime(self.hass, self._entry.entry_id, self._consumer_id)
        runtime[RUNTIME_FIELD_CMD_W] = float(self._current_value)
        runtime.setdefault(RUNTIME_FIELD_START_TIMER_S, 0.0)
        runtime.setdefault(RUNTIME_FIELD_STOP_TIMER_S, 0.0)
        async_dispatch_consumer_runtime_update(self.hass, self._entry.entry_id, self._consumer_id)

    async def async_set_native_value(self, value: float) -> None:
        self._current_value = float(value)
        if self._binding is None:
            self._update_consumer_runtime()
            self.async_write_ha_state()
            return
        self._binding.set_desired_power(self._current_value)
        await self._binding.async_push_power(self.hass)
        self._update_consumer_runtime()
        self.async_write_ha_state()


class SolarEnergyFlowConsumerDelayNumber(RestoreNumber):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_step = 10.0
    _attr_native_min_value = 0.0
    _attr_native_max_value = 3600.0
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, consumer: dict[str, Any], is_start: bool) -> None:
        self._entry = entry
        self._consumer = consumer
        self._is_start = is_start
        self._consumer_id = consumer[CONSUMER_ID]
        suffix = "start_delay_s" if is_start else "stop_delay_s"
        name = "Start delay (s)" if is_start else "Stop delay (s)"
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self._consumer_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{self._consumer_id}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}"),
            name=consumer.get(CONSUMER_NAME, "Consumer"),
            manufacturer="Solar Energy Flow",
            model="Energy Divider Consumer",
        )
        self._default_value = 60.0 if is_start else 300.0
        self._current_value: float = self._default_value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._current_value = float(last.native_value)
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        return self._current_value

    async def async_set_native_value(self, value: float) -> None:
        self._current_value = float(value)
        self.async_write_ha_state()


class SolarEnergyFlowManualNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        default: float,
        step: float,
        min_value: float | None,
        max_value: float | None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._option_key = option_key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{option_key}"
        self._attr_native_step = step
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def native_value(self) -> float:
        data = getattr(self.coordinator, "data", None)
        if data is not None:
            if self._option_key == CONF_MANUAL_SP_VALUE:
                display_value = getattr(data, "manual_sp_display_value", None)
                if display_value is not None:
                    return round(display_value, 1)
                return round(data.manual_sp_value, 1)
            return round(data.manual_out_value, 1)
        try:
            return round(float(self._entry.options.get(self._option_key, self._default)), 1)
        except (TypeError, ValueError):
            return round(self._default, 1)

    def _runtime_mode(self) -> str:
        return self.coordinator.get_runtime_mode()

    def _mirror_value(self) -> float:
        data = getattr(self.coordinator, "data", None)
        if data is not None:
            if self._option_key == CONF_MANUAL_SP_VALUE:
                display_value = getattr(data, "manual_sp_display_value", None)
                if display_value is not None:
                    return round(display_value, 1)
                return round(data.manual_sp_value, 1)
            return round(data.manual_out_value, 1)
        try:
            return round(float(self._entry.options.get(self._option_key, self._default)), 1)
        except (TypeError, ValueError):
            return round(self._default, 1)

    async def _async_snap_back(self) -> None:
        if self._option_key == CONF_MANUAL_SP_VALUE:
            await self.coordinator.async_snap_back_manual_sp()
        else:
            await self.coordinator.async_snap_back_manual_out()
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        runtime_mode = self._runtime_mode()
        allowed = False
        if self._option_key == CONF_MANUAL_SP_VALUE:
            allowed = runtime_mode == RUNTIME_MODE_MANUAL_SP
        elif self._option_key == CONF_MANUAL_OUT_VALUE:
            allowed = runtime_mode == RUNTIME_MODE_MANUAL_OUT

        if not allowed:
            await self._async_snap_back()
            return

        options = dict(self._entry.options)

        options.setdefault(CONF_ENABLED, DEFAULT_ENABLED)
        options.setdefault(CONF_RUNTIME_MODE, runtime_mode)
        options.setdefault(CONF_MANUAL_SP_VALUE, self.coordinator.get_manual_sp_value())
        options.setdefault(CONF_MANUAL_OUT_VALUE, self.coordinator.get_manual_out_value())
        options[self._option_key] = value

        if self._option_key == CONF_MANUAL_SP_VALUE:
            await self.coordinator.async_set_manual_sp(value)
        else:
            await self.coordinator.async_set_manual_out(value)

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()

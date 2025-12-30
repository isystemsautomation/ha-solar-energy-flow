from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .consumer_bindings import get_consumer_binding
from .const import (
    CONF_BATTERY_SOC_ENTITY,
    CONF_CONSUMERS,
    CONSUMER_DEVICE_SUFFIX,
    CONSUMER_ID,
    CONSUMER_MAX_POWER_W,
    CONSUMER_MIN_POWER_W,
    CONSUMER_NAME,
    CONSUMER_ASSUMED_POWER_W,
    CONSUMER_DEFAULT_ASSUMED_POWER_W,
    CONSUMER_TYPE,
    CONSUMER_TYPE_CONTROLLED,
    DOMAIN,
    DIVIDER_DEVICE_SUFFIX,
    HUB_DEVICE_SUFFIX,
    PID_DEVICE_SUFFIX,
)
from .coordinator import SolarEnergyFlowCoordinator
from .helpers import (
    RUNTIME_FIELD_CMD_W,
    RUNTIME_FIELD_IS_ON,
    RUNTIME_FIELD_START_TIMER_S,
    RUNTIME_FIELD_STOP_TIMER_S,
    RUNTIME_FIELD_REASON,
    consumer_runtime_updated_signal,
    get_consumer_runtime,
    get_entry_coordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = get_entry_coordinator(hass, entry.entry_id)
    consumers = entry.options.get(CONF_CONSUMERS, [])
    if not isinstance(consumers, list):
        consumers = []
    entities: list[SensorEntity] = [
        SolarEnergyFlowEffectiveSPSensor(coordinator, entry),
        SolarEnergyFlowPVValueSensor(coordinator, entry),
        SolarEnergyFlowOutputSensor(coordinator, entry),
        SolarEnergyFlowErrorSensor(coordinator, entry),
        SolarEnergyFlowStatusSensor(coordinator, entry),
        SolarEnergyFlowGridPowerSensor(coordinator, entry),
        SolarEnergyFlowPTermSensor(coordinator, entry),
        SolarEnergyFlowITermSensor(coordinator, entry),
        SolarEnergyFlowDTermSensor(coordinator, entry),
        SolarEnergyFlowLimiterStateSensor(coordinator, entry),
        SolarEnergyFlowOutputPreRateLimitSensor(coordinator, entry),
        EnergyDividerPIDOutputPctSensor(coordinator, entry),
        EnergyDividerDeltaWSensor(coordinator, entry),
        EnergyDividerActiveConsumerSensor(coordinator, entry),
        EnergyDividerActivePrioritySensor(coordinator, entry),
        EnergyDividerConsumersSummarySensor(coordinator, entry, consumers),
        EnergyDividerTotalPowerSensor(coordinator, entry, consumers),
        EnergyDividerPriorityListSensor(coordinator, entry, consumers),
        EnergyDividerStateSensor(coordinator, entry),
        EnergyDividerReasonSensor(coordinator, entry),
    ]

    if CONF_BATTERY_SOC_ENTITY in entry.options:
        battery_soc_entity = entry.options.get(CONF_BATTERY_SOC_ENTITY)
    else:
        battery_soc_entity = entry.data.get(CONF_BATTERY_SOC_ENTITY)
    if battery_soc_entity:
        entities.append(BatterySOCSensor(entry, battery_soc_entity))

    for consumer in consumers:
        entities.extend(
            [
                ConsumerPIDOutputPctSensor(coordinator, entry, consumer),
                ConsumerDeltaWSensor(coordinator, entry, consumer),
            ]
        )
        entities.append(ConsumerStateSensor(entry, consumer))
        entities.append(ConsumerStartTimerSensor(entry, consumer))
        entities.append(ConsumerStopTimerSensor(entry, consumer))
        entities.append(ConsumerReasonSensor(entry, consumer))
        if consumer.get(CONSUMER_TYPE) == CONSUMER_TYPE_CONTROLLED:
            entities.append(ConsumerCommandedPowerSensor(entry, consumer))
        elif consumer.get(CONSUMER_TYPE) == CONSUMER_TYPE_BINARY:
            entities.append(ConsumerAssumedPowerSensor(entry, consumer))

    async_add_entities(entities)


class _BaseFlowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_suffix: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{unique_suffix}"
        if entity_category is not None:
            self._attr_entity_category = entity_category
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def _data(self):
        return getattr(self.coordinator, "data", None)


class _BaseDividerSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_suffix: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{unique_suffix}"
        if entity_category is not None:
            self._attr_entity_category = entity_category
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} Energy Divider",
            manufacturer="Solar Energy Flow",
            model="Energy Divider",
        )


class _BaseDividerRuntimeSensor(_BaseDividerSensor):
    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_suffix: str,
        consumers: list[dict],
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator, entry, name, unique_suffix, entity_category)
        self._consumer_ids: set[str] = set()
        for consumer in consumers:
            consumer_id = consumer.get(CONSUMER_ID)
            if consumer_id:
                self._consumer_ids.add(consumer_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                consumer_runtime_updated_signal(self._entry.entry_id),
                self._handle_runtime_update,
            )
        )
        self.async_write_ha_state()

    @callback
    def _handle_runtime_update(self, consumer_id: str) -> None:
        if not self._consumer_ids or consumer_id in self._consumer_ids:
            self.async_write_ha_state()


class SolarEnergyFlowEffectiveSPSensor(_BaseFlowSensor):
    _attr_icon = "mdi:target-variant"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Effective SP", "effective_sp")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "sp", None)


class SolarEnergyFlowPVValueSensor(_BaseFlowSensor):
    _attr_icon = "mdi:gauge"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "PV value", "pv_value")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "pv", None)


class SolarEnergyFlowOutputSensor(_BaseFlowSensor):
    _attr_icon = "mdi:tune-vertical"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Output", "output")

    @property
    def native_value(self):
        data = self._data
        out = getattr(data, "out", None) if data else None
        return round(out, 1) if out is not None else None


class SolarEnergyFlowErrorSensor(_BaseFlowSensor):
    _attr_icon = "mdi:delta"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Error", "error")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "error", None)


class SolarEnergyFlowStatusSensor(_BaseFlowSensor):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Status", "status")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "status", None)


class SolarEnergyFlowGridPowerSensor(_BaseFlowSensor):
    _attr_icon = "mdi:home-lightning-bolt-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Grid power", "grid_power")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "grid_power", None)


class SolarEnergyFlowPTermSensor(_BaseFlowSensor):
    _attr_icon = "mdi:alpha-p-circle-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "P term", "p_term")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "p_term", None)


class SolarEnergyFlowITermSensor(_BaseFlowSensor):
    _attr_icon = "mdi:alpha-i-circle-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "I term", "i_term")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "i_term", None)


class SolarEnergyFlowDTermSensor(_BaseFlowSensor):
    _attr_icon = "mdi:alpha-d-circle-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "D term", "d_term")

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "d_term", None)


class SolarEnergyFlowLimiterStateSensor(_BaseFlowSensor):
    _attr_icon = "mdi:flash-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Limiter state", "limiter_state", EntityCategory.DIAGNOSTIC)

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "limiter_state", None)


class SolarEnergyFlowOutputPreRateLimitSensor(_BaseFlowSensor):
    _attr_icon = "mdi:tune-vertical"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator, entry, "Output (pre rate limit)", "output_pre_rate_limit", EntityCategory.DIAGNOSTIC
        )

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "output_pre_rate_limit", None)
        return round(value, 1) if value is not None else None


class EnergyDividerPIDOutputPctSensor(_BaseDividerSensor):
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "PID output %", "divider_pid_output_pct", EntityCategory.DIAGNOSTIC)

    @property
    def native_value(self):
        try:
            value = getattr(self.coordinator, "pid_output_pct", None)
            if value is None:
                return None
            return round(float(value), 1)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to read PID output for %s: %s", self._entry.entry_id, err)
            return None


class EnergyDividerDeltaWSensor(_BaseDividerSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Delta W", "divider_delta_w", EntityCategory.DIAGNOSTIC)

    @property
    def native_value(self):
        try:
            value = getattr(self.coordinator, "delta_w", None)
            return float(value) if value is not None else None
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to read delta W for %s: %s", self._entry.entry_id, err)
            return None


class EnergyDividerActiveConsumerSensor(_BaseDividerSensor):
    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            "Active controlled consumer",
            "divider_active_consumer",
            EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self) -> str | None:
        try:
            name = getattr(self.coordinator, "active_controlled_consumer_name", None)
            if not name:
                return "None"
            return str(name)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to read active controlled consumer for %s: %s", self._entry.entry_id, err)
            return "None"


class EnergyDividerActivePrioritySensor(_BaseDividerSensor):
    _attr_icon = "mdi:order-numeric-ascending"

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            "Active consumer priority",
            "divider_active_priority",
            EntityCategory.DIAGNOSTIC,
        )

    @property
    def native_value(self):
        try:
            priority = getattr(self.coordinator, "active_controlled_consumer_priority", None)
            if priority is None:
                return "-"
            if isinstance(priority, (int, float)):
                return priority
            return str(priority)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to read active consumer priority for %s: %s", self._entry.entry_id, err)
            return "-"


class EnergyDividerStateSensor(_BaseDividerSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Divider state", "divider_state", EntityCategory.DIAGNOSTIC)

    @property
    def native_value(self):
        try:
            state = getattr(self.coordinator, "divider_state", None)
            if state is None:
                return "n/a"
            return str(state)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to read divider state for %s: %s", self._entry.entry_id, err)
            return "n/a"


class EnergyDividerReasonSensor(_BaseDividerSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Divider reason", "divider_reason", EntityCategory.DIAGNOSTIC)

    @property
    def native_value(self):
        try:
            reason = getattr(self.coordinator, "divider_reason", None)
            if reason is None:
                return "n/a"
            return str(reason)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to read divider reason for %s: %s", self._entry.entry_id, err)
            return "n/a"


class EnergyDividerConsumersSummarySensor(_BaseDividerRuntimeSensor):
    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry, consumers: list[dict]) -> None:
        super().__init__(
            coordinator, entry, "Consumers summary", "divider_consumers_summary", consumers, EntityCategory.DIAGNOSTIC
        )
        self._consumers = consumers

    def _truncate(self, value: str) -> str:
        if len(value) <= 255:
            return value
        return value[:252] + "..."

    @staticmethod
    def _assumed_power_w(consumer: dict) -> float:
        try:
            return float(consumer.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W) or 0.0)
        except (TypeError, ValueError):
            return CONSUMER_DEFAULT_ASSUMED_POWER_W

    def _format_consumer(self, consumer: dict) -> str | None:
        try:
            consumer_id = consumer.get(CONSUMER_ID)
            if consumer_id is None:
                return None
            name = consumer.get(CONSUMER_NAME, consumer_id)
            runtime = get_consumer_runtime(self.hass, self._entry.entry_id, consumer_id)
            cmd_w = runtime.get(RUNTIME_FIELD_CMD_W, 0.0)
            consumer_type = consumer.get(CONSUMER_TYPE)
            display_value: str
            if consumer_type == CONSUMER_TYPE_CONTROLLED:
                display_value = f"{round(float(cmd_w or 0.0))}W"
            elif consumer_type == CONSUMER_TYPE_BINARY:
                is_on = bool(runtime.get(RUNTIME_FIELD_IS_ON, False))
                if is_on:
                    assumed_power = round(self._assumed_power_w(consumer))
                    display_value = f"ON {assumed_power}W"
                else:
                    display_value = "OFF"
            else:
                binding = get_consumer_binding(self.hass, self._entry.entry_id, consumer)
                enabled_state = binding.get_effective_enabled(self.hass) if binding is not None else None
                if enabled_state is True:
                    display_value = "ON"
                elif enabled_state is False:
                    display_value = "OFF"
                else:
                    display_value = "UNKNOWN"
            return f"{name}={display_value}"
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to format consumer summary for %s: %s", self._entry.entry_id, err)
            return None

    @property
    def native_value(self) -> str:
        try:
            if not self._consumers:
                return "empty"
            entries: list[str] = []
            for consumer in self._consumers:
                formatted = self._format_consumer(consumer)
                if formatted:
                    entries.append(formatted)
            summary = "; ".join(entries)
            if not summary:
                return "empty"
            return self._truncate(summary)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to build consumers summary for %s: %s", self._entry.entry_id, err)
            return "error"


class EnergyDividerTotalPowerSensor(_BaseDividerRuntimeSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry, consumers: list[dict]) -> None:
        super().__init__(
            coordinator, entry, "Total consumer power", "divider_total_power", consumers, EntityCategory.DIAGNOSTIC
        )
        self._consumers = consumers

    def _safe_float(self, value: float | int | None) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _compute_total_power(self) -> float:
        total = 0.0
        for consumer in self._consumers:
            consumer_id = consumer.get(CONSUMER_ID)
            if not consumer_id:
                continue
            try:
                consumer_type = consumer.get(CONSUMER_TYPE)
                runtime = get_consumer_runtime(self.hass, self._entry.entry_id, consumer_id)
                if consumer_type == CONSUMER_TYPE_CONTROLLED:
                    total += self._safe_float(runtime.get(RUNTIME_FIELD_CMD_W))
                elif consumer_type == CONSUMER_TYPE_BINARY:
                    is_on = bool(runtime.get(RUNTIME_FIELD_IS_ON, False))
                    if is_on:
                        total += self._safe_float(
                            consumer.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W)
                        )
                else:
                    total += 0.0
            except Exception as err:  # pragma: no cover - defensive
                _LOGGER.exception(
                    "Failed to compute total power for consumer %s on %s: %s", consumer_id, self._entry.entry_id, err
                )
        return total

    @property
    def native_value(self) -> float:
        try:
            return self._compute_total_power()
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to compute divider total power for %s: %s", self._entry.entry_id, err)
            return 0.0


class EnergyDividerPriorityListSensor(_BaseDividerRuntimeSensor):
    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry, consumers: list[dict]) -> None:
        super().__init__(
            coordinator, entry, "Priority list", "divider_priority_list", consumers, EntityCategory.DIAGNOSTIC
        )
        self._consumers = consumers

    @staticmethod
    def _truncate(value: str) -> str:
        if len(value) <= 255:
            return value
        return value[:254] + "…"

    @staticmethod
    def _format_priority(raw_priority: float | int | str | None, fallback: int) -> str:
        try:
            if raw_priority is None:
                return str(fallback)
            value = float(raw_priority)
            if value.is_integer():
                return str(int(value))
            return str(round(value, 2))
        except (TypeError, ValueError):
            return str(fallback)

    def _format_consumer_state(self, consumer: dict, fallback_priority: int) -> str | None:
        consumer_id = consumer.get(CONSUMER_ID)
        if not consumer_id:
            return None
        try:
            runtime = get_consumer_runtime(self.hass, self._entry.entry_id, consumer_id)
            consumer_type = consumer.get(CONSUMER_TYPE)
            priority = self._format_priority(consumer.get(CONSUMER_PRIORITY), fallback_priority)
            name = consumer.get(CONSUMER_NAME, consumer_id)

            if consumer_type == CONSUMER_TYPE_CONTROLLED:
                cmd_w = runtime.get(RUNTIME_FIELD_CMD_W, 0.0)
                try:
                    cmd_w_value = float(cmd_w or 0.0)
                except (TypeError, ValueError):
                    cmd_w_value = 0.0
                state = "RUNNING" if cmd_w_value > 0 else "OFF"
                cmd_part = f" {round(cmd_w_value)}W"
                type_label = "controlled"
            else:
                is_on = bool(runtime.get(RUNTIME_FIELD_IS_ON, False))
                state = "ON" if is_on else "OFF"
                assumed_power = 0.0
                if is_on:
                    try:
                        assumed_power = float(
                            consumer.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W) or 0.0
                        )
                    except (TypeError, ValueError):
                        assumed_power = CONSUMER_DEFAULT_ASSUMED_POWER_W
                cmd_part = f" {round(assumed_power)}W" if is_on else ""
                type_label = "binary" if consumer_type == CONSUMER_TYPE_BINARY else "other"

            return f"{priority}: {name} ({type_label}) {state}{cmd_part}".strip()
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception(
                "Failed to format priority list entry for consumer %s on %s: %s",
                consumer_id,
                self._entry.entry_id,
                err,
            )
            return None

    @property
    def native_value(self) -> str:
        try:
            if not self._consumers:
                return "empty"

            entries: list[str] = []
            for index, consumer in enumerate(self._consumers):
                formatted = self._format_consumer_state(consumer, index + 1)
                if formatted:
                    entries.append(formatted)

            if not entries:
                return "empty"

            return self._truncate("; ".join(entries))
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to build priority list for %s: %s", self._entry.entry_id, err)
            return "error"


class BatterySOCSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:battery-high"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, source_entity: str) -> None:
        self._entry = entry
        self._source_entity = source_entity
        self._attr_name = "Battery SOC"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_battery_soc"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} Energy Divider",
            manufacturer="Solar Energy Flow",
            model="Energy Divider",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_entity], self._handle_state_update
            )
        )
        self.async_write_ha_state()

    @callback
    def _handle_state_update(self, event) -> None:
        self.async_write_ha_state()

    def _read_source_value(self):
        state = self.hass.states.get(self._source_entity)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return state.state

    @property
    def native_value(self):
        return self._read_source_value()


class _BaseConsumerMirrorSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        consumer: dict,
        name: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._consumer = consumer
        self._consumer_id = consumer[CONSUMER_ID]
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self._consumer_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{self._consumer_id}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}"),
            name=consumer.get(CONSUMER_NAME, "Consumer"),
            manufacturer="Solar Energy Flow",
            model="Energy Divider Consumer",
        )


class ConsumerPIDOutputPctSensor(_BaseConsumerMirrorSensor):
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(coordinator, entry, consumer, "PID output %", "pid_output_pct")

    @property
    def native_value(self):
        value = getattr(self.coordinator, "pid_output_pct", None)
        return round(value, 1) if value is not None else None


class ConsumerDeltaWSensor(_BaseConsumerMirrorSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(coordinator, entry, consumer, "Delta W", "delta_w")

    @property
    def native_value(self):
        return getattr(self.coordinator, "delta_w", None)


class _BaseConsumerRuntimeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, consumer: dict, name: str, unique_suffix: str) -> None:
        self._entry = entry
        self._consumer = consumer
        self._consumer_id = consumer[CONSUMER_ID]
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self._consumer_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{self._consumer_id}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}"),
            name=consumer.get(CONSUMER_NAME, "Consumer"),
            manufacturer="Solar Energy Flow",
            model="Energy Divider Consumer",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                consumer_runtime_updated_signal(self._entry.entry_id),
                self._handle_runtime_update,
            )
        )
        self.async_write_ha_state()

    @callback
    def _handle_runtime_update(self, consumer_id: str) -> None:
        if consumer_id != self._consumer_id:
            return
        self.async_write_ha_state()

    def _runtime(self) -> dict[str, float]:
        return get_consumer_runtime(self.hass, self._entry.entry_id, self._consumer_id)


class ConsumerCommandedPowerSensor(_BaseConsumerRuntimeSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "Power command", "cmd_power")

    @property
    def native_value(self):
        runtime = self._runtime()
        return runtime.get(RUNTIME_FIELD_CMD_W, 0.0)


class ConsumerStateSensor(_BaseConsumerRuntimeSensor):
    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "State", "state")
        self._consumer_type = consumer.get(CONSUMER_TYPE)

    @property
    def native_value(self):
        coordinator = getattr(self, "coordinator", None)
        if coordinator is None:
            return "OFF"
        runtime_store = getattr(coordinator, "consumer_runtime", None)
        runtime = runtime_store.get(self._consumer_id, {}) if isinstance(runtime_store, dict) else {}
        if self._consumer_type == CONSUMER_TYPE_BINARY:
            is_on = bool(runtime.get(RUNTIME_FIELD_IS_ON, False))
            return "RUNNING" if is_on else "OFF"
        try:
            cmd_w = float(runtime.get(RUNTIME_FIELD_CMD_W) or 0.0)
        except (TypeError, ValueError):
            cmd_w = 0.0
        return "RUNNING" if cmd_w > 0 else "OFF"


class ConsumerStartTimerSensor(_BaseConsumerRuntimeSensor):
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "Start timer", "start_timer_s")

    @property
    def native_value(self):
        runtime = self._runtime()
        return runtime.get(RUNTIME_FIELD_START_TIMER_S, 0.0)


class ConsumerStopTimerSensor(_BaseConsumerRuntimeSensor):
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "Stop timer", "stop_timer_s")

    @property
    def native_value(self):
        runtime = self._runtime()
        return runtime.get(RUNTIME_FIELD_STOP_TIMER_S, 0.0)


class ConsumerReasonSensor(_BaseConsumerRuntimeSensor):
    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "Reason", "reason")

    @property
    def native_value(self):
        runtime = self._runtime()
        return runtime.get(RUNTIME_FIELD_REASON, "")


class ConsumerAssumedPowerSensor(_BaseConsumerRuntimeSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "Assumed power", "assumed_power_w")
        self._assumed_power = float(consumer.get(CONSUMER_ASSUMED_POWER_W, CONSUMER_DEFAULT_ASSUMED_POWER_W))
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._assumed_power

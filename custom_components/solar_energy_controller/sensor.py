from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarEnergyFlowCoordinator

type SolarEnergyControllerConfigEntry = ConfigEntry[SolarEnergyFlowCoordinator]

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: SolarEnergyControllerConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
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
        ]
    )


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
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Solar Energy Controller",
            model="PID Controller",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _data(self):
        return getattr(self.coordinator, "data", None)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        return data is not None


class SolarEnergyFlowEffectiveSPSensor(_BaseFlowSensor):
    _attr_icon = "mdi:target-variant"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Effective SP", "effective_sp")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        return data is not None and getattr(data, "sp", None) is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "sp", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowPVValueSensor(_BaseFlowSensor):
    _attr_icon = "mdi:gauge"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "PV value", "pv_value")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        return data is not None and getattr(data, "pv", None) is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "pv", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowOutputSensor(_BaseFlowSensor):
    _attr_icon = "mdi:tune-vertical"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Output", "output")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        return data is not None and getattr(data, "out", None) is not None

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
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        # Error can be None when PV or SP is missing, which is valid
        return data is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "error", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowStatusSensor(_BaseFlowSensor):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Status", "status")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        return data is not None and getattr(data, "status", None) is not None

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "status", None)

    @property
    def extra_state_attributes(self):
        """Expose all PID data as attributes for the custom card."""
        data = self._data
        if not data:
            return {}
        
        # Get runtime options from coordinator
        options = self.coordinator._build_runtime_options()
        
        # Get values from entry options
        from .const import (
            CONF_KP, CONF_KI, CONF_KD, CONF_MIN_OUTPUT, CONF_MAX_OUTPUT,
            CONF_PID_DEADBAND,
            DEFAULT_KP, DEFAULT_KI, DEFAULT_KD, DEFAULT_MIN_OUTPUT, DEFAULT_MAX_OUTPUT,
            DEFAULT_PID_DEADBAND,
            RUNTIME_MODE_AUTO_SP, RUNTIME_MODE_MANUAL_SP, RUNTIME_MODE_HOLD, RUNTIME_MODE_MANUAL_OUT,
        )
        
        return {
            "enabled": options.enabled,
            "runtime_mode": options.runtime_mode,
            "runtime_modes": [
                RUNTIME_MODE_AUTO_SP,
                RUNTIME_MODE_MANUAL_SP,
                RUNTIME_MODE_HOLD,
                RUNTIME_MODE_MANUAL_OUT,
            ],
            "pv_value": getattr(data, "pv", None),
            "effective_sp": getattr(data, "sp", None),
            "error": getattr(data, "error", None),
            "output": getattr(data, "out", None),
            "status": getattr(data, "status", None),
            "p_term": getattr(data, "p_term", None),
            "i_term": getattr(data, "i_term", None),
            "d_term": getattr(data, "d_term", None),
            "grid_power": getattr(data, "grid_power", None),
            "kp": self._entry.options.get(CONF_KP, DEFAULT_KP),
            "ki": self._entry.options.get(CONF_KI, DEFAULT_KI),
            "kd": self._entry.options.get(CONF_KD, DEFAULT_KD),
            "deadband": self._entry.options.get(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND),
            "min_output": self._entry.options.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT),
            "max_output": self._entry.options.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT),
            "manual_out": self.coordinator.get_manual_out_value(),
            "manual_sp": self.coordinator.get_manual_sp_value(),
            "limiter_state": getattr(data, "limiter_state", None),
            "output_pre_rate_limit": getattr(data, "output_pre_rate_limit", None),
        }


class SolarEnergyFlowGridPowerSensor(_BaseFlowSensor):
    _attr_icon = "mdi:home-lightning-bolt-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Grid power", "grid_power")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        # Grid power can be None if grid sensor is unavailable, which is valid
        return data is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "grid_power", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowPTermSensor(_BaseFlowSensor):
    _attr_icon = "mdi:alpha-p-circle-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "P term", "p_term", EntityCategory.DIAGNOSTIC)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        # P term can be None when PID is not active, which is valid
        return data is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "p_term", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowITermSensor(_BaseFlowSensor):
    _attr_icon = "mdi:alpha-i-circle-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "I term", "i_term", EntityCategory.DIAGNOSTIC)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        # I term can be None when PID is not active, which is valid
        return data is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "i_term", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowDTermSensor(_BaseFlowSensor):
    _attr_icon = "mdi:alpha-d-circle-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "D term", "d_term", EntityCategory.DIAGNOSTIC)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        # D term can be None when PID is not active, which is valid
        return data is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "d_term", None)
        return round(value, 1) if value is not None else None


class SolarEnergyFlowLimiterStateSensor(_BaseFlowSensor):
    _attr_icon = "mdi:flash-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Limiter state", "limiter_state", EntityCategory.DIAGNOSTIC)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        return data is not None and getattr(data, "limiter_state", None) is not None

    @property
    def native_value(self):
        data = self._data
        return getattr(data, "limiter_state", None)


class SolarEnergyFlowOutputPreRateLimitSensor(_BaseFlowSensor):
    _attr_icon = "mdi:tune-vertical"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator, entry, "Output (pre rate limit)", "output_pre_rate_limit", EntityCategory.DIAGNOSTIC
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self._data
        # Output pre rate limit can be None when output is not calculated, which is valid
        return data is not None

    @property
    def native_value(self):
        data = self._data
        value = getattr(data, "output_pre_rate_limit", None)
        return round(value, 1) if value is not None else None

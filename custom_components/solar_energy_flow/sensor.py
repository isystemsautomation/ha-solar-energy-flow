from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarEnergyFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
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
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def _data(self):
        return getattr(self.coordinator, "data", None)


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
        value = getattr(data, "i_term", None)
        return round(value, 1) if value is not None else None


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

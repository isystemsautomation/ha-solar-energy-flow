from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SolarEnergyFlowOutputSensor(coordinator, entry),
            SolarEnergyFlowErrorSensor(coordinator, entry),
            SolarEnergyFlowStatusSensor(coordinator, entry),
            SolarEnergyFlowLimiterStateSensor(coordinator, entry),
        ]
    )


class _BaseFlowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, name: str, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )


class SolarEnergyFlowOutputSensor(_BaseFlowSensor):
    _attr_icon = "mdi:tune-vertical"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Output", "output")

    @property
    def native_value(self):
        out = getattr(self.coordinator.data, "out", None)
        return round(out, 1) if out is not None else None


class SolarEnergyFlowErrorSensor(_BaseFlowSensor):
    _attr_icon = "mdi:delta"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Error", "error")

    @property
    def native_value(self):
        return self.coordinator.data.error


class SolarEnergyFlowStatusSensor(_BaseFlowSensor):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Status", "status")

    @property
    def native_value(self):
        return self.coordinator.data.status


class SolarEnergyFlowLimiterStateSensor(_BaseFlowSensor):
    _attr_icon = "mdi:flash-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Limiter state", "limiter_state")

    @property
    def native_value(self):
        return getattr(self.coordinator.data, "limiter_state", None)

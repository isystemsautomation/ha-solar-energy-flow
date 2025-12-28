from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DEFAULT_NAME


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SolarEnergyFlowOutputSensor(coordinator, entry),
            SolarEnergyFlowErrorSensor(coordinator, entry),
            SolarEnergyFlowStatusSensor(coordinator, entry),
        ]
    )


class _BaseFlowSensor(CoordinatorEntity, SensorEntity):
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
        super().__init__(coordinator, entry, "Solar Energy Flow Output", "output")

    @property
    def native_value(self):
        return self.coordinator.data.out


class SolarEnergyFlowErrorSensor(_BaseFlowSensor):
    _attr_icon = "mdi:delta"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Solar Energy Flow Error", "error")

    @property
    def native_value(self):
        return self.coordinator.data.error


class SolarEnergyFlowStatusSensor(_BaseFlowSensor):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Solar Energy Flow Status", "status")

    @property
    def native_value(self):
        return self.coordinator.data.status

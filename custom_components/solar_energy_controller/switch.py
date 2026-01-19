from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLED,
    CONF_GRID_LIMITER_ENABLED,
    CONF_RATE_LIMITER_ENABLED,
    DEFAULT_ENABLED,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_RATE_LIMITER_ENABLED,
    DOMAIN,
)
from .coordinator import SolarEnergyFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SolarEnergyFlowEnabledSwitch(coordinator, entry),
            SolarEnergyFlowGridLimiterSwitch(coordinator, entry),
            SolarEnergyFlowRateLimiterSwitch(coordinator, entry),
        ]
    )


class SolarEnergyFlowEnabledSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Enabled"

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(CONF_ENABLED, DEFAULT_ENABLED))

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_update_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_update_enabled(False)

    async def _async_update_enabled(self, enabled: bool) -> None:
        options = dict(self._entry.options)
        options[CONF_ENABLED] = enabled

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()


class SolarEnergyFlowRateLimiterSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Rate limiter"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_rate_limiter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(CONF_RATE_LIMITER_ENABLED, DEFAULT_RATE_LIMITER_ENABLED))

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_update_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_update_state(False)

    async def _async_update_state(self, enabled: bool) -> None:
        options = dict(self._entry.options)
        options[CONF_RATE_LIMITER_ENABLED] = enabled
        options.setdefault(CONF_ENABLED, DEFAULT_ENABLED)

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()


class SolarEnergyFlowGridLimiterSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Grid limiter enabled"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_grid_limiter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(CONF_GRID_LIMITER_ENABLED, DEFAULT_GRID_LIMITER_ENABLED))

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_update_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_update_state(False)

    async def _async_update_state(self, enabled: bool) -> None:
        options = dict(self._entry.options)
        options[CONF_GRID_LIMITER_ENABLED] = enabled
        options.setdefault(CONF_ENABLED, DEFAULT_ENABLED)

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()

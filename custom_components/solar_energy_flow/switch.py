from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLED,
    CONF_GRID_LIMITER_ENABLED,
    CONF_RATE_LIMITER_ENABLED,
    DEFAULT_ENABLED,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_RATE_LIMITER_ENABLED,
    DOMAIN,
    HUB_DEVICE_SUFFIX,
    PID_DEVICE_SUFFIX,
    DIVIDER_DEVICE_SUFFIX,
    CONF_CONSUMERS,
    CONSUMER_ID,
    CONSUMER_NAME,
    CONSUMER_DEVICE_SUFFIX,
    CONSUMER_TYPE,
    CONSUMER_TYPE_CONTROLLED,
)
from .consumer_bindings import ConsumerBinding, get_consumer_binding
from .coordinator import SolarEnergyFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    consumers = list(entry.options.get(CONF_CONSUMERS, []))

    entities: list[SwitchEntity] = [
        SolarEnergyFlowEnabledSwitch(coordinator, entry),
        SolarEnergyFlowGridLimiterSwitch(coordinator, entry),
        SolarEnergyFlowRateLimiterSwitch(coordinator, entry),
    ]

    for consumer in consumers:
        entities.append(SolarEnergyFlowConsumerSwitch(entry, consumer))

    async_add_entities(entities)

    entry.async_on_unload(
        entry.add_update_listener(_async_reload_on_consumer_change(consumers))
    )


def _async_reload_on_consumer_change(initial_consumers: list[dict[str, Any]]):
    async def _reload_if_needed(hass: HomeAssistant, updated_entry: ConfigEntry):
        if initial_consumers != updated_entry.options.get(CONF_CONSUMERS, []):
            await hass.config_entries.async_reload(updated_entry.entry_id)

    return _reload_if_needed


class SolarEnergyFlowEnabledSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Enabled"

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
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


class SolarEnergyFlowConsumerSwitch(RestoreEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Enabled"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, consumer: dict[str, Any]) -> None:
        self._entry = entry
        self._consumer = consumer
        self._is_on: bool = False
        self._binding: ConsumerBinding | None = None
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{consumer[CONSUMER_ID]}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{consumer[CONSUMER_ID]}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}"),
            name=consumer.get(CONSUMER_NAME, "Consumer"),
            manufacturer="Solar Energy Flow",
            model="Energy Divider Consumer",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._binding = get_consumer_binding(self.hass, self._entry.entry_id, self._consumer)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == "on"
        elif self._binding is not None:
            actual_state = self._binding.get_effective_enabled(self.hass)
            if actual_state is not None:
                self._is_on = actual_state

    @property
    def is_on(self) -> bool:
        if self._binding is not None:
            actual_state = self._binding.get_effective_enabled(self.hass)
            if actual_state is not None:
                self._is_on = actual_state
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        self._is_on = enabled
        if self._binding is None:
            self.async_write_ha_state()
            return

        await self._binding.async_set_enabled(self.hass, enabled)
        actual_state = self._binding.get_effective_enabled(self.hass)
        self._is_on = enabled if actual_state is None else actual_state

        if self._consumer.get(CONSUMER_TYPE) == CONSUMER_TYPE_CONTROLLED:
            await self._binding.async_push_power(self.hass)

        self.async_write_ha_state()


class SolarEnergyFlowRateLimiterSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Rate limiter"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SolarEnergyFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_rate_limiter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
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
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
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

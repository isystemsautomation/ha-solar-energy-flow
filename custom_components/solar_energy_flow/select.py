from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLED,
    CONF_GRID_LIMITER_DEADBAND_W,
    CONF_GRID_LIMITER_ENABLED,
    CONF_GRID_LIMITER_LIMIT_W,
    CONF_GRID_LIMITER_TYPE,
    CONF_PID_DEADBAND,
    CONF_RUNTIME_MODE,
    CONF_MANUAL_SP_VALUE,
    CONF_MANUAL_OUT_VALUE,
    DEFAULT_ENABLED,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_PID_DEADBAND,
    DEFAULT_GRID_LIMITER_TYPE,
    DEFAULT_RUNTIME_MODE,
    DEFAULT_MANUAL_SP_VALUE,
    DEFAULT_MANUAL_OUT_VALUE,
    DOMAIN,
    GRID_LIMITER_TYPE_EXPORT,
    GRID_LIMITER_TYPE_IMPORT,
    RUNTIME_MODE_AUTO_SP,
    RUNTIME_MODE_HOLD,
    RUNTIME_MODE_MANUAL_OUT,
    RUNTIME_MODE_MANUAL_SP,
    HUB_DEVICE_SUFFIX,
    PID_DEVICE_SUFFIX,
)
from .coordinator import SolarEnergyFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SolarEnergyFlowSelect(
                coordinator,
                entry,
                CONF_GRID_LIMITER_TYPE,
                "Grid limiter type",
                [GRID_LIMITER_TYPE_IMPORT, GRID_LIMITER_TYPE_EXPORT],
                DEFAULT_GRID_LIMITER_TYPE,
                EntityCategory.CONFIG,
            ),
            SolarEnergyFlowSelect(
                coordinator,
                entry,
                CONF_RUNTIME_MODE,
                "Runtime mode",
                [RUNTIME_MODE_AUTO_SP, RUNTIME_MODE_MANUAL_SP, RUNTIME_MODE_HOLD, RUNTIME_MODE_MANUAL_OUT],
                DEFAULT_RUNTIME_MODE,
                None,
            ),
        ]
    )


class SolarEnergyFlowSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarEnergyFlowCoordinator,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        options: list[str],
        default: str,
        entity_category: EntityCategory | None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._option_key = option_key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{option_key}"
        self._attr_options = options
        self._attr_entity_category = entity_category
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}"),
            name=f"{entry.title} PID Controller",
            manufacturer="Solar Energy Flow",
            model="PID Controller",
        )

    @property
    def current_option(self) -> str | None:
        value = self._entry.options.get(self._option_key, self._default)
        if value in self._attr_options:
            return value
        return self._default

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return

        options = dict(self._entry.options)
        options.setdefault(CONF_ENABLED, DEFAULT_ENABLED)
        options.setdefault(CONF_GRID_LIMITER_ENABLED, DEFAULT_GRID_LIMITER_ENABLED)
        options.setdefault(CONF_GRID_LIMITER_LIMIT_W, DEFAULT_GRID_LIMITER_LIMIT_W)
        options.setdefault(CONF_GRID_LIMITER_DEADBAND_W, DEFAULT_GRID_LIMITER_DEADBAND_W)
        options.setdefault(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND)
        options.setdefault(CONF_RUNTIME_MODE, DEFAULT_RUNTIME_MODE)

        if self._option_key == CONF_GRID_LIMITER_TYPE and option not in (
            GRID_LIMITER_TYPE_IMPORT,
            GRID_LIMITER_TYPE_EXPORT,
        ):
            option = DEFAULT_GRID_LIMITER_TYPE
        previous_runtime_mode = self.coordinator.get_runtime_mode()

        options[self._option_key] = option

        if (
            self._option_key == CONF_RUNTIME_MODE
            and option == RUNTIME_MODE_MANUAL_SP
            and previous_runtime_mode != RUNTIME_MODE_MANUAL_SP
        ):
            manual_sp = self.coordinator.set_manual_sp_from_normal_setpoint()
            if manual_sp is not None:
                options[CONF_MANUAL_SP_VALUE] = manual_sp
            else:
                options.pop(CONF_MANUAL_SP_VALUE, None)
                await self.coordinator.async_reset_manual_sp()

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()

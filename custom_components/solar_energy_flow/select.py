from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLED,
    CONF_GRID_LIMITER_DEADBAND_W,
    CONF_GRID_LIMITER_ENABLED,
    CONF_GRID_LIMITER_LIMIT_W,
    CONF_GRID_LIMITER_TYPE,
    CONF_PID_DEADBAND,
    DEFAULT_ENABLED,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_PID_DEADBAND,
    DEFAULT_GRID_LIMITER_TYPE,
    DOMAIN,
    GRID_LIMITER_TYPE_EXPORT,
    GRID_LIMITER_TYPE_IMPORT,
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
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._option_key = option_key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{option_key}"
        self._attr_options = options
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
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

        if self._option_key == CONF_GRID_LIMITER_TYPE and option not in (
            GRID_LIMITER_TYPE_IMPORT,
            GRID_LIMITER_TYPE_EXPORT,
        ):
            option = DEFAULT_GRID_LIMITER_TYPE

        options[self._option_key] = option

        self.coordinator.apply_options(options)
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()

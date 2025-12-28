from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    DEFAULT_ENABLED,
    DEFAULT_KD,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_MIN_OUTPUT,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_PID_DEADBAND,
    DOMAIN,
)
from .coordinator import SolarEnergyFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolarEnergyFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

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
            None,
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
            None,
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
    ]

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
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

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    PLATFORMS,
    HUB_DEVICE_SUFFIX,
    PID_DEVICE_SUFFIX,
    DIVIDER_DEVICE_SUFFIX,
)
from .consumer_bindings import cleanup_consumer_bindings
from .coordinator import SolarEnergyFlowCoordinator
from .helpers import ENTRY_DATA_CONSUMER_RUNTIME, get_entry_data, set_entry_coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via YAML (not supported) or allow config flow to run."""
    # No YAML configuration is supported; return True so the config flow can be used.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SolarEnergyFlowCoordinator(hass, entry)
    entry_data = set_entry_coordinator(hass, entry.entry_id, coordinator)
    entry_data.setdefault(ENTRY_DATA_CONSUMER_RUNTIME, {})

    device_registry = dr.async_get(hass)
    hub_identifier = (DOMAIN, f"{entry.entry_id}_{HUB_DEVICE_SUFFIX}")
    pid_identifier = (DOMAIN, f"{entry.entry_id}_{PID_DEVICE_SUFFIX}")
    divider_identifier = (DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}")

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={hub_identifier},
        name="Solar Energy Flow",
        manufacturer="Solar Energy Flow",
        model="Hub",
    )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={pid_identifier},
        via_device=hub_identifier,
        name=f"{entry.title} PID Controller",
        manufacturer="Solar Energy Flow",
        model="PID Controller",
    )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={divider_identifier},
        via_device=hub_identifier,
        name=f"{entry.title} Energy Divider",
        manufacturer="Solar Energy Flow",
        model="Energy Divider",
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    entry_data = get_entry_data(hass, entry.entry_id)
    coordinator: SolarEnergyFlowCoordinator = entry_data["coordinator"]
    new_options = dict(entry.options)
    old_options = coordinator.options_cache

    if old_options == new_options:
        _LOGGER.debug("Options unchanged for %s; skipping handling", entry.entry_id)
        return

    coordinator.options_cache = new_options

    if coordinator.options_require_reload(old_options, new_options):
        _LOGGER.warning("Wiring change detected for %s; reloading entry", entry.entry_id)
        await hass.config_entries.async_reload(entry.entry_id)
        return

    coordinator.apply_options(new_options)
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        cleanup_consumer_bindings(hass, entry.entry_id)
    return unload_ok

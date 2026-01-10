from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DIVIDER_ENABLED,
    CONSUMER_DEVICE_SUFFIX,
    DEFAULT_DIVIDER_ENABLED,
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

    # Don't create hub device - it serves only as a reference for sub-devices but shouldn't appear in UI
    # PID Controller is created as a direct child of the config entry (no via_device)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={pid_identifier},
        name=f"{entry.title} PID Controller",
        manufacturer="Solar Energy Flow",
        model="PID Controller",
    )

    # Only create Divider device if divider is enabled, otherwise remove it if it exists
    divider_enabled = entry.options.get(CONF_DIVIDER_ENABLED, DEFAULT_DIVIDER_ENABLED)
    
    if divider_enabled:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={divider_identifier},
            name=f"{entry.title} Energy Divider",
            manufacturer="Solar Energy Flow",
            model="Energy Divider",
        )
    else:
        # Remove Divider device if it exists but divider is disabled
        divider_device = device_registry.async_get_device(identifiers={divider_identifier})
        if divider_device and entry.entry_id in divider_device.config_entries:
            try:
                device_registry.async_remove_device(divider_device.id)
            except Exception:
                _LOGGER.debug("Could not remove divider device %s, will be cleaned up later", divider_device.id)
        
        # Remove all consumer devices when divider is disabled
        # Iterate through all devices and check if they're consumer devices for this entry
        consumer_device_prefix = f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_"
        devices_to_remove = []
        
        for device in device_registry.devices.values():
            # Check if this device belongs to this config entry
            if entry.entry_id not in device.config_entries:
                continue
            
            # Check if this device is a consumer device
            # Consumer devices have identifiers like (DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{consumer_id}")
            for identifier_tuple in device.identifiers:
                if (
                    len(identifier_tuple) == 2
                    and identifier_tuple[0] == DOMAIN
                    and identifier_tuple[1].startswith(consumer_device_prefix)
                ):
                    devices_to_remove.append(device.id)
                    break
        
        # Remove consumer devices
        for device_id in devices_to_remove:
            try:
                device_registry.async_remove_device(device_id)
                _LOGGER.debug("Removed consumer device %s (divider disabled)", device_id)
            except Exception:
                _LOGGER.debug("Could not remove consumer device %s, will be cleaned up later", device_id)
    
    # Remove hub device if it exists (it shouldn't appear in UI since no entities attach to it directly)
    # PID and Divider devices are now direct children of the config entry, not the hub
    hub_device = device_registry.async_get_device(identifiers={hub_identifier})
    if hub_device and entry.entry_id in hub_device.config_entries:
        # Remove hub device if it exists (from old setup)
        # It will be automatically cleaned up when we reload
        try:
            device_registry.async_remove_device(hub_device.id)
        except Exception:
            # Device might still have references, will be cleaned up on next reload
            _LOGGER.debug("Could not remove hub device %s, will be cleaned up later", hub_device.id)

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

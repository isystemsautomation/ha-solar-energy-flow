from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import device_registry as dr
from homeassistant.components import lovelace

from .const import DOMAIN, PLATFORMS
from .coordinator import SolarEnergyFlowCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via YAML (not supported) or allow config flow to run."""
    _LOGGER.info("Solar Energy Flow: Initializing integration (async_setup called)")
    
    # Register static path for frontend resources
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    if os.path.isdir(frontend_path):
        hass.http.register_static_path(
            f"/{DOMAIN}/frontend", frontend_path, cache_headers=False
        )
        _LOGGER.info("Solar Energy Flow: Registered static path: /%s/frontend -> %s", DOMAIN, frontend_path)
    else:
        _LOGGER.warning("Solar Energy Flow: Frontend directory not found: %s", frontend_path)

    # Auto-register Lovelace resources on HA start
    async def register_resources(_event: Event) -> None:
        """Register custom card resources automatically."""
        _LOGGER.info("Attempting to register Lovelace resources for %s", DOMAIN)
        
        # Get version from manifest
        version = "0.1.2"
        try:
            import json
            manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    version = manifest.get("version", version)
        except Exception as err:
            _LOGGER.debug("Could not read version from manifest: %s", err)

        resources = [
            {
                "url": f"/{DOMAIN}/frontend/pid-controller-mini.js?v={version}",
                "type": "module",
            },
            {
                "url": f"/{DOMAIN}/frontend/pid-controller-popup.js?v={version}",
                "type": "module",
            },
        ]

        # Try to access Lovelace resources API
        try:
            # Check if lovelace module has resources
            if not hasattr(lovelace, "resources"):
                _LOGGER.warning(
                    "Lovelace resources API not found. Please add cards manually: "
                    "Settings → Dashboards → Resources. URLs: %s",
                    [r["url"] for r in resources]
                )
                return
            
            resources_api = lovelace.resources
            if not hasattr(resources_api, "async_create_item"):
                _LOGGER.warning(
                    "Lovelace resources.async_create_item not found. Please add cards manually: "
                    "Settings → Dashboards → Resources. URLs: %s",
                    [r["url"] for r in resources]
                )
                return

            # Get existing resources to avoid duplicates
            existing_resources = []
            try:
                existing_resources_list = await resources_api.async_get_info(hass)
                if existing_resources_list:
                    existing_resources = [
                        item.get("url", "") if isinstance(item, dict) else str(item)
                        for item in existing_resources_list
                        if item
                    ]
            except Exception as err:
                _LOGGER.debug("Could not get existing resources: %s", err)

            # Register resources if not already present
            registered_count = 0
            for resource in resources:
                resource_url = resource["url"]
                if resource_url in existing_resources:
                    _LOGGER.debug("Lovelace resource already exists: %s", resource_url)
                    continue

                try:
                    await resources_api.async_create_item(
                        hass, {"url": resource_url, "type": resource["type"]}
                    )
                    _LOGGER.info(
                        "✓ Registered Lovelace resource: %s (%s)", resource_url, resource["type"]
                    )
                    registered_count += 1
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to register Lovelace resource %s: %s", resource_url, err
                    )
            
            if registered_count > 0:
                _LOGGER.info("Successfully registered %d Lovelace resource(s) for %s", registered_count, DOMAIN)
            else:
                _LOGGER.debug("All resources already registered or registration skipped")
                
        except Exception as err:
            _LOGGER.warning(
                "Error accessing Lovelace resources API: %s. Please add cards manually: "
                "Settings → Dashboards → Resources. URLs: %s",
                err, [r["url"] for r in resources]
            )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register_resources)

    # No YAML configuration is supported; return True so the config flow can be used.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SolarEnergyFlowCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Solar Energy Flow",
        model="PID Controller",
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: SolarEnergyFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
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
    return unload_ok

from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry, ConfigEntryError, ConfigEntryNotReady
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import device_registry as dr
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN, PLATFORMS
from .coordinator import SolarEnergyFlowCoordinator

_LOGGER = logging.getLogger(__name__)

type SolarEnergyControllerConfigEntry = ConfigEntry[SolarEnergyFlowCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.info("Solar Energy Controller: Initializing integration")
    
    version = "0.1.2"
    try:
        import json
        
        def read_manifest():
            manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        
        manifest = await hass.async_add_executor_job(read_manifest)
        if manifest:
            version = manifest.get("version", version)
    except Exception:
        pass
    
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    if os.path.isdir(frontend_path):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path=f"/{DOMAIN}/frontend",
                path=frontend_path,
                cache_headers=False
            )
        ])
        _LOGGER.info("Solar Energy Controller: Registered static path: /%s/frontend -> %s", DOMAIN, frontend_path)
    else:
        _LOGGER.warning("Solar Energy Controller: Frontend directory not found: %s", frontend_path)

    async def register_resources(_event: Event) -> None:
        _LOGGER.info("Attempting to register Lovelace resources for %s", DOMAIN)

        resources = [
            {
                "url": f"/{DOMAIN}/frontend/pid-controller-mini.js?v={version}",
                "res_type": "module",
            },
            {
                "url": f"/{DOMAIN}/frontend/pid-controller-popup.js?v={version}",
                "res_type": "module",
            },
        ]

        try:
            import asyncio
            await asyncio.sleep(1)
            
            lovelace_obj = None
            if hasattr(hass, "lovelace"):
                lovelace_obj = hass.lovelace
            elif "lovelace" in hass.data:
                lovelace_obj = hass.data["lovelace"]
            if not lovelace_obj:
                _LOGGER.warning(
                    "Lovelace not available. Please add cards manually: "
                    "Settings → Dashboards → Resources. URLs: %s",
                    [r["url"] for r in resources]
                )
                return
            
            lovelace_mode = getattr(lovelace_obj, "mode", None)
            if lovelace_mode != "storage":
                _LOGGER.info(
                    "Lovelace is in %s mode. Auto-registration only works in storage mode. "
                    "Please add cards manually: %s",
                    lovelace_mode, [r["url"] for r in resources]
                )
                return
            
            existing_resources = []
            try:
                resources_api = lovelace_obj.resources
                existing_items = resources_api.async_items()
                existing_resources = [
                    item.get("url", "") if isinstance(item, dict) else str(item)
                    for item in existing_items
                    if item
                ]
            except Exception as err:
                _LOGGER.debug("Could not get existing resources: %s", err)

            registered_count = 0
            for resource in resources:
                resource_url = resource["url"]
                url_base = resource_url.split("?")[0]
                if any(url_base in existing for existing in existing_resources):
                    _LOGGER.debug("Lovelace resource already exists: %s", url_base)
                    continue

                try:
                    await resources_api.async_create_item(
                        {"url": resource_url, "res_type": resource["res_type"]}
                    )
                    _LOGGER.info(
                        "✓ Registered Lovelace resource: %s (%s)", resource_url, resource["res_type"]
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
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SolarEnergyControllerConfigEntry) -> bool:
    """Set up Solar Energy Controller from a config entry."""
    from .const import (
        CONF_PROCESS_VALUE_ENTITY,
        CONF_SETPOINT_ENTITY,
        CONF_OUTPUT_ENTITY,
        CONF_GRID_POWER_ENTITY,
    )

    # Validate that all required entities exist and are accessible
    # Check both entry.data and entry.options (entities can be in either)
    required_entities = {
        CONF_PROCESS_VALUE_ENTITY: entry.options.get(CONF_PROCESS_VALUE_ENTITY) or entry.data.get(CONF_PROCESS_VALUE_ENTITY),
        CONF_SETPOINT_ENTITY: entry.options.get(CONF_SETPOINT_ENTITY) or entry.data.get(CONF_SETPOINT_ENTITY),
        CONF_OUTPUT_ENTITY: entry.options.get(CONF_OUTPUT_ENTITY) or entry.data.get(CONF_OUTPUT_ENTITY),
        CONF_GRID_POWER_ENTITY: entry.options.get(CONF_GRID_POWER_ENTITY) or entry.data.get(CONF_GRID_POWER_ENTITY),
    }

    missing_entities = []
    unavailable_entities = []

    for key, entity_id in required_entities.items():
        if not entity_id:
            missing_entities.append(key)
            continue

        if entity_id not in hass.states:
            missing_entities.append(key)
        else:
            state = hass.states[entity_id]
            if state.state in ("unavailable", "unknown"):
                unavailable_entities.append(key)

    if missing_entities:
        entity_names = {
            CONF_PROCESS_VALUE_ENTITY: "Process Value",
            CONF_SETPOINT_ENTITY: "Setpoint",
            CONF_OUTPUT_ENTITY: "Output",
            CONF_GRID_POWER_ENTITY: "Grid Power",
        }
        missing_names = [entity_names[key] for key in missing_entities]
        raise ConfigEntryError(
            f"Required entities not found: {', '.join(missing_names)}. "
            "Please check your configuration and ensure all entities exist."
        )

    if unavailable_entities:
        entity_names = {
            CONF_PROCESS_VALUE_ENTITY: "Process Value",
            CONF_SETPOINT_ENTITY: "Setpoint",
            CONF_OUTPUT_ENTITY: "Output",
            CONF_GRID_POWER_ENTITY: "Grid Power",
        }
        unavailable_names = [entity_names[key] for key in unavailable_entities]
        raise ConfigEntryNotReady(
            f"Required entities are unavailable: {', '.join(unavailable_names)}. "
            "Please ensure the entities are working and try again."
        )

    coordinator = SolarEnergyFlowCoordinator(hass, entry)
    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Solar Energy Controller",
        model="PID Controller",
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to initialize coordinator: {err}") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    return True


async def _update_listener(hass: HomeAssistant, entry: SolarEnergyControllerConfigEntry) -> None:
    coordinator = entry.runtime_data
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


async def async_unload_entry(hass: HomeAssistant, entry: SolarEnergyControllerConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok

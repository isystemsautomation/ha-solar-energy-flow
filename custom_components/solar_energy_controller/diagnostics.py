"""Diagnostics support for Solar Energy Controller."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SolarEnergyFlowCoordinator

type SolarEnergyControllerConfigEntry = ConfigEntry[SolarEnergyFlowCoordinator]

# No sensitive information to redact - entity IDs are not considered sensitive
# and there are no passwords, tokens, or coordinates in this integration
TO_REDACT: list[str] = []


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolarEnergyControllerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SolarEnergyFlowCoordinator = entry.runtime_data

    # Get current state data
    current_data = None
    if coordinator.data:
        current_data = {
            "pv": coordinator.data.pv,
            "sp": coordinator.data.sp,
            "grid_power": coordinator.data.grid_power,
            "out": coordinator.data.out,
            "output_pre_rate_limit": coordinator.data.output_pre_rate_limit,
            "error": coordinator.data.error,
            "enabled": coordinator.data.enabled,
            "status": coordinator.data.status,
            "limiter_state": coordinator.data.limiter_state,
            "runtime_mode": coordinator.data.runtime_mode,
            "manual_sp_value": coordinator.data.manual_sp_value,
            "manual_out_value": coordinator.data.manual_out_value,
            "manual_sp_display_value": coordinator.data.manual_sp_display_value,
            "p_term": coordinator.data.p_term,
            "i_term": coordinator.data.i_term,
            "d_term": coordinator.data.d_term,
        }

    # Get runtime options
    runtime_options = None
    try:
        options = coordinator._build_runtime_options()
        runtime_options = {
            "enabled": options.enabled,
            "min_output": options.min_output,
            "max_output": options.max_output,
            "pv_min": options.pv_min,
            "pv_max": options.pv_max,
            "sp_min": options.sp_min,
            "sp_max": options.sp_max,
            "grid_min": options.grid_min,
            "grid_max": options.grid_max,
            "invert_pv": options.invert_pv,
            "grid_power_invert": options.grid_power_invert,
            "limiter_enabled": options.limiter_enabled,
            "limiter_type": options.limiter_type,
            "limiter_limit_w": options.limiter_limit_w,
            "limiter_deadband_w": options.limiter_deadband_w,
            "rate_limiter_enabled": options.rate_limiter_enabled,
            "rate_limit": options.rate_limit,
            "pid_deadband": options.pid_deadband,
            "pid_mode": options.pid_mode,
            "runtime_mode": options.runtime_mode,
            "max_output_step": options.max_output_step,
            "output_epsilon": options.output_epsilon,
        }
    except Exception:
        pass

    # Get PID configuration
    pid_config = None
    try:
        pid_cfg = coordinator.pid.cfg
        pid_config = {
            "kp": pid_cfg.kp,
            "ki": pid_cfg.ki,
            "kd": pid_cfg.kd,
            "min_output": pid_cfg.min_output,
            "max_output": pid_cfg.max_output,
        }
    except Exception:
        pass

    # Get PID internal state
    pid_state = None
    try:
        pid_state = {
            "integral": coordinator.pid._integral,
            "prev_pv": coordinator.pid._prev_pv,
            "prev_t": coordinator.pid._prev_t,  # This is a float (time.monotonic()), not a datetime
            "prev_error": coordinator.pid._prev_error,
        }
    except Exception:
        pass

    # Get coordinator metadata
    coordinator_info = {
        "update_interval": str(coordinator.update_interval),
        "last_update_success": coordinator.last_update_success,
        "last_update_time": coordinator.last_update_time.isoformat() if coordinator.last_update_time else None,
    }

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "state": entry.state.value if hasattr(entry.state, "value") else str(entry.state),
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": coordinator_info,
        "current_state": current_data,
        "runtime_options": runtime_options,
        "pid_config": pid_config,
        "pid_state": pid_state,
    }


"""Test diagnostics support for Solar Energy Controller."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.solar_energy_controller import DOMAIN
from custom_components.solar_energy_controller.const import (
    CONF_GRID_MAX,
    CONF_GRID_MIN,
    CONF_GRID_POWER_ENTITY,
    CONF_KP,
    CONF_KI,
    CONF_KD,
    CONF_MAX_OUTPUT,
    CONF_MIN_OUTPUT,
    CONF_OUTPUT_ENTITY,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_PV_MAX,
    CONF_PV_MIN,
    CONF_SETPOINT_ENTITY,
    CONF_SP_MAX,
    CONF_SP_MIN,
    DEFAULT_GRID_MAX,
    DEFAULT_GRID_MIN,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_KD,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_MIN_OUTPUT,
    DEFAULT_PV_MAX,
    DEFAULT_PV_MIN,
    DEFAULT_SP_MAX,
    DEFAULT_SP_MIN,
    RUNTIME_MODE_AUTO_SP,
)
from custom_components.solar_energy_controller.diagnostics import async_get_config_entry_diagnostics
from custom_components.solar_energy_controller.coordinator import SolarEnergyFlowCoordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.title = "Test Controller"
    entry.state = ConfigEntryState.LOADED
    entry.data = {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
        CONF_SETPOINT_ENTITY: "number.setpoint",
        CONF_OUTPUT_ENTITY: "number.output",
        CONF_GRID_POWER_ENTITY: "sensor.grid_power",
    }
    entry.options = {
        CONF_KP: DEFAULT_KP,
        CONF_KI: DEFAULT_KI,
        CONF_KD: DEFAULT_KD,
        CONF_MIN_OUTPUT: DEFAULT_MIN_OUTPUT,
        CONF_MAX_OUTPUT: DEFAULT_MAX_OUTPUT,
        CONF_PV_MIN: DEFAULT_PV_MIN,
        CONF_PV_MAX: DEFAULT_PV_MAX,
        CONF_SP_MIN: DEFAULT_SP_MIN,
        CONF_SP_MAX: DEFAULT_SP_MAX,
        CONF_GRID_MIN: DEFAULT_GRID_MIN,
        CONF_GRID_MAX: DEFAULT_GRID_MAX,
    }
    return entry


@pytest.fixture
def mock_coordinator(mock_entry):
    """Create a mock coordinator with data."""
    coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    
    # Mock FlowState data
    from custom_components.solar_energy_controller.coordinator import FlowState
    mock_data = FlowState(
        pv=50.0,
        sp=60.0,
        grid_power=100.0,
        out=55.0,
        output_pre_rate_limit=55.0,
        error=10.0,
        enabled=True,
        status="running",
        limiter_state="normal",
        runtime_mode=RUNTIME_MODE_AUTO_SP,
        manual_sp_value=None,
        manual_out_value=55.0,
        manual_sp_display_value=None,
        manual_out_display_value=55.0,
        p_term=5.0,
        i_term=3.0,
        d_term=2.0,
    )
    coordinator.data = mock_data
    
    # Mock runtime options
    from custom_components.solar_energy_controller.coordinator import RuntimeOptions
    mock_options = RuntimeOptions(
        enabled=True,
        min_output=DEFAULT_MIN_OUTPUT,
        max_output=DEFAULT_MAX_OUTPUT,
        pv_min=DEFAULT_PV_MIN,
        pv_max=DEFAULT_PV_MAX,
        sp_min=DEFAULT_SP_MIN,
        sp_max=DEFAULT_SP_MAX,
        grid_min=DEFAULT_GRID_MIN,
        grid_max=DEFAULT_GRID_MAX,
        invert_pv=False,
        grid_power_invert=False,
        limiter_enabled=False,
        limiter_type="import",
        limiter_limit_w=1000.0,
        limiter_deadband_w=50.0,
        rate_limiter_enabled=False,
        rate_limit=10.0,
        pid_deadband=0.0,
        pid_mode="direct",
        runtime_mode=RUNTIME_MODE_AUTO_SP,
        max_output_step=100.0,
        output_epsilon=1.0,
    )
    coordinator._build_runtime_options = MagicMock(return_value=mock_options)
    
    # Mock PID
    from custom_components.solar_energy_controller.pid import PIDConfig
    mock_pid = MagicMock()
    mock_pid.cfg = PIDConfig(
        kp=DEFAULT_KP,
        ki=DEFAULT_KI,
        kd=DEFAULT_KD,
        min_output=0.0,
        max_output=100.0,
    )
    mock_pid._integral = 3.0
    mock_pid._prev_pv = 50.0
    mock_pid._prev_t = 123456.789
    mock_pid._prev_error = 10.0
    coordinator.pid = mock_pid
    
    # Mock coordinator metadata
    coordinator.update_interval = 10
    coordinator.last_update_success = True
    from datetime import datetime
    coordinator.last_update_time = datetime(2024, 1, 1, 12, 0, 0)
    
    return coordinator


async def test_diagnostics_with_data(hass: HomeAssistant, mock_entry, mock_coordinator) -> None:
    """Test diagnostics with coordinator data."""
    mock_entry.runtime_data = mock_coordinator
    
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    
    assert "entry" in result
    assert result["entry"]["entry_id"] == "test_entry_123"
    assert result["entry"]["title"] == "Test Controller"
    assert result["entry"]["state"] == "loaded"
    assert "data" in result["entry"]
    assert "options" in result["entry"]
    
    assert "coordinator" in result
    assert result["coordinator"]["update_interval"] == "10"
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["last_update_time"] is not None
    
    assert "current_state" in result
    assert result["current_state"]["pv"] == 50.0
    assert result["current_state"]["sp"] == 60.0
    assert result["current_state"]["out"] == 55.0
    assert result["current_state"]["error"] == 10.0
    assert result["current_state"]["status"] == "running"
    assert result["current_state"]["runtime_mode"] == RUNTIME_MODE_AUTO_SP
    
    assert "runtime_options" in result
    assert result["runtime_options"]["enabled"] is True
    assert result["runtime_options"]["min_output"] == DEFAULT_MIN_OUTPUT
    assert result["runtime_options"]["max_output"] == DEFAULT_MAX_OUTPUT
    
    assert "pid_config" in result
    assert result["pid_config"]["kp"] == DEFAULT_KP
    assert result["pid_config"]["ki"] == DEFAULT_KI
    assert result["pid_config"]["kd"] == DEFAULT_KD
    
    assert "pid_state" in result
    assert result["pid_state"]["integral"] == 3.0
    assert result["pid_state"]["prev_pv"] == 50.0
    assert result["pid_state"]["prev_t"] == 123456.789
    assert result["pid_state"]["prev_error"] == 10.0


async def test_diagnostics_without_data(hass: HomeAssistant, mock_entry, mock_coordinator) -> None:
    """Test diagnostics when coordinator has no data."""
    mock_coordinator.data = None
    mock_entry.runtime_data = mock_coordinator
    
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    
    assert "current_state" in result
    assert result["current_state"] is None
    
    # Other sections should still be present
    assert "entry" in result
    assert "coordinator" in result
    assert "runtime_options" in result
    assert "pid_config" in result
    assert "pid_state" in result


async def test_diagnostics_runtime_options_exception(hass: HomeAssistant, mock_entry, mock_coordinator) -> None:
    """Test diagnostics when _build_runtime_options raises an exception."""
    mock_coordinator._build_runtime_options = MagicMock(side_effect=Exception("Test error"))
    mock_entry.runtime_data = mock_coordinator
    
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    
    # Should handle exception gracefully
    assert "runtime_options" in result
    assert result["runtime_options"] is None


async def test_diagnostics_pid_config_exception(hass: HomeAssistant, mock_entry, mock_coordinator) -> None:
    """Test diagnostics when PID config access raises an exception."""
    mock_coordinator.pid = None
    mock_entry.runtime_data = mock_coordinator
    
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    
    # Should handle exception gracefully
    assert "pid_config" in result
    assert result["pid_config"] is None
    assert result["pid_state"] is None


async def test_diagnostics_pid_state_exception(hass: HomeAssistant, mock_entry, mock_coordinator) -> None:
    """Test diagnostics when PID state access raises an exception."""
    # Make pid._integral raise AttributeError
    del mock_coordinator.pid._integral
    mock_entry.runtime_data = mock_coordinator
    
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    
    # Should handle exception gracefully
    assert "pid_state" in result
    assert result["pid_state"] is None


async def test_diagnostics_data_redaction(hass: HomeAssistant, mock_entry, mock_coordinator) -> None:
    """Test that diagnostics properly redacts sensitive data."""
    mock_entry.runtime_data = mock_coordinator
    
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    
    # Entry data and options should be redacted (though TO_REDACT is empty in this integration)
    assert "data" in result["entry"]
    assert "options" in result["entry"]
    # Since TO_REDACT is empty, data should be unchanged
    assert result["entry"]["data"] == mock_entry.data


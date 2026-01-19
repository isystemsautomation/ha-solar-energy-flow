"""Test sensor entities."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.solar_energy_controller.sensor import (
    SolarEnergyFlowDTermSensor,
    SolarEnergyFlowEffectiveSPSensor,
    SolarEnergyFlowErrorSensor,
    SolarEnergyFlowGridPowerSensor,
    SolarEnergyFlowITermSensor,
    SolarEnergyFlowLimiterStateSensor,
    SolarEnergyFlowOutputPreRateLimitSensor,
    SolarEnergyFlowOutputSensor,
    SolarEnergyFlowPTermSensor,
    SolarEnergyFlowPVValueSensor,
    SolarEnergyFlowStatusSensor,
    async_setup_entry,
)
from custom_components.solar_energy_controller.coordinator import SolarEnergyFlowCoordinator
from custom_components.solar_energy_controller.const import DOMAIN


@dataclass
class MockFlowState:
    """Mock FlowState for testing."""
    pv: float | None = None
    sp: float | None = None
    out: float | None = None
    error: float | None = None
    status: str | None = None
    grid_power: float | None = None
    p_term: float | None = None
    i_term: float | None = None
    d_term: float | None = None
    limiter_state: str | None = None
    output_pre_rate_limit: float | None = None


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    # Set data as a property that can be accessed
    mock_data = MockFlowState(
        pv=50.0,
        sp=60.0,
        out=55.0,
        error=10.0,
        status="running",
        grid_power=100.0,
        p_term=5.0,
        i_term=3.0,
        d_term=2.0,
        limiter_state="normal",
        output_pre_rate_limit=55.0,
    )
    type(coordinator).data = mock_data
    # CoordinatorEntity requires last_update_success
    coordinator.last_update_success = True
    coordinator._build_runtime_options = MagicMock(return_value=MagicMock(
        enabled=True,
        runtime_mode="AUTO SP",
    ))
    coordinator.get_manual_out_value = MagicMock(return_value=55.0)
    coordinator.get_manual_sp_value = MagicMock(return_value=60.0)
    return coordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.title = "Test Controller"
    entry.options = {
        "kp": 1.0,
        "ki": 0.1,
        "kd": 0.0,
        "min_output": 0.0,
        "max_output": 100.0,
        "pid_deadband": 0.0,
    }
    return entry


def test_effective_sp_sensor(mock_coordinator, mock_entry):
    """Test Effective SP sensor."""
    sensor = SolarEnergyFlowEffectiveSPSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Effective SP"
    assert sensor.available is True
    assert sensor.native_value == 60.0
    
    # Test with None data
    type(mock_coordinator).data = MockFlowState(sp=None)
    assert sensor.available is False
    assert sensor.native_value is None


def test_pv_value_sensor(mock_coordinator, mock_entry):
    """Test PV value sensor."""
    sensor = SolarEnergyFlowPVValueSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "PV value"
    assert sensor.available is True
    assert sensor.native_value == 50.0
    
    # Test with None data
    type(mock_coordinator).data = MockFlowState(pv=None)
    assert sensor.available is False
    assert sensor.native_value is None


def test_output_sensor(mock_coordinator, mock_entry):
    """Test Output sensor."""
    sensor = SolarEnergyFlowOutputSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Output"
    assert sensor.available is True
    assert sensor.native_value == 55.0
    
    # Test with None data
    type(mock_coordinator).data = MockFlowState(out=None)
    assert sensor.available is False
    assert sensor.native_value is None


def test_error_sensor(mock_coordinator, mock_entry):
    """Test Error sensor."""
    sensor = SolarEnergyFlowErrorSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Error"
    assert sensor.available is True
    assert sensor.native_value == 10.0
    
    # Error can be None, but sensor should still be available
    type(mock_coordinator).data = MockFlowState(error=None)
    assert sensor.available is True
    assert sensor.native_value is None


def test_status_sensor(mock_coordinator, mock_entry):
    """Test Status sensor."""
    sensor = SolarEnergyFlowStatusSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Status"
    assert sensor.available is True
    assert sensor.native_value == "running"
    
    # Test extra_state_attributes
    attrs = sensor.extra_state_attributes
    assert "enabled" in attrs
    assert "runtime_mode" in attrs
    assert "pv_value" in attrs
    assert "output" in attrs


def test_grid_power_sensor(mock_coordinator, mock_entry):
    """Test Grid power sensor."""
    sensor = SolarEnergyFlowGridPowerSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Grid power"
    assert sensor.available is True
    assert sensor.native_value == 100.0


def test_p_term_sensor(mock_coordinator, mock_entry):
    """Test P term sensor."""
    sensor = SolarEnergyFlowPTermSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "P term"
    assert sensor.available is True
    assert sensor.native_value == 5.0


def test_i_term_sensor(mock_coordinator, mock_entry):
    """Test I term sensor."""
    sensor = SolarEnergyFlowITermSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "I term"
    assert sensor.available is True
    assert sensor.native_value == 3.0


def test_d_term_sensor(mock_coordinator, mock_entry):
    """Test D term sensor."""
    sensor = SolarEnergyFlowDTermSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "D term"
    assert sensor.available is True
    assert sensor.native_value == 2.0


def test_limiter_state_sensor(mock_coordinator, mock_entry):
    """Test Limiter state sensor."""
    sensor = SolarEnergyFlowLimiterStateSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Limiter state"
    assert sensor.available is True
    assert sensor.native_value == "normal"


def test_output_pre_rate_limit_sensor(mock_coordinator, mock_entry):
    """Test Output (pre rate limit) sensor."""
    sensor = SolarEnergyFlowOutputPreRateLimitSensor(mock_coordinator, mock_entry)
    
    assert sensor._attr_name == "Output (pre rate limit)"
    assert sensor.available is True
    assert sensor.native_value == 55.0


async def test_async_setup_entry(hass: HomeAssistant, mock_entry):
    """Test async_setup_entry for sensors."""
    mock_coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    mock_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, mock_add_entities)
    
    # Verify entities are created
    assert mock_add_entities.called
    call_args = mock_add_entities.call_args[0][0]
    assert len(call_args) == 11  # Should create 11 sensor entities


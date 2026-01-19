"""Test number entities."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.solar_energy_controller.const import (
    CONF_KP,
    CONF_MANUAL_OUT_VALUE,
    CONF_MANUAL_SP_VALUE,
    CONF_MAX_OUTPUT,
    CONF_MIN_OUTPUT,
    CONF_RUNTIME_MODE,
    DEFAULT_KP,
    DEFAULT_MANUAL_OUT_VALUE,
    DEFAULT_MANUAL_SP_VALUE,
    RUNTIME_MODE_AUTO_SP,
    RUNTIME_MODE_MANUAL_OUT,
    RUNTIME_MODE_MANUAL_SP,
)
from custom_components.solar_energy_controller.coordinator import SolarEnergyFlowCoordinator
from custom_components.solar_energy_controller.number import (
    SolarEnergyFlowManualNumber,
    SolarEnergyFlowNumber,
    async_setup_entry,
)


@dataclass
class MockFlowState:
    """Mock FlowState for testing."""
    manual_sp_value: float | None = None
    manual_out_value: float | None = None
    manual_sp_display_value: float | None = None


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    coordinator.data = MockFlowState(
        manual_sp_value=60.0,
        manual_out_value=55.0,
        manual_sp_display_value=60.0,
    )
    coordinator.apply_options = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.get_runtime_mode = MagicMock(return_value=RUNTIME_MODE_AUTO_SP)
    coordinator.get_manual_sp_value = MagicMock(return_value=60.0)
    coordinator.get_manual_out_value = MagicMock(return_value=55.0)
    coordinator.async_set_manual_sp = AsyncMock()
    coordinator.async_set_manual_out = AsyncMock()
    coordinator.async_snap_back_manual_sp = AsyncMock()
    coordinator.async_snap_back_manual_out = AsyncMock()
    return coordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.title = "Test Controller"
    entry.options = {CONF_KP: 1.0}
    entry.hass = MagicMock()
    entry.hass.config_entries = MagicMock()
    entry.hass.config_entries.async_update_entry = AsyncMock()
    return entry


def test_number_entity_native_value(mock_coordinator, mock_entry):
    """Test number entity native_value property."""
    number = SolarEnergyFlowNumber(
        mock_coordinator,
        mock_entry,
        CONF_KP,
        "Kp",
        DEFAULT_KP,
        0.001,
        0.0,
        1000.0,
        None,
    )
    
    assert number.native_value == 1.0
    
    # Test with missing option
    mock_entry.options = {}
    assert number.native_value == DEFAULT_KP


async def test_number_entity_set_value(mock_coordinator, mock_entry):
    """Test number entity set_native_value."""
    number = SolarEnergyFlowNumber(
        mock_coordinator,
        mock_entry,
        CONF_KP,
        "Kp",
        DEFAULT_KP,
        0.001,
        0.0,
        1000.0,
        None,
    )
    number.hass = mock_entry.hass
    
    await number.async_set_native_value(2.0)
    
    mock_coordinator.apply_options.assert_called_once()
    mock_entry.hass.config_entries.async_update_entry.assert_called_once()
    
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_KP] == 2.0


async def test_number_entity_min_max_adjustment(mock_coordinator, mock_entry):
    """Test number entity min/max auto-adjustment."""
    number = SolarEnergyFlowNumber(
        mock_coordinator,
        mock_entry,
        CONF_MIN_OUTPUT,
        "Min output",
        0.0,
        1.0,
        -20000.0,
        20000.0,
        None,
    )
    number.hass = mock_entry.hass
    mock_entry.options = {CONF_MAX_OUTPUT: 100.0}
    
    # Set min_output > max_output, should auto-adjust max
    await number.async_set_native_value(150.0)
    
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_MIN_OUTPUT] == 150.0
    assert call_args[CONF_MAX_OUTPUT] == 150.0


async def test_number_entity_error_handling(mock_coordinator, mock_entry):
    """Test number entity error handling."""
    number = SolarEnergyFlowNumber(
        mock_coordinator,
        mock_entry,
        CONF_KP,
        "Kp",
        DEFAULT_KP,
        0.001,
        0.0,
        1000.0,
        None,
    )
    number.hass = mock_entry.hass
    
    mock_coordinator.apply_options.side_effect = Exception("Test error")
    
    with pytest.raises(HomeAssistantError):
        await number.async_set_native_value(2.0)


def test_manual_number_native_value(mock_coordinator, mock_entry):
    """Test manual number entity native_value property."""
    number = SolarEnergyFlowManualNumber(
        mock_coordinator,
        mock_entry,
        CONF_MANUAL_SP_VALUE,
        "Manual SP",
        DEFAULT_MANUAL_SP_VALUE,
        1.0,
        -20000.0,
        20000.0,
    )
    
    assert number.native_value == 60.0
    
    # Test with None data - configure mock to return None for data attribute
    mock_coordinator.data = None
    # The number entity uses getattr(coordinator, "data", None), so we need to
    # ensure the mock returns None. Since we set it directly, getattr should work.
    # But if the entity cached it, we need to recreate the number entity
    number2 = SolarEnergyFlowManualNumber(
        mock_coordinator,
        mock_entry,
        CONF_MANUAL_SP_VALUE,
        "Manual SP",
        DEFAULT_MANUAL_SP_VALUE,
        1.0,
        -20000.0,
        20000.0,
    )
    assert number2.native_value == round(DEFAULT_MANUAL_SP_VALUE, 1)


async def test_manual_number_set_value_allowed(mock_coordinator, mock_entry):
    """Test manual number set_native_value when mode allows it."""
    number = SolarEnergyFlowManualNumber(
        mock_coordinator,
        mock_entry,
        CONF_MANUAL_SP_VALUE,
        "Manual SP",
        DEFAULT_MANUAL_SP_VALUE,
        1.0,
        -20000.0,
        20000.0,
    )
    number.hass = mock_entry.hass
    mock_coordinator.get_runtime_mode.return_value = RUNTIME_MODE_MANUAL_SP
    
    await number.async_set_native_value(70.0)
    
    mock_coordinator.async_set_manual_sp.assert_called_once_with(70.0)
    mock_coordinator.apply_options.assert_called_once()


async def test_manual_number_set_value_not_allowed(mock_coordinator, mock_entry):
    """Test manual number set_native_value when mode doesn't allow it."""
    number = SolarEnergyFlowManualNumber(
        mock_coordinator,
        mock_entry,
        CONF_MANUAL_SP_VALUE,
        "Manual SP",
        DEFAULT_MANUAL_SP_VALUE,
        1.0,
        -20000.0,
        20000.0,
    )
    number.hass = mock_entry.hass
    number.async_write_ha_state = MagicMock()
    mock_coordinator.get_runtime_mode.return_value = RUNTIME_MODE_AUTO_SP
    
    # Should raise ServiceValidationError when mode doesn't allow
    # Note: snap_back is not called because the exception is raised first
    with pytest.raises(ServiceValidationError):
        await number.async_set_native_value(70.0)
    
    # Exception is raised before snap_back, so it won't be called
    mock_coordinator.async_snap_back_manual_sp.assert_not_called()
    mock_coordinator.async_set_manual_sp.assert_not_called()


async def test_manual_number_set_value_validation_error(mock_coordinator, mock_entry):
    """Test manual number raises ServiceValidationError when mode doesn't allow."""
    number = SolarEnergyFlowManualNumber(
        mock_coordinator,
        mock_entry,
        CONF_MANUAL_SP_VALUE,
        "Manual SP",
        DEFAULT_MANUAL_SP_VALUE,
        1.0,
        -20000.0,
        20000.0,
    )
    number.hass = mock_entry.hass
    number.async_write_ha_state = MagicMock()
    mock_coordinator.get_runtime_mode.return_value = RUNTIME_MODE_AUTO_SP
    
    # The current implementation raises ServiceValidationError when mode doesn't allow
    with pytest.raises(ServiceValidationError):
        await number.async_set_native_value(70.0)


async def test_manual_out_number_set_value(mock_coordinator, mock_entry):
    """Test manual OUT number set_native_value."""
    number = SolarEnergyFlowManualNumber(
        mock_coordinator,
        mock_entry,
        CONF_MANUAL_OUT_VALUE,
        "Manual OUT",
        DEFAULT_MANUAL_OUT_VALUE,
        1.0,
        -20000.0,
        20000.0,
    )
    number.hass = mock_entry.hass
    mock_coordinator.get_runtime_mode.return_value = RUNTIME_MODE_MANUAL_OUT
    
    await number.async_set_native_value(80.0)
    
    mock_coordinator.async_set_manual_out.assert_called_once_with(80.0)


async def test_async_setup_entry(hass: HomeAssistant, mock_entry):
    """Test async_setup_entry for numbers."""
    mock_coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    mock_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, mock_add_entities)
    
    # Verify entities are created
    assert mock_add_entities.called
    call_args = mock_add_entities.call_args[0][0]
    assert len(call_args) == 11  # Should create 11 number entities (8 config + 2 manual + 1 rate limit)


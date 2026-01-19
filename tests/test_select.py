"""Test select entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.solar_energy_controller.const import (
    CONF_GRID_LIMITER_TYPE,
    CONF_RUNTIME_MODE,
    DEFAULT_GRID_LIMITER_TYPE,
    DEFAULT_RUNTIME_MODE,
    GRID_LIMITER_TYPE_EXPORT,
    GRID_LIMITER_TYPE_IMPORT,
    RUNTIME_MODE_AUTO_SP,
    RUNTIME_MODE_MANUAL_SP,
)
from custom_components.solar_energy_controller.coordinator import SolarEnergyFlowCoordinator
from custom_components.solar_energy_controller.select import (
    SolarEnergyFlowSelect,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    coordinator.apply_options = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.get_runtime_mode = MagicMock(return_value=RUNTIME_MODE_AUTO_SP)
    coordinator.set_manual_sp_from_normal_setpoint = MagicMock(return_value=60.0)
    coordinator.async_reset_manual_sp = AsyncMock()
    return coordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.title = "Test Controller"
    entry.options = {}
    entry.hass = MagicMock()
    entry.hass.config_entries = MagicMock()
    entry.hass.config_entries.async_update_entry = AsyncMock()
    return entry


def test_select_current_option(mock_coordinator, mock_entry):
    """Test select entity current_option property."""
    select = SolarEnergyFlowSelect(
        mock_coordinator,
        mock_entry,
        CONF_GRID_LIMITER_TYPE,
        "Grid limiter type",
        [GRID_LIMITER_TYPE_IMPORT, GRID_LIMITER_TYPE_EXPORT],
        DEFAULT_GRID_LIMITER_TYPE,
        None,
    )
    
    assert select.current_option == DEFAULT_GRID_LIMITER_TYPE
    
    mock_entry.options = {CONF_GRID_LIMITER_TYPE: GRID_LIMITER_TYPE_EXPORT}
    assert select.current_option == GRID_LIMITER_TYPE_EXPORT
    
    # Test with invalid option
    mock_entry.options = {CONF_GRID_LIMITER_TYPE: "invalid"}
    assert select.current_option == DEFAULT_GRID_LIMITER_TYPE


async def test_select_select_option_valid(mock_coordinator, mock_entry):
    """Test select entity select_option with valid option."""
    select = SolarEnergyFlowSelect(
        mock_coordinator,
        mock_entry,
        CONF_GRID_LIMITER_TYPE,
        "Grid limiter type",
        [GRID_LIMITER_TYPE_IMPORT, GRID_LIMITER_TYPE_EXPORT],
        DEFAULT_GRID_LIMITER_TYPE,
        None,
    )
    select.hass = mock_entry.hass
    
    await select.async_select_option(GRID_LIMITER_TYPE_EXPORT)
    
    mock_coordinator.apply_options.assert_called_once()
    mock_entry.hass.config_entries.async_update_entry.assert_called_once()
    
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_GRID_LIMITER_TYPE] == GRID_LIMITER_TYPE_EXPORT


async def test_select_select_option_invalid(mock_coordinator, mock_entry):
    """Test select entity select_option with invalid option."""
    select = SolarEnergyFlowSelect(
        mock_coordinator,
        mock_entry,
        CONF_GRID_LIMITER_TYPE,
        "Grid limiter type",
        [GRID_LIMITER_TYPE_IMPORT, GRID_LIMITER_TYPE_EXPORT],
        DEFAULT_GRID_LIMITER_TYPE,
        None,
    )
    
    with pytest.raises(ServiceValidationError):
        await select.async_select_option("invalid_option")


async def test_select_runtime_mode_change_to_manual_sp(mock_coordinator, mock_entry):
    """Test select entity changing runtime mode to MANUAL_SP."""
    select = SolarEnergyFlowSelect(
        mock_coordinator,
        mock_entry,
        CONF_RUNTIME_MODE,
        "Runtime mode",
        [RUNTIME_MODE_AUTO_SP, RUNTIME_MODE_MANUAL_SP],
        DEFAULT_RUNTIME_MODE,
        None,
    )
    select.hass = mock_entry.hass
    mock_coordinator.get_runtime_mode.return_value = RUNTIME_MODE_AUTO_SP
    
    await select.async_select_option(RUNTIME_MODE_MANUAL_SP)
    
    # Should set manual SP from normal setpoint
    mock_coordinator.set_manual_sp_from_normal_setpoint.assert_called_once()
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_RUNTIME_MODE] == RUNTIME_MODE_MANUAL_SP


async def test_select_runtime_mode_no_change(mock_coordinator, mock_entry):
    """Test select entity when runtime mode doesn't change."""
    select = SolarEnergyFlowSelect(
        mock_coordinator,
        mock_entry,
        CONF_RUNTIME_MODE,
        "Runtime mode",
        [RUNTIME_MODE_AUTO_SP, RUNTIME_MODE_MANUAL_SP],
        DEFAULT_RUNTIME_MODE,
        None,
    )
    select.hass = mock_entry.hass
    mock_coordinator.get_runtime_mode.return_value = RUNTIME_MODE_MANUAL_SP
    
    await select.async_select_option(RUNTIME_MODE_MANUAL_SP)
    
    # Should not reset manual SP if already in MANUAL_SP mode
    mock_coordinator.async_reset_manual_sp.assert_not_called()


async def test_select_error_handling(mock_coordinator, mock_entry):
    """Test select entity error handling."""
    select = SolarEnergyFlowSelect(
        mock_coordinator,
        mock_entry,
        CONF_GRID_LIMITER_TYPE,
        "Grid limiter type",
        [GRID_LIMITER_TYPE_IMPORT, GRID_LIMITER_TYPE_EXPORT],
        DEFAULT_GRID_LIMITER_TYPE,
        None,
    )
    select.hass = mock_entry.hass
    
    mock_coordinator.apply_options.side_effect = Exception("Test error")

    with pytest.raises(HomeAssistantError):
        await select.async_select_option(GRID_LIMITER_TYPE_EXPORT)


async def test_async_setup_entry(hass: HomeAssistant, mock_entry):
    """Test async_setup_entry for selects."""
    mock_coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    mock_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, mock_add_entities)
    
    # Verify entities are created
    assert mock_add_entities.called
    call_args = mock_add_entities.call_args[0][0]
    assert len(call_args) == 2  # Should create 2 select entities


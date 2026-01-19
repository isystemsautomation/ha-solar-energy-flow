"""Test the __init__ module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryError, ConfigEntryNotReady
from homeassistant.core import HomeAssistant

from custom_components.solar_energy_controller import DOMAIN, async_setup, async_setup_entry, async_unload_entry
from custom_components.solar_energy_controller.const import (
    CONF_GRID_POWER_ENTITY,
    CONF_OUTPUT_ENTITY,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_SETPOINT_ENTITY,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_listen_once = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.title = "Test Controller"
    entry.data = {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv",
        CONF_SETPOINT_ENTITY: "number.sp",
        CONF_OUTPUT_ENTITY: "number.output",
        CONF_GRID_POWER_ENTITY: "sensor.grid",
    }
    entry.options = {}
    entry.runtime_data = None
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


async def test_async_setup(mock_hass):
    """Test async_setup function."""
    with patch("os.path.isdir", return_value=True), patch("os.path.dirname", return_value="/test/path"):
        result = await async_setup(mock_hass, {})
        
        assert result is True
        mock_hass.http.async_register_static_paths.assert_called_once()
        mock_hass.bus.async_listen_once.assert_called_once()


async def test_async_setup_entry_success(mock_hass, mock_entry):
    """Test successful async_setup_entry."""
    # Setup mock states
    mock_hass.states.__contains__ = MagicMock(return_value=True)
    mock_hass.states.__getitem__ = MagicMock(return_value=MagicMock(state="100"))
    
    # Mock coordinator
    with patch("custom_components.solar_energy_controller.SolarEnergyFlowCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator
        
        # Mock device registry
        with patch("custom_components.solar_energy_controller.dr.async_get") as mock_dr:
            mock_dr_instance = MagicMock()
            mock_dr_instance.async_get_or_create = MagicMock()
            mock_dr.return_value = mock_dr_instance
            
            result = await async_setup_entry(mock_hass, mock_entry)
            
            assert result is True
            assert mock_entry.runtime_data == mock_coordinator
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once()


async def test_async_setup_entry_missing_entities(mock_hass, mock_entry):
    """Test async_setup_entry with missing entities."""
    # Mock states.get to return None (entity not found)
    mock_hass.states.get = MagicMock(return_value=None)
    # Add data attribute for device registry access
    if not hasattr(mock_hass, 'data'):
        mock_hass.data = {}
    # Add config attribute for storage path
    if not hasattr(mock_hass, 'config'):
        mock_hass.config = MagicMock()
        mock_hass.config.config_dir = "/tmp/test_config"
    
    # Mock device registry
    mock_device_registry = MagicMock()
    mock_device_registry.async_get_or_create = MagicMock()
    
    with patch('custom_components.solar_energy_controller.__init__.dr.async_get', return_value=mock_device_registry):
        with pytest.raises(ConfigEntryError, match="Required entities not found"):
            await async_setup_entry(mock_hass, mock_entry)


async def test_async_setup_entry_unavailable_entities(mock_hass, mock_entry):
    """Test async_setup_entry with unavailable entities."""
    # Mock states.get to return a state with "unavailable" status
    mock_state = MagicMock()
    mock_state.state = "unavailable"
    mock_hass.states.get = MagicMock(return_value=mock_state)
    # Add data attribute for device registry access
    if not hasattr(mock_hass, 'data'):
        mock_hass.data = {}
    # Add config attribute for storage path
    if not hasattr(mock_hass, 'config'):
        mock_hass.config = MagicMock()
        mock_hass.config.config_dir = "/tmp/test_config"
    
    # Mock device registry
    mock_device_registry = MagicMock()
    mock_device_registry.async_get_or_create = MagicMock()
    
    with patch('custom_components.solar_energy_controller.__init__.dr.async_get', return_value=mock_device_registry):
        with pytest.raises(ConfigEntryNotReady, match="Required entities are unavailable"):
            await async_setup_entry(mock_hass, mock_entry)


async def test_async_setup_entry_coordinator_failure(mock_hass, mock_entry):
    """Test async_setup_entry when coordinator initialization fails."""
    mock_hass.states.__contains__ = MagicMock(return_value=True)
    mock_hass.states.__getitem__ = MagicMock(return_value=MagicMock(state="100"))
    
    with patch("custom_components.solar_energy_controller.SolarEnergyFlowCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=Exception("Test error"))
        mock_coordinator_class.return_value = mock_coordinator
        
        with patch("custom_components.solar_energy_controller.dr.async_get"):
            with pytest.raises(ConfigEntryNotReady, match="Failed to initialize coordinator"):
                await async_setup_entry(mock_hass, mock_entry)


async def test_async_unload_entry(mock_hass, mock_entry):
    """Test async_unload_entry."""
    result = await async_unload_entry(mock_hass, mock_entry)
    
    assert result is True
    mock_hass.config_entries.async_unload_platforms.assert_called_once_with(mock_entry, ["sensor", "switch", "number", "select"])


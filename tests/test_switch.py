"""Test switch entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.solar_energy_controller.const import (
    CONF_ENABLED,
    CONF_GRID_LIMITER_ENABLED,
    CONF_RATE_LIMITER_ENABLED,
    DEFAULT_ENABLED,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_RATE_LIMITER_ENABLED,
)
from custom_components.solar_energy_controller.coordinator import SolarEnergyFlowCoordinator
from custom_components.solar_energy_controller.switch import (
    SolarEnergyFlowEnabledSwitch,
    SolarEnergyFlowGridLimiterSwitch,
    SolarEnergyFlowRateLimiterSwitch,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    coordinator.apply_options = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
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


def test_enabled_switch_is_on(mock_coordinator, mock_entry):
    """Test Enabled switch is_on property."""
    mock_entry.options = {CONF_ENABLED: True}
    switch = SolarEnergyFlowEnabledSwitch(mock_coordinator, mock_entry)
    
    assert switch.is_on is True
    
    mock_entry.options = {CONF_ENABLED: False}
    assert switch.is_on is False
    
    mock_entry.options = {}
    assert switch.is_on == DEFAULT_ENABLED


async def test_enabled_switch_turn_on(mock_coordinator, mock_entry):
    """Test Enabled switch turn on."""
    switch = SolarEnergyFlowEnabledSwitch(mock_coordinator, mock_entry)
    switch.hass = mock_entry.hass
    
    await switch.async_turn_on()
    
    mock_coordinator.apply_options.assert_called_once()
    mock_entry.hass.config_entries.async_update_entry.assert_called_once()
    mock_coordinator.async_request_refresh.assert_called_once()
    
    # Check that enabled was set to True
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_ENABLED] is True


async def test_enabled_switch_turn_off(mock_coordinator, mock_entry):
    """Test Enabled switch turn off."""
    switch = SolarEnergyFlowEnabledSwitch(mock_coordinator, mock_entry)
    switch.hass = mock_entry.hass
    
    await switch.async_turn_off()
    
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_ENABLED] is False


async def test_enabled_switch_error_handling(mock_coordinator, mock_entry):
    """Test Enabled switch error handling."""
    switch = SolarEnergyFlowEnabledSwitch(mock_coordinator, mock_entry)
    switch.hass = mock_entry.hass
    
    mock_coordinator.apply_options.side_effect = Exception("Test error")

    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()


def test_rate_limiter_switch_is_on(mock_coordinator, mock_entry):
    """Test Rate limiter switch is_on property."""
    mock_entry.options = {CONF_RATE_LIMITER_ENABLED: True}
    switch = SolarEnergyFlowRateLimiterSwitch(mock_coordinator, mock_entry)
    
    assert switch.is_on is True


async def test_rate_limiter_switch_turn_on(mock_coordinator, mock_entry):
    """Test Rate limiter switch turn on."""
    switch = SolarEnergyFlowRateLimiterSwitch(mock_coordinator, mock_entry)
    switch.hass = mock_entry.hass
    
    await switch.async_turn_on()
    
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_RATE_LIMITER_ENABLED] is True


def test_grid_limiter_switch_is_on(mock_coordinator, mock_entry):
    """Test Grid limiter switch is_on property."""
    mock_entry.options = {CONF_GRID_LIMITER_ENABLED: True}
    switch = SolarEnergyFlowGridLimiterSwitch(mock_coordinator, mock_entry)
    
    assert switch.is_on is True


async def test_grid_limiter_switch_turn_on(mock_coordinator, mock_entry):
    """Test Grid limiter switch turn on."""
    switch = SolarEnergyFlowGridLimiterSwitch(mock_coordinator, mock_entry)
    switch.hass = mock_entry.hass
    
    await switch.async_turn_on()
    
    call_args = mock_coordinator.apply_options.call_args[0][0]
    assert call_args[CONF_GRID_LIMITER_ENABLED] is True


async def test_grid_limiter_switch_error_handling(mock_coordinator, mock_entry):
    """Test Grid limiter switch error handling."""
    switch = SolarEnergyFlowGridLimiterSwitch(mock_coordinator, mock_entry)
    switch.hass = mock_entry.hass
    
    mock_coordinator.apply_options.side_effect = Exception("Test error")

    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()


async def test_async_setup_entry(hass: HomeAssistant, mock_entry):
    """Test async_setup_entry for switches."""
    mock_coordinator = MagicMock(spec=SolarEnergyFlowCoordinator)
    mock_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, mock_add_entities)
    
    # Verify entities are created
    assert mock_add_entities.called
    call_args = mock_add_entities.call_args[0][0]
    assert len(call_args) == 3  # Should create 3 switch entities


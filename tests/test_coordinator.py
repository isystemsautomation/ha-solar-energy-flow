"""Test the coordinator."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.solar_energy_controller.const import (
    CONF_ENABLED,
    CONF_GRID_LIMITER_ENABLED,
    CONF_GRID_POWER_ENTITY,
    CONF_KP,
    CONF_KI,
    CONF_KD,
    CONF_MAX_OUTPUT,
    CONF_MIN_OUTPUT,
    CONF_OUTPUT_ENTITY,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_RATE_LIMITER_ENABLED,
    CONF_RUNTIME_MODE,
    CONF_SETPOINT_ENTITY,
    DEFAULT_ENABLED,
    DEFAULT_KP,
    DEFAULT_KI,
    DEFAULT_KD,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_MIN_OUTPUT,
    RUNTIME_MODE_AUTO_SP,
    RUNTIME_MODE_HOLD,
    RUNTIME_MODE_MANUAL_OUT,
    RUNTIME_MODE_MANUAL_SP,
)
from custom_components.solar_energy_controller.coordinator import SolarEnergyFlowCoordinator
from custom_components.solar_energy_controller.const import (
    CONF_PV_MIN,
    CONF_PV_MAX,
    DEFAULT_GRID_MIN,
    DEFAULT_GRID_MAX,
    DEFAULT_PV_MIN,
    DEFAULT_PV_MAX,
    DEFAULT_SP_MIN,
    DEFAULT_SP_MAX,
)


@dataclass
class MockState:
    """Mock Home Assistant state."""
    state: str = "100.0"
    attributes: dict = None
    
    def __init__(self, state="100.0", attributes=None):
        self.state = state
        self.attributes = attributes or {}


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=MockState("100.0"))
    hass.states.__contains__ = MagicMock(return_value=True)
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.options = {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv",
        CONF_SETPOINT_ENTITY: "number.sp",
        CONF_OUTPUT_ENTITY: "number.output",
        CONF_GRID_POWER_ENTITY: "sensor.grid",
        CONF_KP: DEFAULT_KP,
        CONF_KI: DEFAULT_KI,
        CONF_KD: DEFAULT_KD,
        CONF_MIN_OUTPUT: DEFAULT_MIN_OUTPUT,
        CONF_MAX_OUTPUT: DEFAULT_MAX_OUTPUT,
        CONF_ENABLED: DEFAULT_ENABLED,
        CONF_RUNTIME_MODE: RUNTIME_MODE_AUTO_SP,
    }
    entry.data = {}
    return entry


def test_coordinator_initialization(mock_hass, mock_entry):
    """Test coordinator initialization."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    assert coordinator.hass == mock_hass
    assert coordinator.entry == mock_entry
    assert coordinator.pid is not None
    assert coordinator._runtime_mode == RUNTIME_MODE_AUTO_SP
    assert coordinator._limiter_state == "normal"


def test_coordinator_apply_options(mock_hass, mock_entry):
    """Test coordinator apply_options."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    new_options = {
        CONF_KP: 2.0,
        CONF_KI: 0.2,
        CONF_KD: 0.1,
        CONF_RUNTIME_MODE: RUNTIME_MODE_MANUAL_SP,
    }
    
    coordinator.apply_options(new_options)
    
    assert coordinator.options_cache == new_options
    assert coordinator._runtime_mode == RUNTIME_MODE_MANUAL_SP


def test_coordinator_get_runtime_mode(mock_hass, mock_entry):
    """Test coordinator get_runtime_mode."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    assert coordinator.get_runtime_mode() == RUNTIME_MODE_AUTO_SP
    
    coordinator._runtime_mode = RUNTIME_MODE_MANUAL_SP
    assert coordinator.get_runtime_mode() == RUNTIME_MODE_MANUAL_SP


def test_coordinator_get_manual_sp_value(mock_hass, mock_entry):
    """Test coordinator get_manual_sp_value."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    coordinator._manual_sp_value = 60.0
    
    assert coordinator.get_manual_sp_value() == 60.0


def test_coordinator_get_manual_out_value(mock_hass, mock_entry):
    """Test coordinator get_manual_out_value."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    coordinator._manual_out_value = 55.0
    
    assert coordinator.get_manual_out_value() == 55.0


async def test_coordinator_async_set_manual_sp(mock_hass, mock_entry):
    """Test coordinator async_set_manual_sp."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    await coordinator.async_set_manual_sp(70.0)
    
    assert coordinator._manual_sp_value == 70.0
    assert coordinator._manual_sp_initialized is True


async def test_coordinator_async_set_manual_out(mock_hass, mock_entry):
    """Test coordinator async_set_manual_out."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    coordinator._runtime_mode = RUNTIME_MODE_MANUAL_OUT
    
    await coordinator.async_set_manual_out(80.0)
    
    assert coordinator._manual_out_value == 80.0
    assert coordinator._last_output_raw == 80.0


async def test_coordinator_async_reset_manual_sp(mock_hass, mock_entry):
    """Test coordinator async_reset_manual_sp."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    coordinator._manual_sp_value = 60.0
    coordinator._manual_sp_initialized = True
    
    await coordinator.async_reset_manual_sp()
    
    assert coordinator._manual_sp_value is None
    assert coordinator._manual_sp_initialized is False


def test_coordinator_set_manual_sp_from_normal_setpoint(mock_hass, mock_entry):
    """Test coordinator set_manual_sp_from_normal_setpoint."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    # Mock _get_normal_setpoint_value
    with patch.object(coordinator, "_get_normal_setpoint_value", return_value=65.0):
        result = coordinator.set_manual_sp_from_normal_setpoint()
        
        assert result == 65.0
        assert coordinator._manual_sp_value == 65.0
        assert coordinator._manual_sp_initialized is True


def test_coordinator_options_require_reload(mock_hass, mock_entry):
    """Test coordinator options_require_reload."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    old_options = {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv",
        CONF_SETPOINT_ENTITY: "number.sp",
    }
    new_options = {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv2",  # Changed
        CONF_SETPOINT_ENTITY: "number.sp",
    }
    
    assert coordinator.options_require_reload(old_options, new_options) is True
    
    # Test with no wiring changes
    new_options2 = {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv",
        CONF_SETPOINT_ENTITY: "number.sp",
        CONF_KP: 2.0,  # Only tuning changed
    }
    
    assert coordinator.options_require_reload(old_options, new_options2) is False


async def test_coordinator_read_inputs(mock_hass, mock_entry):
    """Test coordinator _read_inputs."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    # Mock states - _read_inputs calls states.get for PV, Grid, and SP
    def mock_get(entity_id):
        if "pv" in entity_id.lower() or entity_id == "sensor.pv":
            return MockState("50.0")
        elif "grid" in entity_id.lower() or entity_id == "sensor.grid":
            return MockState("100.0")
        elif "sp" in entity_id.lower() or entity_id == "number.sp":
            return MockState("60.0")
        return None
    
    mock_hass.states.get = MagicMock(side_effect=mock_get)
    
    options = coordinator._build_runtime_options()
    inputs = coordinator._read_inputs(options)
    
    assert inputs.pv == 50.0
    assert inputs.sp == 60.0
    assert inputs.grid_power == 100.0


async def test_coordinator_read_inputs_unavailable(mock_hass, mock_entry):
    """Test coordinator _read_inputs with unavailable entities."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    # Mock unavailable states
    def mock_get(entity_id):
        if "pv" in entity_id.lower() or entity_id == "sensor.pv":
            return MockState("unavailable")
        elif "grid" in entity_id.lower() or entity_id == "sensor.grid":
            return MockState("100.0")
        elif "sp" in entity_id.lower() or entity_id == "number.sp":
            return MockState("60.0")
        return None
    
    mock_hass.states.get = MagicMock(side_effect=mock_get)
    
    options = coordinator._build_runtime_options()
    inputs = coordinator._read_inputs(options)
    
    # PV should be None when unavailable
    assert inputs.pv is None


async def test_coordinator_async_update_data(mock_hass, mock_entry):
    """Test coordinator _async_update_data."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    # Set output range to 0-100 so 55% = 55.0 raw for easier testing
    mock_entry.options[CONF_MIN_OUTPUT] = 0.0
    mock_entry.options[CONF_MAX_OUTPUT] = 100.0

    # Mock states - called for PV, Grid, SP, and Output
    call_count = 0
    def mock_get(entity_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1 or "pv" in (entity_id or "").lower():
            return MockState("50.0")
        elif call_count == 2 or "grid" in (entity_id or "").lower():
            return MockState("100.0")
        elif call_count == 3 or "sp" in (entity_id or "").lower():
            return MockState("60.0")
        elif call_count == 4 or "output" in (entity_id or "").lower():
            return MockState("55.0")
        return None
    
    mock_hass.states.get = MagicMock(side_effect=mock_get)
    
    # Mock PID step - returns percent values (55.0 = 55%)
    with patch.object(coordinator.pid, "step") as mock_step:
        from custom_components.solar_energy_controller.pid import PIDStepResult
        mock_step.return_value = PIDStepResult(
            output=55.0,  # 55% which becomes 55.0 raw with 0-100 range
            error=10.0,
            p_term=5.0,
            i_term=3.0,
            d_term=2.0,
            output_pre_rate_limit=55.0,
        )
        
        # Mock output writing - need to actually set _last_output_raw
        async def mock_write(ent, output, opts):
            coordinator._last_output_raw = output
            return MagicMock(write_failed=False, output=output)
        
        with patch.object(coordinator, "_maybe_write_output", side_effect=mock_write):
            result = await coordinator._async_update_data()
            
            assert result is not None
            assert result.pv == 50.0
            assert result.sp == 60.0
            assert result.out == pytest.approx(55.0)


async def test_coordinator_async_update_data_disabled(mock_hass, mock_entry):
    """Test coordinator _async_update_data when disabled."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    mock_entry.options[CONF_ENABLED] = False
    
    result = await coordinator._async_update_data()
    
    assert result.status == "disabled"
    assert result.out == DEFAULT_MIN_OUTPUT


async def test_coordinator_async_update_data_hold_mode(mock_hass, mock_entry):
    """Test coordinator _async_update_data in HOLD mode."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    coordinator._last_output_raw = 50.0
    mock_entry.options[CONF_RUNTIME_MODE] = RUNTIME_MODE_HOLD
    # Update coordinator's runtime mode to match entry options
    coordinator._runtime_mode = RUNTIME_MODE_HOLD
    
    # Mock states for inputs
    def mock_get(entity_id):
        if entity_id and ("pv" in entity_id.lower() or "grid" in entity_id.lower() or "sp" in entity_id.lower() or "output" in entity_id.lower()):
            return MockState("0.0")
        return None
    mock_hass.states.get = MagicMock(side_effect=mock_get)
    
    result = await coordinator._async_update_data()
    
    assert result.status == "hold"
    assert result.out == 50.0


async def test_coordinator_async_update_data_manual_out_mode(mock_hass, mock_entry):
    """Test coordinator _async_update_data in MANUAL_OUT mode."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    coordinator._manual_out_value = 70.0
    mock_entry.options[CONF_RUNTIME_MODE] = RUNTIME_MODE_MANUAL_OUT
    # Update coordinator's runtime mode to match entry options
    coordinator._runtime_mode = RUNTIME_MODE_MANUAL_OUT
    
    # Mock states for inputs
    def mock_get(entity_id):
        if entity_id and ("pv" in entity_id.lower() or "grid" in entity_id.lower() or "sp" in entity_id.lower() or "output" in entity_id.lower()):
            return MockState("0.0")
        return None
    mock_hass.states.get = MagicMock(side_effect=mock_get)
    
    result = await coordinator._async_update_data()
    
    assert result.status == "manual_out"
    assert result.out == 70.0


async def test_coordinator_maybe_write_output(mock_hass, mock_entry):
    """Test coordinator _maybe_write_output."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    # Mock _set_output
    with patch("custom_components.solar_energy_controller.coordinator._set_output", new_callable=AsyncMock) as mock_set:
        mock_set.return_value = True
        
        result = await coordinator._maybe_write_output("number.output", 55.0, options)
        
        assert result.write_failed is False
        assert result.output == 55.0
        mock_set.assert_called_once()


async def test_coordinator_maybe_write_output_failed(mock_hass, mock_entry):
    """Test coordinator _maybe_write_output when write fails."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    # Mock _set_output to fail
    with patch("custom_components.solar_energy_controller.coordinator._set_output", new_callable=AsyncMock) as mock_set:
        mock_set.return_value = False
        
        result = await coordinator._maybe_write_output("number.output", 55.0, options)
        
        assert result.write_failed is True


def test_coordinator_build_runtime_options(mock_hass, mock_entry):
    """Test coordinator _build_runtime_options."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    assert options.enabled == DEFAULT_ENABLED
    assert options.min_output == DEFAULT_MIN_OUTPUT
    assert options.max_output == DEFAULT_MAX_OUTPUT
    assert options.pv_min == DEFAULT_PV_MIN
    assert options.pv_max == DEFAULT_PV_MAX
    assert options.sp_min == DEFAULT_SP_MIN
    assert options.sp_max == DEFAULT_SP_MAX


def test_coordinator_get_range_value(mock_hass, mock_entry):
    """Test coordinator _get_range_value."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    min_val, max_val = coordinator._get_range_value(
        CONF_PV_MIN, CONF_PV_MAX, DEFAULT_PV_MIN, DEFAULT_PV_MAX
    )
    
    assert min_val == DEFAULT_PV_MIN
    assert max_val == DEFAULT_PV_MAX


def test_coordinator_output_percent_from_raw(mock_hass, mock_entry):
    """Test coordinator _output_percent_from_raw."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    # Test normalization
    percent = coordinator._output_percent_from_raw(5500.0, options)
    assert percent == 50.0  # (5500 - 0) / (11000 - 0) * 100
    
    # Test with None
    assert coordinator._output_percent_from_raw(None, options) is None


def test_coordinator_output_raw_from_percent(mock_hass, mock_entry):
    """Test coordinator _output_raw_from_percent."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    # Test denormalization
    raw = coordinator._output_raw_from_percent(50.0, options)
    assert raw == 5500.0  # 0 + (50.0 / 100.0) * (11000 - 0)
    
    # Test with None
    assert coordinator._output_raw_from_percent(None, options) is None


def test_coordinator_apply_output_fence(mock_hass, mock_entry):
    """Test coordinator _apply_output_fence."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    # Test normal value
    output, should_write = coordinator._apply_output_fence(5500.0, options)
    assert output == 5500.0
    assert should_write is True
    
    # Test clamping to min
    output, should_write = coordinator._apply_output_fence(-100.0, options)
    assert output == DEFAULT_MIN_OUTPUT
    assert should_write is True
    
    # Test clamping to max
    output, should_write = coordinator._apply_output_fence(20000.0, options)
    assert output == DEFAULT_MAX_OUTPUT
    assert should_write is True


def test_coordinator_apply_output_status(mock_hass, mock_entry):
    """Test coordinator _apply_output_status."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    # Test normal status
    status = coordinator._apply_output_status("running", False)
    assert status == "running"
    
    # Test write failed
    status = coordinator._apply_output_status("running", True)
    assert status == "output_write_failed"


def test_coordinator_build_pid_config_from_options(mock_hass, mock_entry):
    """Test coordinator _build_pid_config_from_options."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    # _build_pid_config_from_options expects entry.options (Mapping), not RuntimeOptions
    pid_config = coordinator._build_pid_config_from_options(mock_entry.options)
    
    assert pid_config.kp == DEFAULT_KP
    assert pid_config.ki == DEFAULT_KI
    assert pid_config.kd == DEFAULT_KD
    assert pid_config.min_output == 0.0  # Always normalized to 0-100
    assert pid_config.max_output == 100.0


def test_coordinator_compute_setpoint_context(mock_hass, mock_entry):
    """Test coordinator _compute_setpoint_context."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    from custom_components.solar_energy_controller.coordinator import InputValues, RuntimeOptions
    
    options = coordinator._build_runtime_options()
    inputs = InputValues(pv=50.0, sp=60.0, grid_power=100.0)
    
    context = coordinator._compute_setpoint_context(options, inputs, RUNTIME_MODE_AUTO_SP, None)
    
    assert context.runtime_mode == RUNTIME_MODE_AUTO_SP
    assert context.pv_for_pid == 50.0
    assert context.sp_for_pid == 60.0


def test_coordinator_apply_grid_limiter(mock_hass, mock_entry):
    """Test coordinator _apply_grid_limiter."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    from custom_components.solar_energy_controller.coordinator import InputValues, SetpointContext, RuntimeOptions
    from custom_components.solar_energy_controller.const import GRID_LIMITER_STATE_NORMAL, GRID_LIMITER_TYPE_IMPORT
    
    options = coordinator._build_runtime_options()
    options.limiter_enabled = True
    options.limiter_type = GRID_LIMITER_TYPE_IMPORT
    options.limiter_limit_w = 1000.0
    options.limiter_deadband_w = 50.0
    
    inputs = InputValues(pv=50.0, sp=60.0, grid_power=1500.0)
    setpoint = SetpointContext(
        runtime_mode=RUNTIME_MODE_AUTO_SP,
        manual_sp_value=None,
        manual_sp_display_value=None,
        pv_for_pid=50.0,
        sp_for_pid=60.0,
        status="running",
        mode_changed=False,
    )
    
    result = coordinator._apply_grid_limiter(options, inputs, setpoint, GRID_LIMITER_STATE_NORMAL)
    
    assert result is not None
    assert result.limiter_state in (GRID_LIMITER_STATE_NORMAL, "limiting_import", "limiting_export")


async def test_coordinator_maybe_write_output_no_write(mock_hass, mock_entry):
    """Test coordinator _maybe_write_output when write is not needed."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    # Test with None output
    result = await coordinator._maybe_write_output(None, None, options)
    
    assert result.write_failed is False
    assert result.output is None


async def test_coordinator_maybe_write_output_no_entity(mock_hass, mock_entry):
    """Test coordinator _maybe_write_output when no output entity."""
    coordinator = SolarEnergyFlowCoordinator(mock_hass, mock_entry)
    
    options = coordinator._build_runtime_options()
    
    result = await coordinator._maybe_write_output(None, 55.0, options)
    
    # Should still update internal state
    assert coordinator._last_output_raw == 55.0


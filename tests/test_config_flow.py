"""Test the Solar Energy Controller config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.solar_energy_controller import DOMAIN
from custom_components.solar_energy_controller.const import (
    CONF_GRID_MAX,
    CONF_GRID_MIN,
    CONF_GRID_POWER_ENTITY,
    CONF_NAME,
    CONF_OUTPUT_ENTITY,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_PV_MAX,
    CONF_PV_MIN,
    CONF_SETPOINT_ENTITY,
    CONF_SP_MAX,
    CONF_SP_MIN,
    DEFAULT_GRID_MAX,
    DEFAULT_GRID_MIN,
    DEFAULT_PV_MAX,
    DEFAULT_PV_MIN,
    DEFAULT_SP_MAX,
    DEFAULT_SP_MIN,
)


# enable_custom_integrations fixture is provided by pytest_homeassistant_custom_component
# and should work automatically. No wrapper needed.


def _setup_test_entities(hass: HomeAssistant) -> None:
    """Helper to set up test entities required for config flow."""
    hass.states.async_set("sensor.pv_sensor", "50.0")
    hass.states.async_set("number.setpoint", "60.0")
    hass.states.async_set("number.output", "55.0")
    hass.states.async_set("sensor.grid_power", "100.0")


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user flow."""
    _setup_test_entities(hass)
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Controller"
    assert result2["data"] == {
        CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
        CONF_SETPOINT_ENTITY: "number.setpoint",
        CONF_OUTPUT_ENTITY: "number.output",
        CONF_GRID_POWER_ENTITY: "sensor.grid_power",
        CONF_PV_MIN: DEFAULT_PV_MIN,
        CONF_PV_MAX: DEFAULT_PV_MAX,
        CONF_SP_MIN: DEFAULT_SP_MIN,
        CONF_SP_MAX: DEFAULT_SP_MAX,
        CONF_GRID_MIN: DEFAULT_GRID_MIN,
        CONF_GRID_MAX: DEFAULT_GRID_MAX,
    }


async def test_user_flow_invalid_pv_domain(hass: HomeAssistant) -> None:
    """Test user flow with invalid PV domain."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Schema validation catches invalid domains before config flow validation
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "switch.invalid",  # Invalid domain
                CONF_SETPOINT_ENTITY: "number.setpoint",
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_user_flow_invalid_sp_domain(hass: HomeAssistant) -> None:
    """Test user flow with invalid setpoint domain."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Schema validation catches invalid domains before config flow validation
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
                CONF_SETPOINT_ENTITY: "sensor.invalid",  # Invalid domain
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_user_flow_invalid_output_domain(hass: HomeAssistant) -> None:
    """Test user flow with invalid output domain."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Schema validation catches invalid domains before config flow validation
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
                CONF_SETPOINT_ENTITY: "number.setpoint",
                CONF_OUTPUT_ENTITY: "sensor.invalid",  # Invalid domain
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_user_flow_invalid_grid_domain(hass: HomeAssistant) -> None:
    """Test user flow with invalid grid domain."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Schema validation catches invalid domains before config flow validation
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
                CONF_SETPOINT_ENTITY: "number.setpoint",
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "switch.invalid",  # Invalid domain
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_user_flow_invalid_pv_range(hass: HomeAssistant) -> None:
    """Test user flow with invalid PV range (max <= min)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: 100.0,
            CONF_PV_MAX: 100.0,  # Equal to min
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert "base" in result2["errors"]
    assert result2["errors"]["base"] == "invalid_range"


async def test_user_flow_invalid_sp_range(hass: HomeAssistant) -> None:
    """Test user flow with invalid SP range (max <= min)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: 100.0,
            CONF_SP_MAX: 50.0,  # Less than min
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert "base" in result2["errors"]
    assert result2["errors"]["base"] == "invalid_range"


async def test_user_flow_invalid_grid_range(hass: HomeAssistant) -> None:
    """Test user flow with invalid grid range (max <= min)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: 100.0,
            CONF_GRID_MAX: 50.0,  # Less than min
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert "base" in result2["errors"]
    assert result2["errors"]["base"] == "invalid_range"


async def test_user_flow_invalid_range_non_numeric(hass: HomeAssistant) -> None:
    """Test user flow with non-numeric range values."""
    _setup_test_entities(hass)
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Schema validation with vol.Coerce(float) will raise InvalidData for non-numeric values
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
                CONF_SETPOINT_ENTITY: "number.setpoint",
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: "not_a_number",  # Invalid
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_user_flow_multiple_errors(hass: HomeAssistant) -> None:
    """Test user flow with multiple validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Schema validation catches invalid domains before config flow validation
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "switch.invalid",  # Invalid domain
                CONF_SETPOINT_ENTITY: "sensor.invalid",  # Invalid domain
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_user_flow_duplicate_entry(hass: HomeAssistant) -> None:
    """Test user flow prevents duplicate entries."""
    _setup_test_entities(hass)
    hass.states.async_set("sensor.grid_power2", "100.0")
    
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller 1",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY

    # Try to create duplicate entry with same PV/SP/Output
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            CONF_NAME: "Test Controller 2",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",  # Same as first
            CONF_SETPOINT_ENTITY: "number.setpoint",  # Same as first
            CONF_OUTPUT_ENTITY: "number.output",  # Same as first
            CONF_GRID_POWER_ENTITY: "sensor.grid_power2",  # Different grid is OK
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )

    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_user_flow_different_unique_id_allowed(hass: HomeAssistant) -> None:
    """Test user flow allows different unique IDs."""
    _setup_test_entities(hass)
    hass.states.async_set("sensor.pv_sensor2", "50.0")
    
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller 1",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY

    # Create second entry with different PV (different unique ID)
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            CONF_NAME: "Test Controller 2",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor2",  # Different PV
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Test Controller 2"


async def test_user_flow_error_recovery(hass: HomeAssistant) -> None:
    """Test user flow can recover from errors."""
    _setup_test_entities(hass)
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt with error - schema validation catches invalid domain
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Controller",
                CONF_PROCESS_VALUE_ENTITY: "switch.invalid",  # Invalid domain
                CONF_SETPOINT_ENTITY: "number.setpoint",
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )

    # Second attempt - need to re-init the flow after InvalidData
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Second attempt with corrected value
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",  # Fixed
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test Controller"


async def test_options_flow_success(hass: HomeAssistant) -> None:
    """Test successful options flow."""
    # Create entry first
    entry = await _create_test_entry(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Update options
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: -1000.0,
            CONF_PV_MAX: 1000.0,
            CONF_SP_MIN: -500.0,
            CONF_SP_MAX: 500.0,
            CONF_GRID_MIN: -2000.0,
            CONF_GRID_MAX: 2000.0,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PV_MIN] == -1000.0
    assert entry.options[CONF_PV_MAX] == 1000.0


async def test_options_flow_invalid_domains(hass: HomeAssistant) -> None:
    """Test options flow with invalid domains."""
    entry = await _create_test_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Schema validation catches invalid domains before config flow validation
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_PROCESS_VALUE_ENTITY: "switch.invalid",
                CONF_SETPOINT_ENTITY: "sensor.invalid",
                CONF_OUTPUT_ENTITY: "sensor.invalid",
                CONF_GRID_POWER_ENTITY: "switch.invalid",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )


async def test_options_flow_invalid_ranges(hass: HomeAssistant) -> None:
    """Test options flow with invalid ranges."""
    entry = await _create_test_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: 100.0,
            CONF_PV_MAX: 50.0,  # Invalid: max < min
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "init"
    assert "base" in result2["errors"]
    assert result2["errors"]["base"] == "invalid_pv_range"


async def test_options_flow_error_recovery(hass: HomeAssistant) -> None:
    """Test options flow can recover from errors."""
    entry = await _create_test_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # First attempt with error - schema validation catches invalid domain
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_PROCESS_VALUE_ENTITY: "switch.invalid",
                CONF_SETPOINT_ENTITY: "number.setpoint",
                CONF_OUTPUT_ENTITY: "number.output",
                CONF_GRID_POWER_ENTITY: "sensor.grid_power",
                CONF_PV_MIN: DEFAULT_PV_MIN,
                CONF_PV_MAX: DEFAULT_PV_MAX,
                CONF_SP_MIN: DEFAULT_SP_MIN,
                CONF_SP_MAX: DEFAULT_SP_MAX,
                CONF_GRID_MIN: DEFAULT_GRID_MIN,
                CONF_GRID_MAX: DEFAULT_GRID_MAX,
            },
        )

    # Second attempt - need to re-init the flow after InvalidData
    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Second attempt with corrected value
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",  # Fixed
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY


async def test_options_flow_preserves_values(hass: HomeAssistant) -> None:
    """Test options flow preserves existing values."""
    entry = await _create_test_entry(hass)

    # Set some options first
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "kp": 2.0,
            "ki": 0.2,
            "enabled": True,
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    # Preserved values should still be there
    assert entry.options.get("kp") == 2.0
    assert entry.options.get("ki") == 0.2
    assert entry.options.get("enabled") is True


async def _create_test_entry(hass: HomeAssistant) -> config_entries.ConfigEntry:
    """Helper to create a test config entry."""
    _setup_test_entities(hass)
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Controller",
            CONF_PROCESS_VALUE_ENTITY: "sensor.pv_sensor",
            CONF_SETPOINT_ENTITY: "number.setpoint",
            CONF_OUTPUT_ENTITY: "number.output",
            CONF_GRID_POWER_ENTITY: "sensor.grid_power",
            CONF_PV_MIN: DEFAULT_PV_MIN,
            CONF_PV_MAX: DEFAULT_PV_MAX,
            CONF_SP_MIN: DEFAULT_SP_MIN,
            CONF_SP_MAX: DEFAULT_SP_MAX,
            CONF_GRID_MIN: DEFAULT_GRID_MIN,
            CONF_GRID_MAX: DEFAULT_GRID_MAX,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    return hass.config_entries.async_entries(DOMAIN)[0]


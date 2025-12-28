from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_PROCESS_VALUE_ENTITY,
    CONF_SETPOINT_ENTITY,
    CONF_OUTPUT_ENTITY,
    CONF_KP,
    CONF_KI,
    CONF_KD,
    CONF_MIN_OUTPUT,
    CONF_MAX_OUTPUT,
    CONF_UPDATE_INTERVAL,
    CONF_ENABLED,
    DEFAULT_KP,
    DEFAULT_KI,
    DEFAULT_KD,
    DEFAULT_MIN_OUTPUT,
    DEFAULT_MAX_OUTPUT,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_ENABLED,
    CONF_INVERT_PV,
    CONF_INVERT_SP,
    CONF_PID_MODE,
    DEFAULT_INVERT_PV,
    DEFAULT_INVERT_SP,
    DEFAULT_PID_MODE,
    PID_MODE_DIRECT,
    PID_MODE_REVERSE,
)
from .pid import PID, PIDConfig

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlowState:
    pv: float | None
    sp: float | None
    out: float | None
    error: float | None
    enabled: bool
    status: str


def _state_to_float(state) -> float | None:
    if state is None:
        return None
    try:
        return float(state.state)
    except Exception:
        return None


def _get_update_interval_seconds(entry: ConfigEntry) -> int:
    raw_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    try:
        interval = int(raw_interval)
    except (TypeError, ValueError):
        _LOGGER.warning(
            "Invalid update interval '%s'; falling back to default (%s)s", raw_interval, DEFAULT_UPDATE_INTERVAL
        )
        return DEFAULT_UPDATE_INTERVAL

    if interval < 1:
        _LOGGER.warning("Update interval must be at least 1 second; clamping %s to 1", interval)
        return 1

    return interval


def _get_pid_limits(entry: ConfigEntry) -> tuple[float, float]:
    raw_min = entry.options.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT)
    raw_max = entry.options.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT)

    try:
        min_output = float(raw_min)
        max_output = float(raw_max)
    except (TypeError, ValueError):
        _LOGGER.warning(
            "Invalid PID output limits min=%s, max=%s; using defaults (min=%s, max=%s)",
            raw_min,
            raw_max,
            DEFAULT_MIN_OUTPUT,
            DEFAULT_MAX_OUTPUT,
        )
        return DEFAULT_MIN_OUTPUT, DEFAULT_MAX_OUTPUT

    if min_output > max_output:
        _LOGGER.warning("min_output %s is greater than max_output %s; swapping values", min_output, max_output)
        min_output, max_output = max_output, min_output

    return min_output, max_output


def _get_pid_mode(entry: ConfigEntry) -> str:
    mode = entry.options.get(CONF_PID_MODE, DEFAULT_PID_MODE)
    if mode in (PID_MODE_DIRECT, PID_MODE_REVERSE):
        return mode
    _LOGGER.warning("Invalid PID mode '%s'; falling back to '%s'", mode, DEFAULT_PID_MODE)
    return DEFAULT_PID_MODE


async def _set_output(hass: HomeAssistant, entity_id: str, value: float) -> None:
    domain = entity_id.split(".", 1)[0]

    if domain == "number":
        await hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": value}, blocking=False)
        return

    if domain == "input_number":
        await hass.services.async_call(
            "input_number", "set_value", {"entity_id": entity_id, "value": value}, blocking=False
        )
        return

    _LOGGER.warning("Unsupported output entity domain '%s' for %s. Use number.* or input_number.*", domain, entity_id)


def _get_entity_id(entry: ConfigEntry, key: str) -> str | None:
    return entry.options.get(key) or entry.data.get(key)


class SolarEnergyFlowCoordinator(DataUpdateCoordinator[FlowState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        interval = _get_update_interval_seconds(entry)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )

        min_output, max_output = _get_pid_limits(entry)
        cfg = PIDConfig(
            kp=entry.options.get(CONF_KP, DEFAULT_KP),
            ki=entry.options.get(CONF_KI, DEFAULT_KI),
            kd=entry.options.get(CONF_KD, DEFAULT_KD),
            min_output=min_output,
            max_output=max_output,
        )
        self.pid = PID(cfg)

    def _refresh_pid_config(self) -> None:
        min_output, max_output = _get_pid_limits(self.entry)
        cfg = PIDConfig(
            kp=self.entry.options.get(CONF_KP, DEFAULT_KP),
            ki=self.entry.options.get(CONF_KI, DEFAULT_KI),
            kd=self.entry.options.get(CONF_KD, DEFAULT_KD),
            min_output=min_output,
            max_output=max_output,
        )
        self.pid.update_config(cfg)

    async def _async_update_data(self) -> FlowState:
        self._refresh_pid_config()

        enabled = self.entry.options.get(CONF_ENABLED, DEFAULT_ENABLED)
        invert_pv = self.entry.options.get(CONF_INVERT_PV, DEFAULT_INVERT_PV)
        invert_sp = self.entry.options.get(CONF_INVERT_SP, DEFAULT_INVERT_SP)
        pid_mode = _get_pid_mode(self.entry)

        pv_ent = _get_entity_id(self.entry, CONF_PROCESS_VALUE_ENTITY)
        sp_ent = _get_entity_id(self.entry, CONF_SETPOINT_ENTITY)
        out_ent = _get_entity_id(self.entry, CONF_OUTPUT_ENTITY)

        pv = _state_to_float(self.hass.states.get(pv_ent)) if pv_ent else None
        sp = _state_to_float(self.hass.states.get(sp_ent)) if sp_ent else None

        if pv is not None and invert_pv:
            pv = -pv

        if sp is not None and invert_sp:
            sp = -sp

        if not enabled:
            self.pid.reset()
            return FlowState(pv=pv, sp=sp, out=None, error=None, enabled=False, status="disabled")

        if pv is None or sp is None:
            self.pid.reset()
            return FlowState(pv=pv, sp=sp, out=None, error=None, enabled=True, status="missing_input")

        error = sp - pv
        if pid_mode == PID_MODE_REVERSE:
            error = -error

        out, err = self.pid.step(pv=pv, error=error)

        if out_ent:
            await _set_output(self.hass, out_ent, out)
        else:
            _LOGGER.warning("No output entity configured.")

        return FlowState(pv=pv, sp=sp, out=out, error=err, enabled=True, status="running")

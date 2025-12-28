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
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_GRID_LIMITER_ENABLED,
    CONF_GRID_LIMITER_TYPE,
    CONF_GRID_LIMITER_LIMIT_W,
    CONF_GRID_LIMITER_DEADBAND_W,
    CONF_PID_DEADBAND,
    DEFAULT_INVERT_PV,
    DEFAULT_INVERT_SP,
    DEFAULT_GRID_POWER_INVERT,
    DEFAULT_PID_MODE,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_GRID_LIMITER_TYPE,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_PID_DEADBAND,
    PID_MODE_DIRECT,
    PID_MODE_REVERSE,
    GRID_LIMITER_TYPE_EXPORT,
    GRID_LIMITER_TYPE_IMPORT,
    GRID_LIMITER_STATE_NORMAL,
    GRID_LIMITER_STATE_LIMITING_IMPORT,
    GRID_LIMITER_STATE_LIMITING_EXPORT,
)
from .pid import PID, PIDConfig

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlowState:
    pv: float | None
    sp: float | None
    grid_power: float | None
    out: float | None
    error: float | None
    enabled: bool
    status: str
    limiter_state: str


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


def _coerce_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_pid_mode(entry: ConfigEntry) -> str:
    mode = entry.options.get(CONF_PID_MODE, DEFAULT_PID_MODE)
    if mode in (PID_MODE_DIRECT, PID_MODE_REVERSE):
        return mode
    _LOGGER.warning("Invalid PID mode '%s'; falling back to '%s'", mode, DEFAULT_PID_MODE)
    return DEFAULT_PID_MODE


def _get_limiter_type(entry: ConfigEntry) -> str:
    limiter_type = entry.options.get(CONF_GRID_LIMITER_TYPE, DEFAULT_GRID_LIMITER_TYPE)
    if limiter_type in (GRID_LIMITER_TYPE_IMPORT, GRID_LIMITER_TYPE_EXPORT):
        return limiter_type
    _LOGGER.warning(
        "Invalid grid limiter type '%s'; falling back to '%s'", limiter_type, DEFAULT_GRID_LIMITER_TYPE
    )
    return DEFAULT_GRID_LIMITER_TYPE


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
            kp=_coerce_float(entry.options.get(CONF_KP, DEFAULT_KP), DEFAULT_KP),
            ki=_coerce_float(entry.options.get(CONF_KI, DEFAULT_KI), DEFAULT_KI),
            kd=_coerce_float(entry.options.get(CONF_KD, DEFAULT_KD), DEFAULT_KD),
            min_output=min_output,
            max_output=max_output,
        )
        self.pid = PID(cfg)
        self._limiter_state = GRID_LIMITER_STATE_NORMAL
        self._last_output: float | None = None

    def _refresh_pid_config(self) -> None:
        min_output, max_output = _get_pid_limits(self.entry)
        cfg = PIDConfig(
            kp=_coerce_float(self.entry.options.get(CONF_KP, DEFAULT_KP), DEFAULT_KP),
            ki=_coerce_float(self.entry.options.get(CONF_KI, DEFAULT_KI), DEFAULT_KI),
            kd=_coerce_float(self.entry.options.get(CONF_KD, DEFAULT_KD), DEFAULT_KD),
            min_output=min_output,
            max_output=max_output,
        )
        self.pid.update_config(cfg)

    async def _async_update_data(self) -> FlowState:
        self._refresh_pid_config()

        enabled = self.entry.options.get(CONF_ENABLED, DEFAULT_ENABLED)
        invert_pv = self.entry.options.get(CONF_INVERT_PV, DEFAULT_INVERT_PV)
        invert_sp = self.entry.options.get(CONF_INVERT_SP, DEFAULT_INVERT_SP)
        grid_power_invert = self.entry.options.get(CONF_GRID_POWER_INVERT, DEFAULT_GRID_POWER_INVERT)
        limiter_enabled = self.entry.options.get(CONF_GRID_LIMITER_ENABLED, DEFAULT_GRID_LIMITER_ENABLED)
        limiter_type = _get_limiter_type(self.entry)
        limiter_limit_w = max(
            0.0,
            _coerce_float(
                self.entry.options.get(CONF_GRID_LIMITER_LIMIT_W, DEFAULT_GRID_LIMITER_LIMIT_W),
                DEFAULT_GRID_LIMITER_LIMIT_W,
            ),
        )
        limiter_deadband_w = max(
            0.0,
            _coerce_float(
                self.entry.options.get(CONF_GRID_LIMITER_DEADBAND_W, DEFAULT_GRID_LIMITER_DEADBAND_W),
                DEFAULT_GRID_LIMITER_DEADBAND_W,
            ),
        )
        pid_deadband = max(
            0.0, _coerce_float(self.entry.options.get(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND), DEFAULT_PID_DEADBAND)
        )
        pid_mode = _get_pid_mode(self.entry)

        pv_ent = _get_entity_id(self.entry, CONF_PROCESS_VALUE_ENTITY)
        sp_ent = _get_entity_id(self.entry, CONF_SETPOINT_ENTITY)
        out_ent = _get_entity_id(self.entry, CONF_OUTPUT_ENTITY)
        grid_ent = _get_entity_id(self.entry, CONF_GRID_POWER_ENTITY)

        pv = _state_to_float(self.hass.states.get(pv_ent)) if pv_ent else None
        sp = _state_to_float(self.hass.states.get(sp_ent)) if sp_ent else None
        grid_power = _state_to_float(self.hass.states.get(grid_ent)) if grid_ent else None

        if pv is not None and invert_pv:
            pv = -pv

        if sp is not None and invert_sp:
            sp = -sp

        if grid_power is not None and grid_power_invert:
            grid_power = -grid_power

        if not enabled:
            self.pid.reset()
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._last_output = None
            return FlowState(
                pv=pv,
                sp=sp,
                grid_power=grid_power,
                out=None,
                error=None,
                enabled=False,
                status="disabled",
                limiter_state=GRID_LIMITER_STATE_NORMAL,
            )

        pv_for_pid: float | None
        sp_for_pid: float | None
        status = "running"

        new_limiter_state = GRID_LIMITER_STATE_NORMAL
        limiter_active = limiter_enabled and grid_power is not None
        if limiter_active:
            if limiter_type == GRID_LIMITER_TYPE_IMPORT:
                if self._limiter_state == GRID_LIMITER_STATE_LIMITING_IMPORT:
                    if grid_power < limiter_limit_w - limiter_deadband_w:
                        new_limiter_state = GRID_LIMITER_STATE_NORMAL
                    else:
                        new_limiter_state = GRID_LIMITER_STATE_LIMITING_IMPORT
                elif grid_power > limiter_limit_w + limiter_deadband_w:
                    new_limiter_state = GRID_LIMITER_STATE_LIMITING_IMPORT
            elif limiter_type == GRID_LIMITER_TYPE_EXPORT:
                if self._limiter_state == GRID_LIMITER_STATE_LIMITING_EXPORT:
                    if grid_power > -(limiter_limit_w - limiter_deadband_w):
                        new_limiter_state = GRID_LIMITER_STATE_NORMAL
                    else:
                        new_limiter_state = GRID_LIMITER_STATE_LIMITING_EXPORT
                elif grid_power < -(limiter_limit_w + limiter_deadband_w):
                    new_limiter_state = GRID_LIMITER_STATE_LIMITING_EXPORT

        pv_for_pid = pv
        sp_for_pid = sp

        if limiter_active and new_limiter_state == GRID_LIMITER_STATE_LIMITING_IMPORT:
            pv_for_pid = grid_power
            sp_for_pid = limiter_limit_w
            status = GRID_LIMITER_STATE_LIMITING_IMPORT
        elif limiter_active and new_limiter_state == GRID_LIMITER_STATE_LIMITING_EXPORT:
            pv_for_pid = grid_power
            sp_for_pid = -limiter_limit_w
            status = GRID_LIMITER_STATE_LIMITING_EXPORT
        elif limiter_enabled and grid_power is None:
            status = "grid_power_unavailable"

        if pv_for_pid is None or sp_for_pid is None:
            self.pid.reset()
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._last_output = None
            return FlowState(
                pv=pv,
                sp=sp_for_pid,
                grid_power=grid_power,
                out=None,
                error=None,
                enabled=True,
                status="missing_input",
                limiter_state=new_limiter_state,
            )

        error = sp_for_pid - pv_for_pid
        if pid_mode == PID_MODE_REVERSE:
            error = -error

        if new_limiter_state == GRID_LIMITER_STATE_NORMAL and pid_deadband > 0 and abs(error) < pid_deadband:
            error = 0.0

        if new_limiter_state != self._limiter_state and self._last_output is not None:
            self.pid.apply_bumpless(current_output=self._last_output, pv=pv_for_pid, error=error)
        self._limiter_state = new_limiter_state

        out, err = self.pid.step(pv=pv_for_pid, error=error)
        self._last_output = out

        if out_ent:
            await _set_output(self.hass, out_ent, out)
        else:
            _LOGGER.warning("No output entity configured.")

        return FlowState(
            pv=pv_for_pid,
            sp=sp_for_pid,
            grid_power=grid_power,
            out=out,
            error=err,
            enabled=True,
            status=status,
            limiter_state=new_limiter_state,
        )

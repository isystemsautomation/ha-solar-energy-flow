from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping, Any

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
    CONF_RATE_LIMIT,
    CONF_RATE_LIMITER_ENABLED,
    CONF_RUNTIME_MODE,
    CONF_MANUAL_OUT_VALUE,
    CONF_MANUAL_SP_VALUE,
    DEFAULT_INVERT_PV,
    DEFAULT_INVERT_SP,
    DEFAULT_GRID_POWER_INVERT,
    DEFAULT_PID_MODE,
    DEFAULT_GRID_LIMITER_ENABLED,
    DEFAULT_GRID_LIMITER_TYPE,
    DEFAULT_GRID_LIMITER_LIMIT_W,
    DEFAULT_GRID_LIMITER_DEADBAND_W,
    DEFAULT_PID_DEADBAND,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_LIMITER_ENABLED,
    DEFAULT_RUNTIME_MODE,
    DEFAULT_MANUAL_OUT_VALUE,
    DEFAULT_MANUAL_SP_VALUE,
    PID_MODE_DIRECT,
    PID_MODE_REVERSE,
    GRID_LIMITER_TYPE_EXPORT,
    GRID_LIMITER_TYPE_IMPORT,
    GRID_LIMITER_STATE_NORMAL,
    GRID_LIMITER_STATE_LIMITING_IMPORT,
    GRID_LIMITER_STATE_LIMITING_EXPORT,
    RUNTIME_MODE_AUTO_SP,
    RUNTIME_MODE_HOLD,
    RUNTIME_MODE_MANUAL_OUT,
    RUNTIME_MODE_MANUAL_SP,
)
from .pid import PID, PIDConfig

_LOGGER = logging.getLogger(__name__)

_OUTPUT_DOMAINS = {"number", "input_number"}


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
    runtime_mode: str
    manual_sp_value: float | None
    manual_out_value: float
    manual_sp_display_value: float | None


def _state_to_float(state, entity_id: str | None = None) -> float | None:
    if state is None:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError) as err:
        _LOGGER.warning(
            "Could not convert state for %s to float (raw=%s): %s",
            entity_id or "unknown entity",
            getattr(state, "state", state),
            err,
        )
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


def _get_update_interval_seconds_from_options(options: Mapping[str, Any]) -> int:
    raw_interval = options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    try:
        interval = int(raw_interval)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_INTERVAL
    if interval < 1:
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


def _get_pid_limits_from_options(options: Mapping[str, Any]) -> tuple[float, float]:
    raw_min = options.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT)
    raw_max = options.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT)

    try:
        min_output = float(raw_min)
        max_output = float(raw_max)
    except (TypeError, ValueError):
        return DEFAULT_MIN_OUTPUT, DEFAULT_MAX_OUTPUT

    if min_output > max_output:
        min_output, max_output = max_output, min_output

    return min_output, max_output


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


async def _set_output(hass: HomeAssistant, entity_id: str, value: float) -> bool:
    value = round(value, 1)
    domain = _get_domain(entity_id)

    if domain not in _OUTPUT_DOMAINS:
        _LOGGER.warning("Unsupported output entity domain '%s' for %s. Use number.* or input_number.*", domain, entity_id)
        return False

    try:
        await hass.services.async_call(domain, "set_value", {"entity_id": entity_id, "value": value}, blocking=True)
    except Exception as err:
        _LOGGER.warning("Failed to set output %s: %s", entity_id, err)
        return False

    return True


def _get_entity_id(entry: ConfigEntry, key: str) -> str | None:
    return entry.options.get(key) or entry.data.get(key)


def _get_domain(entity_id: str | None) -> str | None:
    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


class SolarEnergyFlowCoordinator(DataUpdateCoordinator[FlowState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.options_cache: dict[str, Any] = dict(entry.options)
        self._runtime_mode = entry.options.get(CONF_RUNTIME_MODE, DEFAULT_RUNTIME_MODE)

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
        self.pid = PID(cfg, entry_id=entry.entry_id)
        self._limiter_state = GRID_LIMITER_STATE_NORMAL
        self._last_output: float | None = None
        self._last_pv_for_pid: float | None = None
        self._last_sp_for_pid: float | None = None
        manual_sp_opt = entry.options.get(CONF_MANUAL_SP_VALUE)
        self._manual_sp_value: float | None = None
        self._manual_sp_initialized = False
        if manual_sp_opt is not None:
            try:
                self._manual_sp_value = float(manual_sp_opt)
                self._manual_sp_initialized = True
            except (TypeError, ValueError):
                _LOGGER.warning(
                    "Invalid manual SP '%s'; starting without saved manual setpoint for %s",
                    manual_sp_opt,
                    entry.entry_id,
                )
        self._manual_out_value: float = _coerce_float(
            entry.options.get(CONF_MANUAL_OUT_VALUE, DEFAULT_MANUAL_OUT_VALUE), DEFAULT_MANUAL_OUT_VALUE
        )
        self._previous_runtime_mode = self._runtime_mode
        self._invalid_output_reported = False
        self._output_write_failed_reported = False

    def _get_normal_setpoint_value(self) -> float | None:
        """Return the current external setpoint with inversion applied (no limiter)."""
        sp_ent = _get_entity_id(self.entry, CONF_SETPOINT_ENTITY)
        sp = _state_to_float(self.hass.states.get(sp_ent), sp_ent) if sp_ent else None
        if sp is not None and self.entry.options.get(CONF_INVERT_SP, DEFAULT_INVERT_SP):
            sp = -sp
        return sp

    def set_manual_sp_from_normal_setpoint(self, sp: float | None = None) -> float | None:
        """Set the manual SP to the current AUTO SP value for bumpless transfer."""
        value = sp if sp is not None else self._get_normal_setpoint_value()
        if value is None:
            return None
        self._manual_sp_value = value
        self._manual_sp_initialized = True
        return value

    def _build_pid_config_from_options(self, options: Mapping[str, Any]) -> PIDConfig:
        min_output, max_output = _get_pid_limits_from_options(options)
        return PIDConfig(
            kp=_coerce_float(options.get(CONF_KP, DEFAULT_KP), DEFAULT_KP),
            ki=_coerce_float(options.get(CONF_KI, DEFAULT_KI), DEFAULT_KI),
            kd=_coerce_float(options.get(CONF_KD, DEFAULT_KD), DEFAULT_KD),
            min_output=min_output,
            max_output=max_output,
        )

    def options_require_reload(self, old: Mapping[str, Any], new: Mapping[str, Any]) -> bool:
        wiring_keys = {
            CONF_PROCESS_VALUE_ENTITY,
            CONF_SETPOINT_ENTITY,
            CONF_OUTPUT_ENTITY,
            CONF_GRID_POWER_ENTITY,
            CONF_INVERT_PV,
            CONF_INVERT_SP,
            CONF_GRID_POWER_INVERT,
        }

        for key in wiring_keys:
            if old.get(key) != new.get(key):
                return True
        return False

    def apply_options(self, options: Mapping[str, Any]) -> None:
        """Apply runtime tuning without resetting PID state."""

        self.options_cache = dict(options)
        interval_seconds = _get_update_interval_seconds_from_options(options)
        self.update_interval = timedelta(seconds=interval_seconds)
        if CONF_RUNTIME_MODE in options:
            self._runtime_mode = options[CONF_RUNTIME_MODE]
        if CONF_MANUAL_OUT_VALUE in options:
            self._manual_out_value = _coerce_float(options.get(CONF_MANUAL_OUT_VALUE), self._manual_out_value)
        self.pid.apply_options(self._build_pid_config_from_options(options))

    async def _async_update_data(self) -> FlowState:
        prev_limiter_state = self._limiter_state
        prev_sp_for_pid = self._last_sp_for_pid
        prev_pv_for_pid = self._last_pv_for_pid
        prev_runtime_mode = self._previous_runtime_mode
        prev_manual_sp_value = self._manual_sp_value
        output_write_failed = False

        enabled = self.entry.options.get(CONF_ENABLED, DEFAULT_ENABLED)
        min_output, max_output = _get_pid_limits_from_options(self.entry.options)
        invert_pv = self.entry.options.get(CONF_INVERT_PV, DEFAULT_INVERT_PV)
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
        rate_limiter_enabled = self.entry.options.get(CONF_RATE_LIMITER_ENABLED, DEFAULT_RATE_LIMITER_ENABLED)
        rate_limit = max(0.0, _coerce_float(self.entry.options.get(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT), DEFAULT_RATE_LIMIT))
        pid_deadband = max(
            0.0, _coerce_float(self.entry.options.get(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND), DEFAULT_PID_DEADBAND)
        )
        pid_mode = _get_pid_mode(self.entry)
        runtime_mode = self._runtime_mode
        if runtime_mode not in (
            RUNTIME_MODE_AUTO_SP,
            RUNTIME_MODE_MANUAL_SP,
            RUNTIME_MODE_HOLD,
            RUNTIME_MODE_MANUAL_OUT,
        ):
            runtime_mode = DEFAULT_RUNTIME_MODE
        if runtime_mode != self._runtime_mode:
            self._runtime_mode = runtime_mode

        if runtime_mode != prev_runtime_mode:
            _LOGGER.debug(
                "Runtime mode change entry=%s mode=%s last_output=%s manual_sp_before=%s manual_sp_after=%s manual_out=%s",
                self.entry.entry_id,
                runtime_mode,
                self._last_output,
                prev_manual_sp_value,
                self._manual_sp_value,
                self._manual_out_value,
            )

        pv_ent = _get_entity_id(self.entry, CONF_PROCESS_VALUE_ENTITY)
        out_ent = _get_entity_id(self.entry, CONF_OUTPUT_ENTITY)
        grid_ent = _get_entity_id(self.entry, CONF_GRID_POWER_ENTITY)

        pv = _state_to_float(self.hass.states.get(pv_ent), pv_ent) if pv_ent else None
        grid_power = _state_to_float(self.hass.states.get(grid_ent), grid_ent) if grid_ent else None

        if pv is not None and invert_pv:
            pv = -pv

        sp = self._get_normal_setpoint_value()

        if grid_power is not None and grid_power_invert:
            grid_power = -grid_power

        if not self._manual_sp_initialized and sp is not None:
            self._manual_sp_value = sp
            self._manual_sp_initialized = True
            _LOGGER.debug(
                "Initialized manual SP from auto setpoint entry=%s sp=%s",
                self.entry.entry_id,
                sp,
            )

        mode_changed = runtime_mode != prev_runtime_mode

        if runtime_mode == RUNTIME_MODE_MANUAL_SP and (mode_changed or self._manual_sp_value is None):
            if sp is not None:
                new_manual_sp = self.set_manual_sp_from_normal_setpoint(sp)
                if new_manual_sp is not None:
                    _LOGGER.debug(
                        "Updated manual SP on entering MANUAL SP entry=%s sp=%s",
                        self.entry.entry_id,
                        new_manual_sp,
                    )
            elif mode_changed:
                self._manual_sp_value = None
                self._manual_sp_initialized = False

        manual_sp_display_value: float | None = self._manual_sp_value
        if runtime_mode == RUNTIME_MODE_AUTO_SP and sp is not None:
            manual_sp_display_value = sp
        elif runtime_mode == RUNTIME_MODE_MANUAL_SP and self._manual_sp_value is None:
            manual_sp_display_value = sp

        def _log_mode_change() -> None:
            if not mode_changed:
                return
            _LOGGER.debug(
                "Runtime mode applied entry=%s %s->%s manual_sp_before=%s manual_sp_after=%s manual_sp_display=%s manual_out=%s",
                self.entry.entry_id,
                prev_runtime_mode,
                runtime_mode,
                prev_manual_sp_value,
                self._manual_sp_value,
                manual_sp_display_value,
                self._manual_out_value,
            )

        def _apply_output_status(base_status: str) -> str:
            nonlocal output_write_failed
            if output_write_failed:
                if not self._output_write_failed_reported:
                    _LOGGER.warning(
                        "Failed to write output for %s; controller status set to output_write_failed",
                        self.entry.entry_id,
                    )
                    self._output_write_failed_reported = True
                return "output_write_failed"
            self._output_write_failed_reported = False
            return base_status

        out_domain = _get_domain(out_ent)
        if out_ent and out_domain not in _OUTPUT_DOMAINS:
            if not self._invalid_output_reported:
                _LOGGER.warning(
                    "Unsupported output entity domain '%s' for %s. Use number.* or input_number.*",
                    out_domain,
                    out_ent,
                )
                self._invalid_output_reported = True
            self._previous_runtime_mode = runtime_mode
            _log_mode_change()
            return FlowState(
                pv=pv,
                sp=sp,
                grid_power=grid_power,
                out=None,
                error=None,
                enabled=enabled,
                status="invalid_output",
                limiter_state=self._limiter_state,
                runtime_mode=runtime_mode,
                manual_sp_value=self._manual_sp_value,
                manual_out_value=self._manual_out_value,
                manual_sp_display_value=manual_sp_display_value,
            )

        if not enabled:
            self.pid.reset()
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            safe_output = min_output
            if out_ent:
                output_write_failed = not await _set_output(self.hass, out_ent, safe_output)
            self._last_output = safe_output
            self._last_pv_for_pid = None
            self._last_sp_for_pid = None
            self._manual_out_value = safe_output
            self._previous_runtime_mode = runtime_mode
            _log_mode_change()
            return FlowState(
                pv=pv,
                sp=sp,
                grid_power=grid_power,
                out=safe_output,
                error=None,
                enabled=False,
                status=_apply_output_status("disabled"),
                limiter_state=GRID_LIMITER_STATE_NORMAL,
                runtime_mode=runtime_mode,
                manual_sp_value=self._manual_sp_value,
                manual_out_value=self._manual_out_value,
                manual_sp_display_value=manual_sp_display_value,
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
        sp_for_pid = self._manual_sp_value if runtime_mode == RUNTIME_MODE_MANUAL_SP else sp

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

        if runtime_mode == RUNTIME_MODE_HOLD:
            held_output = self._last_output if self._last_output is not None else min_output
            if out_ent:
                output_write_failed = not await _set_output(self.hass, out_ent, held_output)
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._manual_out_value = held_output
            self._last_output = held_output
            self._previous_runtime_mode = runtime_mode
            _log_mode_change()
            return FlowState(
                pv=pv,
                sp=sp,
                grid_power=grid_power,
                out=held_output,
                error=None,
                enabled=True,
                status=_apply_output_status("hold"),
                limiter_state=self._limiter_state,
                runtime_mode=runtime_mode,
                manual_sp_value=self._manual_sp_value,
                manual_out_value=self._manual_out_value,
                manual_sp_display_value=manual_sp_display_value,
            )

        if runtime_mode == RUNTIME_MODE_MANUAL_OUT:
            if prev_runtime_mode != RUNTIME_MODE_MANUAL_OUT:
                if self._last_output is not None:
                    self._manual_out_value = self._last_output
                else:
                    self._manual_out_value = _coerce_float(self._manual_out_value, DEFAULT_MANUAL_OUT_VALUE)
            if out_ent:
                output_write_failed = not await _set_output(self.hass, out_ent, self._manual_out_value)
            self._last_output = self._manual_out_value
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._previous_runtime_mode = runtime_mode
            _log_mode_change()
            return FlowState(
                pv=pv,
                sp=sp,
                grid_power=grid_power,
                out=self._manual_out_value,
                error=None,
                enabled=True,
                status=_apply_output_status("manual_out"),
                limiter_state=self._limiter_state,
                runtime_mode=runtime_mode,
                manual_sp_value=self._manual_sp_value,
                manual_out_value=self._manual_out_value,
                manual_sp_display_value=manual_sp_display_value,
            )

        if pv_for_pid is None or sp_for_pid is None:
            self.pid.reset()
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._last_output = None
            self._last_pv_for_pid = None
            self._last_sp_for_pid = None
            self._previous_runtime_mode = runtime_mode
            _log_mode_change()
            return FlowState(
                pv=pv,
                sp=sp_for_pid,
                grid_power=grid_power,
                out=None,
                error=None,
                enabled=True,
                status="missing_input",
                limiter_state=new_limiter_state,
                runtime_mode=runtime_mode,
                manual_sp_value=self._manual_sp_value,
                manual_out_value=self._manual_out_value,
                manual_sp_display_value=manual_sp_display_value,
            )

        error = sp_for_pid - pv_for_pid
        if pid_mode == PID_MODE_REVERSE:
            error = -error

        if new_limiter_state == GRID_LIMITER_STATE_NORMAL and pid_deadband > 0 and abs(error) < pid_deadband:
            error = 0.0

        current_output = self._last_output
        bumpless_needed = prev_runtime_mode in (RUNTIME_MODE_MANUAL_OUT, RUNTIME_MODE_HOLD)
        if not bumpless_needed and current_output is not None:
            if new_limiter_state != prev_limiter_state:
                bumpless_needed = True
            elif prev_sp_for_pid is not None and sp_for_pid is not None and sp_for_pid != prev_sp_for_pid:
                bumpless_needed = True

        if prev_runtime_mode == RUNTIME_MODE_MANUAL_OUT:
            current_output = self._manual_out_value
            self._last_output = current_output
        elif prev_runtime_mode == RUNTIME_MODE_HOLD:
            current_output = self._last_output

        if bumpless_needed and current_output is not None:
            self.pid.bumpless_transfer(current_output=current_output, error=error, pv=pv_for_pid)

        self._limiter_state = new_limiter_state

        out, err = self.pid.step(
            pv=pv_for_pid,
            error=error,
            last_output=self._last_output,
            rate_limiter_enabled=rate_limiter_enabled,
            rate_limit=rate_limit,
        )

        if out_ent:
            output_write_failed = not await _set_output(self.hass, out_ent, out)
        else:
            _LOGGER.warning("No output entity configured.")

        self._last_output = out
        self._last_pv_for_pid = pv_for_pid
        self._last_sp_for_pid = sp_for_pid
        if runtime_mode != RUNTIME_MODE_MANUAL_OUT:
            self._manual_out_value = out
        self._previous_runtime_mode = runtime_mode
        _log_mode_change()

        return FlowState(
            pv=pv_for_pid,
            sp=sp_for_pid,
            grid_power=grid_power,
            out=out,
            error=err,
            enabled=True,
            status=_apply_output_status(status),
            limiter_state=new_limiter_state,
            runtime_mode=runtime_mode,
            manual_sp_value=self._manual_sp_value,
            manual_out_value=self._manual_out_value,
            manual_sp_display_value=manual_sp_display_value,
        )

# Manual test checklist:
# 1) change limiter limit while running -> output continues smoothly (no jump to 0)
# 2) change deadband -> no reset
# 3) change kp/ki -> no reset
# 4) start a big load to trigger limiter -> smooth transition; stop load -> smooth return.

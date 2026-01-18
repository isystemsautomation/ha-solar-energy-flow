from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping, Any, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
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
    CONF_MAX_OUTPUT_STEP,
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
    CONF_OUTPUT_EPSILON,
    CONF_PV_MIN,
    CONF_PV_MAX,
    CONF_SP_MIN,
    CONF_SP_MAX,
    CONF_GRID_MIN,
    CONF_GRID_MAX,
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
    DEFAULT_MAX_OUTPUT_STEP,
    DEFAULT_OUTPUT_EPSILON,
    DEFAULT_PV_MIN,
    DEFAULT_PV_MAX,
    DEFAULT_SP_MIN,
    DEFAULT_SP_MAX,
    DEFAULT_GRID_MIN,
    DEFAULT_GRID_MAX,
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
from .pid import PID, PIDConfig, PIDStepResult

_LOGGER = logging.getLogger(__name__)

_OUTPUT_DOMAINS = {"number", "input_number"}


@dataclass
class FlowState:
    pv: float | None
    sp: float | None
    grid_power: float | None
    out: float | None
    output_pre_rate_limit: float | None
    error: float | None
    enabled: bool
    status: str
    limiter_state: str
    runtime_mode: str
    manual_sp_value: float | None
    manual_out_value: float
    manual_sp_display_value: float | None
    p_term: float | None
    i_term: float | None
    d_term: float | None


@dataclass
class RuntimeOptions:
    enabled: bool
    min_output: float
    max_output: float
    pv_min: float
    pv_max: float
    sp_min: float
    sp_max: float
    grid_min: float
    grid_max: float
    invert_pv: bool
    grid_power_invert: bool
    limiter_enabled: bool
    limiter_type: str
    limiter_limit_w: float
    limiter_deadband_w: float
    rate_limiter_enabled: bool
    rate_limit: float
    pid_deadband: float
    pid_mode: str
    runtime_mode: str
    max_output_step: float
    output_epsilon: float


@dataclass
class InputValues:
    pv: float | None
    sp: float | None
    grid_power: float | None


@dataclass
class SetpointContext:
    runtime_mode: str
    manual_sp_value: float | None
    manual_sp_display_value: float | None
    pv_for_pid: float | None
    sp_for_pid: float | None
    status: str
    mode_changed: bool


@dataclass
class LimiterResult:
    pv_for_pid: float | None
    sp_for_pid: float | None
    pv_pct: float | None
    sp_pct: float | None
    status: str
    limiter_state: str


@dataclass
class OutputPlan:
    output: float | None
    output_pre_rate_limit: float | None
    error: float | None
    status: str
    limiter_state: str
    manual_out_value: float
    p_term: float | None
    i_term: float | None
    d_term: float | None


@dataclass
class OutputWriteResult:
    output: float | None
    status: str
    write_failed: bool


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


def _normalize_value(value: float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    span = maximum - minimum
    if span <= 0:
        return None
    pct = (value - minimum) * 100.0 / span
    return max(0.0, min(100.0, pct))


def _denormalize_value(percent: float | None, minimum: float, maximum: float) -> float | None:
    if percent is None:
        return None
    span = maximum - minimum
    if span <= 0:
        return None
    return minimum + (percent / 100.0) * span


def _range_or_default(min_raw, max_raw, default_min: float, default_max: float) -> tuple[float, float]:
    try:
        min_val = float(min_raw)
        max_val = float(max_raw)
    except (TypeError, ValueError):
        return default_min, default_max
    if max_val <= min_val:
        return default_min, default_max
    return min_val, max_val


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
    except (HomeAssistantError, asyncio.TimeoutError, ValueError) as err:
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

        cfg = PIDConfig(
            kp=_coerce_float(entry.options.get(CONF_KP, DEFAULT_KP), DEFAULT_KP),
            ki=_coerce_float(entry.options.get(CONF_KI, DEFAULT_KI), DEFAULT_KI),
            kd=_coerce_float(entry.options.get(CONF_KD, DEFAULT_KD), DEFAULT_KD),
            min_output=0.0,
            max_output=100.0,
        )
        self.pid = PID(cfg, entry_id=entry.entry_id)
        self._limiter_state = GRID_LIMITER_STATE_NORMAL
        self._last_output_raw: float | None = None
        self._last_output_pct: float | None = None
        self._last_pv_pct: float | None = None
        self._last_sp_pct: float | None = None
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

    def _get_range_value(
        self,
        min_key: str,
        max_key: str,
        default_min: float,
        default_max: float,
    ) -> tuple[float, float]:
        min_raw = self.entry.options.get(min_key, self.entry.data.get(min_key, default_min))
        max_raw = self.entry.options.get(max_key, self.entry.data.get(max_key, default_max))
        return _range_or_default(min_raw, max_raw, default_min, default_max)

    @staticmethod
    def _output_percent_from_raw(value: float | None, options: RuntimeOptions) -> float | None:
        return _normalize_value(value, options.min_output, options.max_output)

    @staticmethod
    def _output_raw_from_percent(value: float | None, options: RuntimeOptions) -> float | None:
        return _denormalize_value(value, options.min_output, options.max_output)

    @staticmethod
    def _rate_limit_to_percent(rate_limit_raw: float, options: RuntimeOptions) -> float:
        span = options.max_output - options.min_output
        if span <= 0:
            return 0.0
        return rate_limit_raw * 100.0 / span

    @staticmethod
    def _deadband_to_percent(deadband_raw: float, span: float) -> float:
        if span <= 0:
            return 0.0
        return deadband_raw * 100.0 / span

    def _build_runtime_options(self) -> RuntimeOptions:
        enabled = self.entry.options.get(CONF_ENABLED, DEFAULT_ENABLED)
        min_output, max_output = _get_pid_limits_from_options(self.entry.options)
        pv_min, pv_max = self._get_range_value(CONF_PV_MIN, CONF_PV_MAX, DEFAULT_PV_MIN, DEFAULT_PV_MAX)
        sp_min, sp_max = self._get_range_value(CONF_SP_MIN, CONF_SP_MAX, DEFAULT_SP_MIN, DEFAULT_SP_MAX)
        grid_min, grid_max = self._get_range_value(CONF_GRID_MIN, CONF_GRID_MAX, DEFAULT_GRID_MIN, DEFAULT_GRID_MAX)
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

        return RuntimeOptions(
            enabled=enabled,
            min_output=min_output,
            max_output=max_output,
            pv_min=pv_min,
            pv_max=pv_max,
            sp_min=sp_min,
            sp_max=sp_max,
            grid_min=grid_min,
            grid_max=grid_max,
            invert_pv=self.entry.options.get(CONF_INVERT_PV, DEFAULT_INVERT_PV),
            grid_power_invert=self.entry.options.get(CONF_GRID_POWER_INVERT, DEFAULT_GRID_POWER_INVERT),
            limiter_enabled=self.entry.options.get(CONF_GRID_LIMITER_ENABLED, DEFAULT_GRID_LIMITER_ENABLED),
            limiter_type=_get_limiter_type(self.entry),
            limiter_limit_w=max(
                0.0,
                _coerce_float(
                    self.entry.options.get(CONF_GRID_LIMITER_LIMIT_W, DEFAULT_GRID_LIMITER_LIMIT_W),
                    DEFAULT_GRID_LIMITER_LIMIT_W,
                ),
            ),
            limiter_deadband_w=max(
                0.0,
                _coerce_float(
                    self.entry.options.get(CONF_GRID_LIMITER_DEADBAND_W, DEFAULT_GRID_LIMITER_DEADBAND_W),
                    DEFAULT_GRID_LIMITER_DEADBAND_W,
                ),
            ),
            rate_limiter_enabled=self.entry.options.get(CONF_RATE_LIMITER_ENABLED, DEFAULT_RATE_LIMITER_ENABLED),
            rate_limit=max(
                0.0, _coerce_float(self.entry.options.get(CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT), DEFAULT_RATE_LIMIT)
            ),
            pid_deadband=max(
                0.0, _coerce_float(self.entry.options.get(CONF_PID_DEADBAND, DEFAULT_PID_DEADBAND), DEFAULT_PID_DEADBAND)
            ),
            pid_mode=_get_pid_mode(self.entry),
            runtime_mode=runtime_mode,
            max_output_step=max(
                0.0,
                _coerce_float(
                    self.entry.options.get(CONF_MAX_OUTPUT_STEP, DEFAULT_MAX_OUTPUT_STEP),
                    DEFAULT_MAX_OUTPUT_STEP,
                ),
            ),
            output_epsilon=max(
                0.0,
                _coerce_float(
                    self.entry.options.get(CONF_OUTPUT_EPSILON, DEFAULT_OUTPUT_EPSILON),
                    DEFAULT_OUTPUT_EPSILON,
                ),
            ),
        )

    def _read_inputs(self, options: RuntimeOptions) -> InputValues:
        pv_ent = _get_entity_id(self.entry, CONF_PROCESS_VALUE_ENTITY)
        grid_ent = _get_entity_id(self.entry, CONF_GRID_POWER_ENTITY)

        pv = _state_to_float(self.hass.states.get(pv_ent), pv_ent) if pv_ent else None
        grid_power = _state_to_float(self.hass.states.get(grid_ent), grid_ent) if grid_ent else None

        if pv is not None and options.invert_pv:
            pv = -pv
        if grid_power is not None and options.grid_power_invert:
            grid_power = -grid_power

        sp = self._get_normal_setpoint_value()

        if not self._manual_sp_initialized and sp is not None:
            self._manual_sp_value = sp
            self._manual_sp_initialized = True
            _LOGGER.debug(
                "Initialized manual SP from auto setpoint entry=%s sp=%s",
                self.entry.entry_id,
                sp,
            )

        return InputValues(pv=pv, sp=sp, grid_power=grid_power)

    def _compute_setpoint_context(
        self,
        options: RuntimeOptions,
        inputs: InputValues,
        prev_runtime_mode: str,
        prev_manual_sp_value: float | None,
    ) -> SetpointContext:
        runtime_mode = options.runtime_mode
        mode_changed = runtime_mode != prev_runtime_mode

        if runtime_mode == RUNTIME_MODE_MANUAL_SP and (mode_changed or self._manual_sp_value is None):
            if inputs.sp is not None:
                new_manual_sp = self.set_manual_sp_from_normal_setpoint(inputs.sp)
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
        if runtime_mode == RUNTIME_MODE_AUTO_SP and inputs.sp is not None:
            manual_sp_display_value = inputs.sp
        elif runtime_mode == RUNTIME_MODE_MANUAL_SP and self._manual_sp_value is None:
            manual_sp_display_value = inputs.sp

        pv_for_pid: float | None = inputs.pv
        sp_for_pid: float | None = self._manual_sp_value if runtime_mode == RUNTIME_MODE_MANUAL_SP else inputs.sp

        status = "running"

        return SetpointContext(
            runtime_mode=runtime_mode,
            manual_sp_value=self._manual_sp_value,
            manual_sp_display_value=manual_sp_display_value,
            pv_for_pid=pv_for_pid,
            sp_for_pid=sp_for_pid,
            status=status,
            mode_changed=mode_changed,
        )

    def _apply_grid_limiter(
        self,
        options: RuntimeOptions,
        inputs: InputValues,
        setpoint: SetpointContext,
        prev_limiter_state: str,
    ) -> LimiterResult:
        new_limiter_state = GRID_LIMITER_STATE_NORMAL
        limiter_active = options.limiter_enabled and inputs.grid_power is not None
        status = setpoint.status
        pv_for_pid = setpoint.pv_for_pid
        sp_for_pid = setpoint.sp_for_pid
        limiter_target_raw = options.limiter_limit_w
        if options.limiter_type == GRID_LIMITER_TYPE_EXPORT:
            limiter_target_raw = -options.limiter_limit_w

        pv_pct = _normalize_value(pv_for_pid, options.pv_min, options.pv_max)
        sp_pct = _normalize_value(sp_for_pid, options.sp_min, options.sp_max)
        grid_pct = _normalize_value(inputs.grid_power, options.grid_min, options.grid_max)
        limit_pct = _normalize_value(limiter_target_raw, options.grid_min, options.grid_max)
        grid_span = options.grid_max - options.grid_min
        deadband_pct = self._deadband_to_percent(options.limiter_deadband_w, grid_span)

        if limiter_active and grid_pct is not None and limit_pct is not None:
            if options.limiter_type == GRID_LIMITER_TYPE_IMPORT:
                if prev_limiter_state == GRID_LIMITER_STATE_LIMITING_IMPORT:
                    if grid_pct < limit_pct - deadband_pct:
                        new_limiter_state = GRID_LIMITER_STATE_NORMAL
                    else:
                        new_limiter_state = GRID_LIMITER_STATE_LIMITING_IMPORT
                elif grid_pct > limit_pct + deadband_pct:
                    new_limiter_state = GRID_LIMITER_STATE_LIMITING_IMPORT
            elif options.limiter_type == GRID_LIMITER_TYPE_EXPORT:
                if prev_limiter_state == GRID_LIMITER_STATE_LIMITING_EXPORT:
                    if grid_pct > limit_pct + deadband_pct:
                        new_limiter_state = GRID_LIMITER_STATE_NORMAL
                    else:
                        new_limiter_state = GRID_LIMITER_STATE_LIMITING_EXPORT
                elif grid_pct < limit_pct - deadband_pct:
                    new_limiter_state = GRID_LIMITER_STATE_LIMITING_EXPORT

        if limiter_active and new_limiter_state == GRID_LIMITER_STATE_LIMITING_IMPORT:
            pv_for_pid = inputs.grid_power
            sp_for_pid = options.limiter_limit_w
            pv_pct = grid_pct
            sp_pct = limit_pct
            status = GRID_LIMITER_STATE_LIMITING_IMPORT
        elif limiter_active and new_limiter_state == GRID_LIMITER_STATE_LIMITING_EXPORT:
            pv_for_pid = inputs.grid_power
            sp_for_pid = -options.limiter_limit_w
            pv_pct = grid_pct
            sp_pct = limit_pct
            status = GRID_LIMITER_STATE_LIMITING_EXPORT
        elif options.limiter_enabled and (inputs.grid_power is None or grid_pct is None or limit_pct is None):
            status = "grid_power_unavailable"

        return LimiterResult(
            pv_for_pid=pv_for_pid,
            sp_for_pid=sp_for_pid,
            pv_pct=pv_pct,
            sp_pct=sp_pct,
            status=status,
            limiter_state=new_limiter_state,
        )

    def _apply_output_fence(self, desired_output: float, options: RuntimeOptions) -> Tuple[float, bool]:
        if not math.isfinite(desired_output):
            _LOGGER.warning(
                "Invalid (non-finite) desired output %s for %s; skipping write",
                desired_output,
                self.entry.entry_id,
            )
            return self._last_output_raw, False

        clamped = max(options.min_output, min(options.max_output, desired_output))
        limited = clamped
        last_output = self._last_output_raw

        if options.max_output_step > 0 and last_output is not None:
            limited = max(last_output - options.max_output_step, min(last_output + options.max_output_step, clamped))

        if last_output is not None and options.output_epsilon > 0 and abs(limited - last_output) <= options.output_epsilon:
            return last_output, False

        return limited, True

    def _log_runtime_mode_change(
        self,
        prev_runtime_mode: str,
        runtime_mode: str,
        prev_manual_sp_value: float | None,
        manual_sp_display_value: float | None,
    ) -> None:
        if prev_runtime_mode == runtime_mode:
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

    def get_runtime_mode(self) -> str:
        """Return the current runtime mode from the latest data or internal state."""
        data_runtime_mode = getattr(getattr(self, "data", None), "runtime_mode", None)
        if data_runtime_mode:
            return data_runtime_mode
        runtime_mode = self._runtime_mode or self.entry.options.get(CONF_RUNTIME_MODE, DEFAULT_RUNTIME_MODE)
        if runtime_mode not in (
            RUNTIME_MODE_AUTO_SP,
            RUNTIME_MODE_MANUAL_SP,
            RUNTIME_MODE_HOLD,
            RUNTIME_MODE_MANUAL_OUT,
        ):
            return DEFAULT_RUNTIME_MODE
        return runtime_mode

    def get_manual_out_value(self) -> float:
        return self._manual_out_value

    def get_manual_sp_value(self) -> float | None:
        return self._manual_sp_value

    async def async_set_manual_out(self, value: float) -> None:
        self._manual_out_value = value
        if self._runtime_mode == RUNTIME_MODE_MANUAL_OUT:
            self._last_output_raw = value
            self._last_output_pct = self._output_percent_from_raw(value, self._build_runtime_options())

    async def async_set_manual_sp(self, value: float) -> None:
        self._manual_sp_value = value
        self._manual_sp_initialized = True

    async def async_snap_back_manual_out(self) -> None:
        await self.async_request_refresh()

    async def async_snap_back_manual_sp(self) -> None:
        await self.async_request_refresh()

    async def async_reset_manual_sp(self) -> None:
        self._manual_sp_value = None
        self._manual_sp_initialized = False

    async def _maybe_write_output(
        self,
        out_ent: str | None,
        desired_output: float | None,
        options: RuntimeOptions,
    ) -> OutputWriteResult:
        if desired_output is None:
            return OutputWriteResult(output=self._last_output_raw, status="", write_failed=False)

        final_output, should_write = self._apply_output_fence(desired_output, options)
        write_failed = False

        if out_ent:
            if should_write:
                write_failed = not await _set_output(self.hass, out_ent, final_output)
            # If we intentionally skipped writing, keep the previous output value.
        else:
            _LOGGER.warning("No output entity configured.")

        if should_write or self._last_output_raw is None:
            self._last_output_raw = final_output

        self._last_output_pct = self._output_percent_from_raw(self._last_output_raw, options)

        return OutputWriteResult(output=self._last_output_raw, status="", write_failed=write_failed)

    def _apply_output_status(self, base_status: str, output_write_failed: bool) -> str:
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

    def _build_pid_config_from_options(self, options: Mapping[str, Any]) -> PIDConfig:
        return PIDConfig(
            kp=_coerce_float(options.get(CONF_KP, DEFAULT_KP), DEFAULT_KP),
            ki=_coerce_float(options.get(CONF_KI, DEFAULT_KI), DEFAULT_KI),
            kd=_coerce_float(options.get(CONF_KD, DEFAULT_KD), DEFAULT_KD),
            min_output=0.0,
            max_output=100.0,
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

    def _calculate_output_plan(
        self,
        options: RuntimeOptions,
        inputs: InputValues,
        setpoint: SetpointContext,
        limiter_result: LimiterResult,
        prev_runtime_mode: str,
        prev_limiter_state: str,
        prev_sp_for_pid: float | None,
        prev_pv_for_pid: float | None,
    ) -> OutputPlan:
        runtime_mode = setpoint.runtime_mode
        pv_for_pid_raw = limiter_result.pv_for_pid
        sp_for_pid_raw = limiter_result.sp_for_pid
        pv_for_pid = limiter_result.pv_pct
        sp_for_pid = limiter_result.sp_pct
        status = limiter_result.status
        manual_sp_display_value = setpoint.manual_sp_display_value
        output_span = options.max_output - options.min_output
        rate_limit_pct = self._rate_limit_to_percent(options.rate_limit, options)
        if limiter_result.limiter_state == GRID_LIMITER_STATE_NORMAL:
            deadband_span = max(options.pv_max - options.pv_min, options.sp_max - options.sp_min)
        else:
            deadband_span = options.grid_max - options.grid_min
        pid_deadband_pct = self._deadband_to_percent(options.pid_deadband, deadband_span)

        error_raw: float | None = None
        if pv_for_pid_raw is not None and sp_for_pid_raw is not None:
            error_raw = sp_for_pid_raw - pv_for_pid_raw
            if options.pid_mode == PID_MODE_REVERSE:
                error_raw = -error_raw

        if not options.enabled:
            self.pid.reset()
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            safe_output = options.min_output
            self._last_output_raw = safe_output
            self._last_output_pct = self._output_percent_from_raw(safe_output, options)
            self._last_pv_pct = None
            self._last_sp_pct = None
            self._manual_out_value = safe_output
            self._previous_runtime_mode = runtime_mode
            self._log_runtime_mode_change(prev_runtime_mode, runtime_mode, setpoint.manual_sp_value, manual_sp_display_value)
            return OutputPlan(
                output=safe_output,
                output_pre_rate_limit=safe_output,
                error=None,
                status="disabled",
                limiter_state=GRID_LIMITER_STATE_NORMAL,
                manual_out_value=self._manual_out_value,
                p_term=None,
                i_term=None,
                d_term=None,
            )

        if runtime_mode == RUNTIME_MODE_HOLD:
            held_output = self._last_output_raw if self._last_output_raw is not None else options.min_output
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._manual_out_value = held_output
            self._last_output_raw = held_output
            self._last_output_pct = self._output_percent_from_raw(held_output, options)
            self._previous_runtime_mode = runtime_mode
            self._log_runtime_mode_change(prev_runtime_mode, runtime_mode, setpoint.manual_sp_value, manual_sp_display_value)
            return OutputPlan(
                output=held_output,
                output_pre_rate_limit=held_output,
                error=None,
                status="hold",
                limiter_state=self._limiter_state,
                manual_out_value=self._manual_out_value,
                p_term=None,
                i_term=None,
                d_term=None,
            )

        if runtime_mode == RUNTIME_MODE_MANUAL_OUT:
            if prev_runtime_mode != RUNTIME_MODE_MANUAL_OUT:
                if self._last_output_raw is not None:
                    self._manual_out_value = self._last_output_raw
                else:
                    self._manual_out_value = _coerce_float(self._manual_out_value, DEFAULT_MANUAL_OUT_VALUE)
            manual_out_value = self._manual_out_value
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._previous_runtime_mode = runtime_mode
            self._log_runtime_mode_change(prev_runtime_mode, runtime_mode, setpoint.manual_sp_value, manual_sp_display_value)
            self._last_output_raw = manual_out_value
            self._last_output_pct = self._output_percent_from_raw(manual_out_value, options)
            return OutputPlan(
                output=manual_out_value,
                output_pre_rate_limit=manual_out_value,
                error=None,
                status="manual_out",
                limiter_state=self._limiter_state,
                manual_out_value=self._manual_out_value,
                p_term=None,
                i_term=None,
                d_term=None,
            )

        if pv_for_pid is None or sp_for_pid is None:
            self.pid.reset()
            self._limiter_state = GRID_LIMITER_STATE_NORMAL
            self._last_output_raw = None
            self._last_output_pct = None
            self._last_pv_pct = None
            self._last_sp_pct = None
            self._previous_runtime_mode = runtime_mode
            self._log_runtime_mode_change(prev_runtime_mode, runtime_mode, setpoint.manual_sp_value, manual_sp_display_value)
            return OutputPlan(
                output=None,
                output_pre_rate_limit=None,
                error=None,
                status="missing_input",
                limiter_state=limiter_result.limiter_state,
                manual_out_value=self._manual_out_value,
                p_term=None,
                i_term=None,
                d_term=None,
            )

        error_pct = sp_for_pid - pv_for_pid
        if options.pid_mode == PID_MODE_REVERSE:
            error_pct = -error_pct

        if (
            limiter_result.limiter_state == GRID_LIMITER_STATE_NORMAL
            and pid_deadband_pct > 0
            and abs(error_pct) < pid_deadband_pct
        ):
            error_pct = 0.0
            if error_raw is not None:
                error_raw = 0.0

        current_output_pct = self._last_output_pct
        bumpless_needed = prev_runtime_mode in (RUNTIME_MODE_MANUAL_OUT, RUNTIME_MODE_HOLD)
        if not bumpless_needed and current_output_pct is not None:
            if limiter_result.limiter_state != prev_limiter_state:
                bumpless_needed = True
            elif prev_sp_for_pid is not None and sp_for_pid is not None and sp_for_pid != prev_sp_for_pid:
                bumpless_needed = True

        if prev_runtime_mode == RUNTIME_MODE_MANUAL_OUT:
            current_output_pct = self._output_percent_from_raw(self._manual_out_value, options)
            self._last_output_pct = current_output_pct
            self._last_output_raw = self._manual_out_value
        elif prev_runtime_mode == RUNTIME_MODE_HOLD:
            current_output_pct = self._last_output_pct

        if bumpless_needed and current_output_pct is not None:
            self.pid.bumpless_transfer(current_output=current_output_pct, error=error_pct, pv=pv_for_pid)

        self._limiter_state = limiter_result.limiter_state

        step_result: PIDStepResult = self.pid.step(
            pv=pv_for_pid,
            error=error_pct,
            last_output=self._last_output_pct,
            rate_limiter_enabled=options.rate_limiter_enabled,
            rate_limit=rate_limit_pct,
        )

        output_raw = self._output_raw_from_percent(step_result.output, options)
        output_pre_rate_raw = self._output_raw_from_percent(step_result.output_pre_rate_limit, options)
        if runtime_mode != RUNTIME_MODE_MANUAL_OUT and output_raw is not None:
            self._manual_out_value = output_raw

        term_factor = output_span / 100.0 if output_span > 0 else None
        p_term_raw = step_result.p_term * term_factor if term_factor is not None else None
        i_term_raw = step_result.i_term * term_factor if term_factor is not None else None
        d_term_raw = step_result.d_term * term_factor if term_factor is not None else None

        self._previous_runtime_mode = runtime_mode
        self._log_runtime_mode_change(prev_runtime_mode, runtime_mode, setpoint.manual_sp_value, manual_sp_display_value)

        self._last_pv_pct = pv_for_pid
        self._last_sp_pct = sp_for_pid
        self._last_output_pct = step_result.output

        return OutputPlan(
            output=output_raw,
            output_pre_rate_limit=output_pre_rate_raw,
            error=error_raw,
            status=status,
            limiter_state=limiter_result.limiter_state,
            manual_out_value=self._manual_out_value,
            p_term=p_term_raw,
            i_term=i_term_raw,
            d_term=d_term_raw,
        )

    async def _async_update_data(self) -> FlowState:
        prev_limiter_state = self._limiter_state
        prev_sp_for_pid = self._last_sp_pct
        prev_pv_for_pid = self._last_pv_pct
        prev_runtime_mode = self._previous_runtime_mode
        prev_manual_sp_value = self._manual_sp_value

        options = self._build_runtime_options()
        inputs = self._read_inputs(options)
        setpoint_context = self._compute_setpoint_context(options, inputs, prev_runtime_mode, prev_manual_sp_value)
        limiter_result = self._apply_grid_limiter(options, inputs, setpoint_context, prev_limiter_state)

        out_ent = _get_entity_id(self.entry, CONF_OUTPUT_ENTITY)
        out_domain = _get_domain(out_ent)
        if out_ent and out_domain not in _OUTPUT_DOMAINS:
            if not self._invalid_output_reported:
                _LOGGER.warning(
                    "Unsupported output entity domain '%s' for %s. Use number.* or input_number.*",
                    out_domain,
                    out_ent,
                )
                self._invalid_output_reported = True
            self._previous_runtime_mode = setpoint_context.runtime_mode
            self._log_runtime_mode_change(prev_runtime_mode, setpoint_context.runtime_mode, prev_manual_sp_value, setpoint_context.manual_sp_display_value)
            return FlowState(
                pv=limiter_result.pv_for_pid,
                sp=limiter_result.sp_for_pid,
                grid_power=inputs.grid_power,
                out=None,
                output_pre_rate_limit=None,
                error=None,
                enabled=options.enabled,
                status="invalid_output",
                limiter_state=self._limiter_state,
                runtime_mode=setpoint_context.runtime_mode,
                manual_sp_value=self._manual_sp_value,
                manual_out_value=self._manual_out_value,
                manual_sp_display_value=setpoint_context.manual_sp_display_value,
                p_term=None,
                i_term=None,
                d_term=None,
            )

        output_plan = self._calculate_output_plan(
            options,
            inputs,
            setpoint_context,
            limiter_result,
            prev_runtime_mode,
            prev_limiter_state,
            prev_sp_for_pid,
            prev_pv_for_pid,
        )

        write_result = await self._maybe_write_output(out_ent, output_plan.output, options)
        final_status = self._apply_output_status(output_plan.status, write_result.write_failed)

        return FlowState(
            pv=limiter_result.pv_for_pid,
            sp=limiter_result.sp_for_pid,
            grid_power=inputs.grid_power,
            out=self._last_output_raw,
            output_pre_rate_limit=output_plan.output_pre_rate_limit,
            error=output_plan.error,
            enabled=options.enabled,
            status=final_status,
            limiter_state=output_plan.limiter_state,
            runtime_mode=setpoint_context.runtime_mode,
            manual_sp_value=self._manual_sp_value,
            manual_out_value=output_plan.manual_out_value,
            manual_sp_display_value=setpoint_context.manual_sp_display_value,
            p_term=output_plan.p_term,
            i_term=output_plan.i_term,
            d_term=output_plan.d_term,
        )

# Manual test checklist:
# 1) change limiter limit while running -> output continues smoothly (no jump to 0)
# 2) change deadband -> no reset
# 3) change kp/ki -> no reset
# 4) start a big load to trigger limiter -> smooth transition; stop load -> smooth return.

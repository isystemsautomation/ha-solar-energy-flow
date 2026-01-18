from __future__ import annotations

from dataclasses import dataclass
import logging
import time


_LOGGER = logging.getLogger(__name__)


@dataclass
class PIDConfig:
    kp: float
    ki: float
    kd: float
    min_output: float
    max_output: float


@dataclass
class PIDStepResult:
    output: float
    error: float
    p_term: float
    i_term: float
    d_term: float
    output_pre_rate_limit: float


class PID:
    """Simple PID with anti-windup via tracking and derivative on measurement.
    
    Features:
    - Conditional integration: integral only accumulates when output is not saturated or rate-limited
    - Anti-windup: prevents integral buildup when output can't respond
    - Derivative on measurement: reduces derivative kick on setpoint changes
    """

    def __init__(self, cfg: PIDConfig, *, entry_id: str | None = None) -> None:
        self.cfg = cfg
        self._integral = 0.0  # Integral term (already multiplied by Ki)
        self._prev_pv: float | None = None
        self._prev_t: float | None = None
        self._prev_error: float | None = None
        self._kaw = self._compute_kaw(cfg.kp)
        if entry_id:
            _LOGGER.debug("PIDController CREATED entry_id=%s", entry_id)

    def update_config(self, cfg: PIDConfig) -> None:
        self.cfg = cfg
        self._kaw = self._compute_kaw(cfg.kp)

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_pv = None
        self._prev_t = None
        self._prev_error = None

    def apply_options(self, cfg: PIDConfig) -> None:
        """Apply new tuning without resetting accumulated state."""

        _LOGGER.debug("PIDController APPLY runtime options; no reset")
        self.update_config(cfg)

    def _compute_kaw(self, kp: float) -> float:
        return 1.0 / max(kp, 0.001)

    def step(
        self,
        pv: float,
        error: float,
        last_output: float | None,
        *,
        rate_limiter_enabled: bool,
        rate_limit: float,
    ) -> PIDStepResult:
        """Return the latest PID step details."""
        now = time.monotonic()
        if self._prev_t is None:
            dt = 0.0
        else:
            dt = max(1e-6, now - self._prev_t)

        # Derivative (on measurement to reduce derivative kick)
        if self._prev_pv is None or dt < 1e-4:
            d_pv = 0.0
        else:
            d_pv = (pv - self._prev_pv) / dt

        p = self.cfg.kp * error
        i = self._integral
        d = -self.cfg.kd * d_pv

        u_pid = p + i + d
        u_sat = max(self.cfg.min_output, min(self.cfg.max_output, u_pid))

        if rate_limiter_enabled and rate_limit > 0 and last_output is not None and dt > 0:
            max_delta = rate_limit * dt
            u_out = max(last_output - max_delta, min(last_output + max_delta, u_sat))
        else:
            u_out = u_sat

        if dt > 0:
            # Conditional integration: only accumulate integral when output is not saturated
            # This prevents integral windup when the output is at its limits
            output_saturated = (u_pid < self.cfg.min_output) or (u_pid > self.cfg.max_output)
            rate_limited = rate_limiter_enabled and rate_limit > 0 and last_output is not None and u_out != u_sat
            
            if not output_saturated and not rate_limited:
                # Output is within limits and not rate-limited: normal integral accumulation with anti-windup
                self._integral += self.cfg.ki * error * dt + self._kaw * (u_out - u_pid) * dt
            else:
                # Output is saturated or rate-limited: only apply anti-windup, don't accumulate error
                # This prevents the integral from growing when the output can't respond
                self._integral += self._kaw * (u_out - u_pid) * dt

        self._prev_pv = pv
        self._prev_t = now
        self._prev_error = error
        return PIDStepResult(
            output=u_out,
            error=error,
            p_term=p,
            i_term=i,
            d_term=d,
            output_pre_rate_limit=u_sat,
        )

    def bumpless_transfer(self, current_output: float, error: float, pv: float | None) -> None:
        """Adjust integral to avoid output jumps when mode/setpoint changes."""

        now = time.monotonic()
        dt = 0.0 if self._prev_t is None else max(1e-6, now - self._prev_t)

        if pv is None or self._prev_pv is None or dt == 0.0:
            d_term = 0.0
        else:
            d_term = -self.cfg.kd * (pv - self._prev_pv) / dt

        if self.cfg.ki != 0:
            self._integral = current_output - self.cfg.kp * error - d_term
        else:
            self._integral = 0.0

        self._prev_pv = pv
        self._prev_t = now
        self._prev_error = error

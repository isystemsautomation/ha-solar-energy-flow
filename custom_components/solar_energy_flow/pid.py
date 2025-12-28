from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class PIDConfig:
    kp: float
    ki: float
    kd: float
    min_output: float
    max_output: float


class PID:
    """Simple PID with anti-windup via integral clamping and derivative on measurement."""

    def __init__(self, cfg: PIDConfig) -> None:
        self.cfg = cfg
        self._integral = 0.0
        self._prev_pv: float | None = None
        self._prev_t: float | None = None

    def update_config(self, cfg: PIDConfig) -> None:
        self.cfg = cfg

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_pv = None
        self._prev_t = None

    def step(self, pv: float, error: float) -> tuple[float, float]:
        """Return (output, error)."""
        now = time.monotonic()
        if self._prev_t is None:
            dt = 0.0
        else:
            dt = max(1e-6, now - self._prev_t)

        # Integral
        if dt > 0:
            self._integral += error * dt

        # Derivative (on measurement to reduce derivative kick)
        if self._prev_pv is None or dt == 0.0:
            d_pv = 0.0
        else:
            d_pv = (pv - self._prev_pv) / dt

        p = self.cfg.kp * error
        i = self.cfg.ki * self._integral
        d = -self.cfg.kd * d_pv

        raw = p + i + d
        out = max(self.cfg.min_output, min(self.cfg.max_output, raw))

        # Anti-windup: clamp integral if saturated and pushing further
        if self.cfg.ki != 0 and dt > 0:
            if out >= self.cfg.max_output and error > 0:
                self._integral -= error * dt
            elif out <= self.cfg.min_output and error < 0:
                self._integral -= error * dt

        self._prev_pv = pv
        self._prev_t = now
        return out, error

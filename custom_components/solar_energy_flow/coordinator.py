from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import entity_registry as er

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


class SolarEnergyFlowCoordinator(DataUpdateCoordinator[FlowState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )

        cfg = PIDConfig(
            kp=entry.options.get(CONF_KP, DEFAULT_KP),
            ki=entry.options.get(CONF_KI, DEFAULT_KI),
            kd=entry.options.get(CONF_KD, DEFAULT_KD),
            min_output=entry.options.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT),
            max_output=entry.options.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT),
        )
        self.pid = PID(cfg)

    def _refresh_pid_config(self) -> None:
        cfg = PIDConfig(
            kp=self.entry.options.get(CONF_KP, DEFAULT_KP),
            ki=self.entry.options.get(CONF_KI, DEFAULT_KI),
            kd=self.entry.options.get(CONF_KD, DEFAULT_KD),
            min_output=self.entry.options.get(CONF_MIN_OUTPUT, DEFAULT_MIN_OUTPUT),
            max_output=self.entry.options.get(CONF_MAX_OUTPUT, DEFAULT_MAX_OUTPUT),
        )
        self.pid.update_config(cfg)

    async def _async_update_data(self) -> FlowState:
        self._refresh_pid_config()

        enabled = self.entry.options.get(CONF_ENABLED, DEFAULT_ENABLED)
        pv_ent = self.entry.data[CONF_PROCESS_VALUE_ENTITY]
        sp_ent = self.entry.data[CONF_SETPOINT_ENTITY]
        out_ent = self.entry.data[CONF_OUTPUT_ENTITY]

        pv = _state_to_float(self.hass.states.get(pv_ent))
        sp = _state_to_float(self.hass.states.get(sp_ent))

        if not enabled:
            self.pid.reset()
            return FlowState(pv=pv, sp=sp, out=None, error=None, enabled=False, status="disabled")

        if pv is None or sp is None:
            self.pid.reset()
            return FlowState(pv=pv, sp=sp, out=None, error=None, enabled=True, status="missing_input")

        out, err = self.pid.step(pv=pv, sp=sp)

        await _set_output(self.hass, out_ent, out)

        return FlowState(pv=pv, sp=sp, out=out, error=err, enabled=True, status="running")

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

ENTRY_DATA_COORDINATOR = "coordinator"
ENTRY_DATA_CONSUMER_RUNTIME = "consumer_runtime"

RUNTIME_FIELD_CMD_W = "cmd_w"
RUNTIME_FIELD_IS_ON = "is_on"
RUNTIME_FIELD_ENABLED = "enabled"
RUNTIME_FIELD_START_TIMER_S = "start_timer_s"
RUNTIME_FIELD_STOP_TIMER_S = "stop_timer_s"
RUNTIME_FIELD_REASON = "reason"
RUNTIME_FIELD_IS_ACTIVE = "is_active"
RUNTIME_FIELD_STEP_CHANGE_REQUEST = "step_change_request"  # "next", "previous", or None


def consumer_runtime_updated_signal(entry_id: str) -> str:
    return f"{DOMAIN}_{entry_id}_consumer_runtime_updated"


def get_entry_data(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry_id, {ENTRY_DATA_CONSUMER_RUNTIME: {}})
    entry_data.setdefault(ENTRY_DATA_CONSUMER_RUNTIME, {})
    return entry_data


def set_entry_coordinator(hass: HomeAssistant, entry_id: str, coordinator: Any) -> dict[str, Any]:
    entry_data = get_entry_data(hass, entry_id)
    entry_data[ENTRY_DATA_COORDINATOR] = coordinator
    return entry_data


def get_entry_coordinator(hass: HomeAssistant, entry_id: str):
    entry_data = get_entry_data(hass, entry_id)
    return entry_data[ENTRY_DATA_COORDINATOR]


def get_consumer_runtime(hass: HomeAssistant, entry_id: str, consumer_id: str) -> dict[str, float]:
    entry_data = get_entry_data(hass, entry_id)
    runtime = entry_data.setdefault(ENTRY_DATA_CONSUMER_RUNTIME, {})
    consumer_state = runtime.setdefault(
        consumer_id,
        {
            RUNTIME_FIELD_CMD_W: 0.0,
            RUNTIME_FIELD_IS_ON: False,
            RUNTIME_FIELD_ENABLED: True,
            RUNTIME_FIELD_START_TIMER_S: 0.0,
            RUNTIME_FIELD_STOP_TIMER_S: 0.0,
            RUNTIME_FIELD_REASON: "",
            RUNTIME_FIELD_IS_ACTIVE: False,
            RUNTIME_FIELD_STEP_CHANGE_REQUEST: None,
        },
    )
    consumer_state.setdefault(RUNTIME_FIELD_CMD_W, 0.0)
    consumer_state.setdefault(RUNTIME_FIELD_IS_ON, False)
    consumer_state.setdefault(RUNTIME_FIELD_ENABLED, True)
    consumer_state.setdefault(RUNTIME_FIELD_START_TIMER_S, 0.0)
    consumer_state.setdefault(RUNTIME_FIELD_STOP_TIMER_S, 0.0)
    consumer_state.setdefault(RUNTIME_FIELD_REASON, "")
    consumer_state.setdefault(RUNTIME_FIELD_IS_ACTIVE, False)
    consumer_state.setdefault(RUNTIME_FIELD_STEP_CHANGE_REQUEST, None)
    return consumer_state


def async_dispatch_consumer_runtime_update(hass: HomeAssistant, entry_id: str, consumer_id: str) -> None:
    async_dispatcher_send(hass, consumer_runtime_updated_signal(entry_id), consumer_id)

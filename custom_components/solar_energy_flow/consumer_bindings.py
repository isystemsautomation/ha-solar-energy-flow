from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONSUMER_CONTROL_MODE_ONOFF,
    CONSUMER_CONTROL_MODE_PRESS,
    CONSUMER_DEFAULT_POWER_SERVICE,
    CONSUMER_DEFAULT_VALUE_FIELD,
    CONSUMER_ENABLE_CONTROL_MODE,
    CONSUMER_ENABLE_TARGET_ENTITY_ID,
    CONSUMER_ID,
    CONSUMER_MIN_RATE_LIMIT_SEC,
    CONSUMER_POWER_DEADBAND_W,
    CONSUMER_POWER_SERVICE,
    CONSUMER_POWER_TARGET_ENTITY_ID,
    CONSUMER_STATE_ENTITY_ID,
    CONSUMER_VALUE_FIELD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_BINDINGS_KEY = f"{DOMAIN}_consumer_bindings"


def _get_entity_domain(entity_id: str | None) -> str | None:
    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


def _state_to_bool(hass: HomeAssistant, entity_id: str | None) -> bool | None:
    if not entity_id:
        return None
    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        return None
    value = state_obj.state
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in ("on", "true", "home", "open", "1", "enabled"):
            return True
        if lowered in ("off", "false", "not_home", "closed", "0", "disabled"):
            return False
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num > 0


def _parse_service(service: str) -> tuple[str, str]:
    if "." in service:
        domain, svc = service.split(".", 1)
        return domain, svc
    return "homeassistant", service


def get_consumer_binding(hass: HomeAssistant, entry_id: str, consumer: dict[str, Any]) -> "ConsumerBinding":
    root = hass.data.setdefault(_BINDINGS_KEY, {})
    entry_bindings = root.setdefault(entry_id, {})
    consumer_id = consumer.get(CONSUMER_ID)
    if consumer_id in entry_bindings:
        entry_bindings[consumer_id].update_consumer(consumer)
        return entry_bindings[consumer_id]

    binding = ConsumerBinding(consumer)
    entry_bindings[consumer_id] = binding
    return binding


def cleanup_consumer_bindings(hass: HomeAssistant, entry_id: str) -> None:
    root = hass.data.get(_BINDINGS_KEY, {})
    root.pop(entry_id, None)
    if not root:
        hass.data.pop(_BINDINGS_KEY, None)


class ConsumerBinding:
    def __init__(self, consumer: dict[str, Any]) -> None:
        self._last_enable_command_at: datetime | None = None
        self._last_power_command_at: datetime | None = None
        self._last_power_value: float | None = None
        self._assumed_enabled: bool | None = None
        self._desired_power: float | None = None
        self.update_consumer(consumer)

    def update_consumer(self, consumer: dict[str, Any]) -> None:
        self.consumer = consumer
        self.enable_control_mode = consumer.get(CONSUMER_ENABLE_CONTROL_MODE, CONSUMER_CONTROL_MODE_ONOFF)
        self.enable_target_entity_id = consumer.get(CONSUMER_ENABLE_TARGET_ENTITY_ID)
        self.state_entity_id = consumer.get(CONSUMER_STATE_ENTITY_ID)
        self.power_target_entity_id = consumer.get(CONSUMER_POWER_TARGET_ENTITY_ID)
        self.power_service = consumer.get(CONSUMER_POWER_SERVICE, CONSUMER_DEFAULT_POWER_SERVICE)
        self.value_field = consumer.get(CONSUMER_VALUE_FIELD, CONSUMER_DEFAULT_VALUE_FIELD)

    def _rate_limited(self, last_time: datetime | None) -> bool:
        if last_time is None:
            return False
        return (datetime.utcnow() - last_time).total_seconds() < CONSUMER_MIN_RATE_LIMIT_SEC

    def _get_actual_enabled(self, hass: HomeAssistant) -> bool | None:
        state_from = self.state_entity_id
        if not state_from and self.enable_control_mode == CONSUMER_CONTROL_MODE_ONOFF:
            state_from = self.enable_target_entity_id
        return _state_to_bool(hass, state_from)

    def get_effective_enabled(self, hass: HomeAssistant) -> bool | None:
        actual = self._get_actual_enabled(hass)
        if actual is not None:
            self._assumed_enabled = actual
            return actual
        return self._assumed_enabled

    async def async_set_enabled(self, hass: HomeAssistant, desired_enabled: bool) -> bool:
        actual_enabled = self.get_effective_enabled(hass)
        if actual_enabled is not None and desired_enabled == actual_enabled:
            return False
        if self._rate_limited(self._last_enable_command_at):
            _LOGGER.debug(
                "Enable command for consumer %s skipped due to rate limit", self.consumer.get(CONSUMER_ID)
            )
            return False
        if not self.enable_target_entity_id:
            _LOGGER.warning("No enable target configured for consumer %s", self.consumer.get(CONSUMER_ID))
            return False

        try:
            if self.enable_control_mode == CONSUMER_CONTROL_MODE_PRESS:
                await hass.services.async_call(
                    "button",
                    "press",
                    {"entity_id": self.enable_target_entity_id},
                    blocking=True,
                )
            else:
                service = "turn_on" if desired_enabled else "turn_off"
                domain = _get_entity_domain(self.enable_target_entity_id) or "homeassistant"
                await hass.services.async_call(
                    domain,
                    service,
                    {"entity_id": self.enable_target_entity_id},
                    blocking=True,
                )
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send enable command for consumer %s (%s): %s",
                self.consumer.get(CONSUMER_ID),
                self.enable_target_entity_id,
                err,
            )
            return False

        self._assumed_enabled = desired_enabled
        self._last_enable_command_at = datetime.utcnow()
        return True

    def set_desired_power(self, value: float) -> None:
        self._desired_power = value

    async def async_push_power(self, hass: HomeAssistant) -> bool:
        if not self.power_target_entity_id:
            return False
        desired = self._desired_power
        if desired is None:
            return False
        enabled_state = self.get_effective_enabled(hass)
        target_power = 0.0 if enabled_state is False else desired

        if self._last_power_value is not None and abs(target_power - self._last_power_value) < CONSUMER_POWER_DEADBAND_W:
            return False
        if self._rate_limited(self._last_power_command_at):
            _LOGGER.debug(
                "Power command for consumer %s skipped due to rate limit", self.consumer.get(CONSUMER_ID)
            )
            return False

        domain, service = _parse_service(self.power_service or CONSUMER_DEFAULT_POWER_SERVICE)
        payload = {self.value_field or CONSUMER_DEFAULT_VALUE_FIELD: target_power, "entity_id": self.power_target_entity_id}
        try:
            await hass.services.async_call(domain, service, payload, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to send power command for consumer %s (%s): %s",
                self.consumer.get(CONSUMER_ID),
                self.power_target_entity_id,
                err,
            )
            return False

        self._last_power_value = target_power
        self._last_power_command_at = datetime.utcnow()
        return True

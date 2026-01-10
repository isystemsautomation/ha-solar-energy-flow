from __future__ import annotations

import math

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CONSUMERS,
    CONF_DIVIDER_ENABLED,
    CONSUMER_DEVICE_SUFFIX,
    CONSUMER_ID,
    CONSUMER_MAX_POWER_W,
    CONSUMER_MIN_POWER_W,
    CONSUMER_NAME,
    CONSUMER_TYPE,
    CONSUMER_TYPE_CONTROLLED,
    CONSUMER_TYPE_BINARY,
    DEFAULT_DIVIDER_ENABLED,
    DIVIDER_DEVICE_SUFFIX,
    DOMAIN,
)
from .helpers import (
    RUNTIME_FIELD_CMD_W,
    RUNTIME_FIELD_IS_ON,
    async_dispatch_consumer_runtime_update,
    consumer_runtime_updated_signal,
    get_consumer_runtime,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    divider_enabled = entry.options.get(CONF_DIVIDER_ENABLED, DEFAULT_DIVIDER_ENABLED)
    consumers = entry.options.get(CONF_CONSUMERS, []) if divider_enabled else []
    entities: list[BinarySensorEntity] = []

    # Only create consumer binary sensors if divider is enabled
    if divider_enabled:
        for consumer in consumers:
            if consumer.get(CONSUMER_TYPE) == CONSUMER_TYPE_CONTROLLED:
                entities.append(ConsumerAtMinBinarySensor(entry, consumer))
                entities.append(ConsumerAtMaxBinarySensor(entry, consumer))
            elif consumer.get(CONSUMER_TYPE) == CONSUMER_TYPE_BINARY:
                entities.append(BinaryConsumerActiveBinarySensor(entry, consumer))

    async_add_entities(entities)

    # Only dispatch consumer runtime updates if divider is enabled
    if divider_enabled:
        for consumer in consumers:
            async_dispatch_consumer_runtime_update(hass, entry.entry_id, consumer[CONSUMER_ID])


class _BaseConsumerRuntimeBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, consumer: dict, name: str, unique_suffix: str) -> None:
        self._entry = entry
        self._consumer = consumer
        self._consumer_id = consumer[CONSUMER_ID]
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self._consumer_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{CONSUMER_DEVICE_SUFFIX}_{self._consumer_id}")},
            via_device=(DOMAIN, f"{entry.entry_id}_{DIVIDER_DEVICE_SUFFIX}"),
            name=consumer.get(CONSUMER_NAME, "Consumer"),
            manufacturer="Solar Energy Flow",
            model="Energy Divider Consumer",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                consumer_runtime_updated_signal(self._entry.entry_id),
                self._handle_runtime_update,
            )
        )
        self.async_write_ha_state()

    @callback
    def _handle_runtime_update(self, consumer_id: str) -> None:
        if consumer_id != self._consumer_id:
            return
        self.async_write_ha_state()

    def _runtime(self) -> dict[str, float]:
        return get_consumer_runtime(self.hass, self._entry.entry_id, self._consumer_id)


class ConsumerAtMinBinarySensor(_BaseConsumerRuntimeBinarySensor):
    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "At min", "at_min")

    @property
    def is_on(self) -> bool:
        runtime = self._runtime()
        cmd_w = round(float(runtime.get(RUNTIME_FIELD_CMD_W, 0.0)), 1)
        min_power = round(float(self._consumer.get(CONSUMER_MIN_POWER_W, 0.0)), 1)
        return math.isclose(cmd_w, min_power) and cmd_w > 0.0


class ConsumerAtMaxBinarySensor(_BaseConsumerRuntimeBinarySensor):
    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "At max", "at_max")

    @property
    def is_on(self) -> bool:
        runtime = self._runtime()
        cmd_w = round(float(runtime.get(RUNTIME_FIELD_CMD_W, 0.0)), 1)
        max_power = round(float(self._consumer.get(CONSUMER_MAX_POWER_W, 0.0)), 1)
        return math.isclose(cmd_w, max_power)


class BinaryConsumerActiveBinarySensor(_BaseConsumerRuntimeBinarySensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, consumer: dict) -> None:
        super().__init__(entry, consumer, "Active", "active")

    @property
    def is_on(self) -> bool:
        runtime = self._runtime()
        return bool(runtime.get(RUNTIME_FIELD_IS_ON, False))

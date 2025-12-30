"""Consumer management module for Solar Energy Flow integration.

This module provides the ConsumerManager class which handles all consumer-related
operations including state management, priority handling, and validation.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping

from homeassistant.core import HomeAssistant

from .const import (
    CONSUMER_ID,
    CONSUMER_NAME,
    CONSUMER_PRIORITY,
    CONSUMER_TYPE,
    CONSUMER_TYPE_BINARY,
    CONSUMER_TYPE_CONTROLLED,
)
from .helpers import (
    RUNTIME_FIELD_ENABLED,
    RUNTIME_FIELD_IS_ACTIVE,
    RUNTIME_FIELD_STEP_CHANGE_REQUEST,
    get_consumer_runtime,
)

_LOGGER = logging.getLogger(__name__)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Coerce a value to float, returning default if conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ConsumerManager:
    """Manages consumer operations including state, priorities, and validation."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the ConsumerManager."""
        self.hass = hass
        self.entry_id = entry_id
        self._cached_enabled_priorities: list[float] | None = None
        self._cached_consumers_hash: int | None = None
        self._cached_consumer_lookups: dict[str, dict[str, Any]] = {}
        self._last_update_time: float = 0.0
        self._update_count: int = 0

    def is_enabled(self, consumer: Mapping[str, Any]) -> bool:
        """Check if consumer is enabled (internal control, not physical device state)."""
        consumer_id = consumer.get(CONSUMER_ID)
        if consumer_id is None:
            return False
        runtime = get_consumer_runtime(self.hass, self.entry_id, consumer_id)
        return bool(runtime.get(RUNTIME_FIELD_ENABLED, True))

    def is_available(self, consumer: Mapping[str, Any]) -> bool:
        """Check if consumer's power target entity is available."""
        from .const import CONSUMER_POWER_TARGET_ENTITY_ID
        
        power_target = consumer.get(CONSUMER_POWER_TARGET_ENTITY_ID)
        if power_target:
            state = self.hass.states.get(power_target)
            if state is None or state.state in ("unavailable", "unknown"):
                return False
        return True

    def get_priority(self, consumer: Mapping[str, Any]) -> float:
        """Get consumer priority, defaulting to 999.0 if not set."""
        return _coerce_float(consumer.get(CONSUMER_PRIORITY), 999.0)

    def get_consumers_hash(self, consumers: list[Mapping[str, Any]]) -> int:
        """Calculate a hash of consumers list to detect changes.
        
        Returns a hash based on consumer IDs, enabled status, and priorities.
        """
        consumer_signatures = []
        for consumer in consumers:
            consumer_id = consumer.get(CONSUMER_ID)
            if consumer_id:
                enabled = self.is_enabled(consumer)
                priority = self.get_priority(consumer)
                consumer_signatures.append((consumer_id, enabled, priority))
        return hash(tuple(sorted(consumer_signatures)))

    def collect_enabled_priorities(
        self, consumers: list[Mapping[str, Any]], use_cache: bool = True
    ) -> list[float]:
        """Collect unique enabled consumer priorities.
        
        Returns a list of unique priority values from enabled consumers.
        Uses tolerance for float comparison to avoid duplicates.
        Optionally caches the result until consumers change.
        
        Args:
            consumers: List of consumer configuration dictionaries
            use_cache: Whether to use cached results if consumers haven't changed
            
        Returns:
            List of unique enabled priority values
        """
        # Check cache
        if use_cache and self._cached_enabled_priorities is not None:
            current_hash = self.get_consumers_hash(consumers)
            if self._cached_consumers_hash == current_hash:
                _LOGGER.debug(
                    f"Using cached enabled priorities: {self._cached_enabled_priorities}"
                )
                return self._cached_enabled_priorities

        # Calculate enabled priorities
        start_time = time.monotonic()
        enabled_priorities = []
        for consumer in consumers:
            if not self.is_enabled(consumer):
                continue
            priority = self.get_priority(consumer)
            if priority > 0:
                # Use tolerance check for float comparison to avoid duplicates
                found = False
                for ep in enabled_priorities:
                    if abs(ep - priority) < 0.01:
                        found = True
                        break
                if not found:
                    enabled_priorities.append(priority)
        
        elapsed = (time.monotonic() - start_time) * 1000  # Convert to ms
        if len(consumers) > 10:
            _LOGGER.debug(
                f"Collected {len(enabled_priorities)} enabled priorities from {len(consumers)} consumers "
                f"in {elapsed:.2f}ms"
            )

        # Update cache
        if use_cache:
            self._cached_enabled_priorities = enabled_priorities
            self._cached_consumers_hash = self.get_consumers_hash(consumers)

        return enabled_priorities

    def invalidate_cache(self) -> None:
        """Invalidate cached consumer data when consumers change."""
        self._cached_enabled_priorities = None
        self._cached_consumers_hash = None
        self._cached_consumer_lookups.clear()

    def validate_consumers(
        self, consumers: list[Mapping[str, Any]]
    ) -> tuple[bool, list[str]]:
        """Validate consumer configurations.
        
        Checks for:
        - Missing required fields
        - Duplicate consumer IDs
        - Invalid priority values
        - Circular dependencies in priorities (if applicable)
        
        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors: list[str] = []
        consumer_ids: set[str] = set()
        priorities: dict[str, float] = {}

        for idx, consumer in enumerate(consumers):
            consumer_id = consumer.get(CONSUMER_ID)
            if not consumer_id:
                errors.append(f"Consumer at index {idx} is missing {CONSUMER_ID}")
                continue

            if consumer_id in consumer_ids:
                errors.append(f"Duplicate consumer ID: {consumer_id}")
                continue
            consumer_ids.add(consumer_id)

            priority = self.get_priority(consumer)
            if priority <= 0:
                errors.append(
                    f"Consumer {consumer_id} has invalid priority: {priority} (must be > 0)"
                )
            priorities[consumer_id] = priority

            consumer_type = consumer.get(CONSUMER_TYPE)
            if consumer_type not in (CONSUMER_TYPE_CONTROLLED, CONSUMER_TYPE_BINARY):
                errors.append(
                    f"Consumer {consumer_id} has invalid type: {consumer_type}"
                )

        is_valid = len(errors) == 0
        if not is_valid:
            _LOGGER.warning(
                f"Consumer validation found {len(errors)} error(s): {errors}"
            )
        else:
            _LOGGER.debug(f"Validated {len(consumers)} consumers successfully")

        return is_valid, errors

    def validate_entity_accessibility(
        self, consumers: list[Mapping[str, Any]]
    ) -> tuple[bool, list[str]]:
        """Validate that consumer entity IDs are accessible.
        
        Checks if entities referenced by consumers exist and are accessible.
        
        Returns:
            Tuple of (all_accessible, list_of_warnings)
        """
        warnings: list[str] = []
        from .const import CONSUMER_POWER_TARGET_ENTITY_ID, CONSUMER_STATE_ENTITY_ID

        for consumer in consumers:
            consumer_id = consumer.get(CONSUMER_ID)
            if not consumer_id:
                continue

            # Check power target entity
            power_target = consumer.get(CONSUMER_POWER_TARGET_ENTITY_ID)
            if power_target:
                state = self.hass.states.get(power_target)
                if state is None:
                    warnings.append(
                        f"Consumer {consumer_id}: Power target entity {power_target} not found"
                    )
                elif state.state in ("unavailable", "unknown"):
                    warnings.append(
                        f"Consumer {consumer_id}: Power target entity {power_target} is {state.state}"
                    )

            # Check state entity
            state_entity = consumer.get(CONSUMER_STATE_ENTITY_ID)
            if state_entity:
                state = self.hass.states.get(state_entity)
                if state is None:
                    warnings.append(
                        f"Consumer {consumer_id}: State entity {state_entity} not found"
                    )

        all_accessible = len(warnings) == 0
        if warnings:
            _LOGGER.warning(
                f"Entity accessibility check found {len(warnings)} warning(s): {warnings[:5]}"
                + (f" (and {len(warnings) - 5} more)" if len(warnings) > 5 else "")
            )
        else:
            _LOGGER.debug(f"All entities accessible for {len(consumers)} consumers")

        return all_accessible, warnings

    def log_performance_metrics(
        self, consumers: list[Mapping[str, Any]], operation: str, duration_ms: float
    ) -> None:
        """Log performance metrics for consumer operations.
        
        Args:
            consumers: List of consumers processed
            operation: Name of the operation (e.g., "update_controlled", "collect_priorities")
            duration_ms: Operation duration in milliseconds
        """
        num_consumers = len(consumers)
        if num_consumers > 10 or duration_ms > 10.0:
            _LOGGER.debug(
                f"Performance: {operation} processed {num_consumers} consumers in {duration_ms:.2f}ms "
                f"(avg: {duration_ms / max(num_consumers, 1):.3f}ms per consumer)"
            )

    def get_consumer_by_id(
        self, consumers: list[Mapping[str, Any]], consumer_id: str
    ) -> Mapping[str, Any] | None:
        """Get consumer configuration by ID with caching.
        
        Args:
            consumers: List of consumer configurations
            consumer_id: ID of consumer to find
            
        Returns:
            Consumer configuration dict or None if not found
        """
        # Check cache first
        if consumer_id in self._cached_consumer_lookups:
            cached = self._cached_consumer_lookups[consumer_id]
            # Verify it's still in the current consumers list
            if cached in consumers:
                return cached

        # Not in cache or cache invalid, find it
        for consumer in consumers:
            if consumer.get(CONSUMER_ID) == consumer_id:
                # Cache it
                self._cached_consumer_lookups[consumer_id] = consumer
                return consumer

        return None


"""Pytest configuration for Solar Energy Controller tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable custom integrations for all tests."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
def mock_hass_frontend():
    """Mock hass_frontend module since it's not available in test environment.
    
    The frontend component requires hass_frontend, which is not available as
    a pip package. We mock it here so frontend can be set up in tests.
    """
    with patch.dict("sys.modules", {"hass_frontend": MagicMock()}):
        yield


"""Fixtures for PurpleAir Local tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from custom_components.purpleair_local.api import PurpleAirReading

pytest_plugins = ("pytest_homeassistant_custom_component",)

FIXTURES = Path(__file__).parent / "fixtures"


def load_payload(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def enable_purpleair_integration(enable_custom_integrations):
    """Allow Home Assistant to load the custom integration under test."""


@pytest.fixture(autouse=True)
def us_customary_units(hass):
    """The legacy entities (and their statistics) are in °F."""
    hass.config.units = US_CUSTOMARY_SYSTEM


@pytest.fixture
def outdoor_payload() -> dict:
    return load_payload("outdoor")


@pytest.fixture
def indoor_payload() -> dict:
    return load_payload("indoor")


@pytest.fixture
def mock_reading(outdoor_payload):
    """Patch the client; tests mutate ``mock.return_value`` or ``side_effect``."""
    with patch(
        "custom_components.purpleair_local.api.PurpleAirLocalClient.async_get_reading",
        new_callable=AsyncMock,
        return_value=PurpleAirReading(outdoor_payload),
    ) as mock:
        yield mock

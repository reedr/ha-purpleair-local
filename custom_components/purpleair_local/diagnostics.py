"""Diagnostics for PurpleAir Local."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import PurpleAirConfigEntry

TO_REDACT = {"lat", "lon", "ssid", "SensorId", "Geo"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PurpleAirConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": {"title": entry.title, "options": dict(entry.options)},
        "last_success": coordinator.last_success,
        "reading": async_redact_data(coordinator.data.raw, TO_REDACT),
    }

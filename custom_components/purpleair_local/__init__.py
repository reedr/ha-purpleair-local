"""PurpleAir Local: read a PurpleAir sensor over the LAN."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PurpleAirLocalClient
from .const import PLATFORMS
from .coordinator import PurpleAirConfigEntry, PurpleAirCoordinator
from .migration import async_adopt_entities


async def async_setup_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    client = PurpleAirLocalClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = PurpleAirCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    if blocked := async_adopt_entities(hass, entry, coordinator.data.mac):
        raise ConfigEntryNotReady(
            f"Waiting to take over {', '.join(blocked)}: remove the REST sensor, "
            "template helper or other integration that still provides them"
        )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


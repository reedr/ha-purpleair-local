"""Taking over entity IDs from REST/template sensors."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.purpleair_local.const import DOMAIN

MAC = "02:00:00:00:ab:c9"


def _entry(hass, adopt) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="RMR Outdoor Air", unique_id=MAC,
        data={"host": "10.0.0.5", "adopt": adopt},
    )
    entry.add_to_hass(hass)
    return entry


async def test_takes_over_orphaned_rest_entities(hass: HomeAssistant, mock_reading, outdoor_payload):
    registry = er.async_get(hass)
    aqi = registry.async_get_or_create("sensor", "rest", "rmr_outdoor_air", suggested_object_id="rmr_outdoor_air")
    registry.async_update_entity(aqi.entity_id, area_id="outside", aliases={"outdoor air"})
    registry.async_get_or_create("sensor", "rest", "rmr_outdoor_air_temp", suggested_object_id="rmr_outdoor_air_temp")

    entry = _entry(hass, {"aqi": "sensor.rmr_outdoor_air", "temperature": "sensor.rmr_outdoor_air_temp",
                          "pm2_5": "sensor.rmr_outdoor_air_pm2_5"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    moved = registry.async_get("sensor.rmr_outdoor_air")
    assert moved.platform == DOMAIN
    assert moved.unique_id == f"{MAC}_aqi"
    assert moved.config_entry_id == entry.entry_id
    assert moved.area_id == "outside"
    assert "outdoor air" in moved.aliases
    assert float(hass.states.get("sensor.rmr_outdoor_air").state) == 0
    assert float(hass.states.get("sensor.rmr_outdoor_air_temp").state) == outdoor_payload["current_temp_f"]
    # freed ID (e.g. a deleted template helper) is claimed exactly
    assert hass.states.get("sensor.rmr_outdoor_air_pm2_5") is not None
    # untouched sensors get normal IDs; the adopt request is consumed
    assert hass.states.get("sensor.rmr_outdoor_air_humidity") is not None
    assert "adopt" not in entry.data


async def test_waits_while_still_provided(hass: HomeAssistant, mock_reading):
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", "rest", "rmr_outdoor_air_temp", suggested_object_id="rmr_outdoor_air_temp")
    # a legacy entity without a registry entry that is still live
    hass.states.async_set("sensor.rmr_outdoor_air", "3")

    entry = _entry(hass, {"aqi": "sensor.rmr_outdoor_air", "temperature": "sensor.rmr_outdoor_air_temp"})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "sensor.rmr_outdoor_air" in entry.reason
    # the unblocked one was taken over; only the blocked one remains queued
    assert registry.async_get("sensor.rmr_outdoor_air_temp").platform == DOMAIN
    assert entry.data["adopt"] == {"aqi": "sensor.rmr_outdoor_air"}

    hass.states.async_remove("sensor.rmr_outdoor_air")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get("sensor.rmr_outdoor_air").platform == DOMAIN


async def test_waits_for_owning_config_entry(hass: HomeAssistant, mock_reading):
    registry = er.async_get(hass)
    helper = MockConfigEntry(domain="template")
    helper.add_to_hass(hass)
    registry.async_get_or_create("sensor", "template", helper.entry_id, config_entry=helper,
                                 suggested_object_id="rmr_outdoor_air_pm2_5")
    entry = _entry(hass, {"pm2_5": "sensor.rmr_outdoor_air_pm2_5"})
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_replaces_own_entity_created_earlier(hass: HomeAssistant, mock_reading):
    """Adopting after the integration already created its own entity."""
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", "rest", "rmr_outdoor_air_temp", suggested_object_id="rmr_outdoor_air_temp")
    entry = _entry(hass, {})
    ours = registry.async_get_or_create("sensor", DOMAIN, f"{MAC}_temperature", config_entry=entry,
                                        suggested_object_id="rmr_outdoor_air_temperature")
    hass.config_entries.async_update_entry(entry, data={**entry.data, "adopt": {"temperature": "sensor.rmr_outdoor_air_temp"}})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(ours.entity_id) is None
    assert registry.async_get("sensor.rmr_outdoor_air_temp").unique_id == f"{MAC}_temperature"

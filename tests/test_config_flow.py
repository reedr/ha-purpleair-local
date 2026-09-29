"""Config, reconfigure and options flows."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.purpleair_local.api import (
    PurpleAirConnectionError,
    PurpleAirReading,
)
from custom_components.purpleair_local.const import DOMAIN


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "10.0.0.5"}
    )


async def test_simple_flow(hass: HomeAssistant, mock_reading):
    result = await _start(hass)
    assert result["step_id"] == "name"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Outdoor Air"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Outdoor Air"
    assert result["data"] == {"host": "10.0.0.5"}
    assert result["result"].unique_id == "02:00:00:00:ab:c9"


async def test_cannot_connect(hass: HomeAssistant, mock_reading):
    mock_reading.side_effect = PurpleAirConnectionError("x")
    result = await _start(hass)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured_updates_host(hass: HomeAssistant, mock_reading):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "10.0.0.9"}, unique_id="02:00:00:00:ab:c9")
    entry.add_to_hass(hass)
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert entry.data["host"] == "10.0.0.5"


async def test_adopt_flow_prefills_existing(hass: HomeAssistant, mock_reading):
    registry = er.async_get(hass)
    for uid in ("rmr_outdoor_air", "rmr_outdoor_air_temp", "rmr_outdoor_air_pm2_5"):
        registry.async_get_or_create("sensor", "rest", uid, suggested_object_id=uid)
    hass.states.async_set("sensor.rmr_outdoor_air_pm10", "1")

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "RMR Outdoor Air", "legacy_prefix": "rmr_outdoor_air"}
    )
    assert result["step_id"] == "adopt"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested == {
        "aqi": "sensor.rmr_outdoor_air",
        "temperature": "sensor.rmr_outdoor_air_temp",
        "pm2_5": "sensor.rmr_outdoor_air_pm2_5",
        "pm10_0": "sensor.rmr_outdoor_air_pm10",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"aqi": "sensor.rmr_outdoor_air", "temperature": "sensor.rmr_outdoor_air_temp", "humidity": ""},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["adopt"] == {
        "aqi": "sensor.rmr_outdoor_air",
        "temperature": "sensor.rmr_outdoor_air_temp",
    }


async def test_adopt_rejects_bad_ids(hass: HomeAssistant, mock_reading):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "X", "legacy_prefix": "light.nope"}
    )
    assert result["errors"] == {"legacy_prefix": "invalid_entity_id"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "X", "legacy_prefix": "sensor.x"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"aqi": "sensor.x", "temperature": "sensor.x"}
    )
    assert result["errors"] == {"aqi": "duplicate_entity_id", "temperature": "duplicate_entity_id"}


async def test_reconfigure(hass: HomeAssistant, mock_reading):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "10.0.0.9"}, unique_id="02:00:00:00:ab:c9")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "10.0.0.5"})
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "10.0.0.5"
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reconfigure_wrong_device(hass: HomeAssistant, mock_reading, indoor_payload):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "10.0.0.9"}, unique_id="02:00:00:00:ab:c9")
    entry.add_to_hass(hass)
    mock_reading.return_value = PurpleAirReading(indoor_payload)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "10.0.0.6"})
    assert result["reason"] == "wrong_device"


async def test_options(hass: HomeAssistant, mock_reading):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "10.0.0.5"}, unique_id="02:00:00:00:ab:c9")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 30})
    assert entry.options == {"scan_interval": 30}

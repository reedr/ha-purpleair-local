"""Entities created from a reading."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.purpleair_local.api import (
    PurpleAirConnectionError,
    PurpleAirReading,
)
from custom_components.purpleair_local.const import DOMAIN


async def _setup(hass: HomeAssistant, title="Outdoor Air") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=title, data={"host": "10.0.0.5"},
                            unique_id="02:00:00:00:ab:c9")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_primary_sensors(hass: HomeAssistant, mock_reading, outdoor_payload):
    await _setup(hass)
    assert float(hass.states.get("sensor.outdoor_air_aqi").state) == 0
    temp = hass.states.get("sensor.outdoor_air_temperature")
    assert float(temp.state) == outdoor_payload["current_temp_f"]
    assert temp.attributes["unit_of_measurement"] == "°F"
    assert float(hass.states.get("sensor.outdoor_air_humidity").state) == outdoor_payload["current_humidity"]
    assert float(hass.states.get("sensor.outdoor_air_dew_point").state) == outdoor_payload["current_dewpoint_f"]
    pressure = hass.states.get("sensor.outdoor_air_pressure")
    assert pressure.attributes["unit_of_measurement"] == "inHg"  # converted for US units
    assert float(pressure.state) == pytest.approx(outdoor_payload["pressure"] * 0.02953, abs=0.01)
    assert float(hass.states.get("sensor.outdoor_air_pm10").state) == outdoor_payload["pm10_0_atm"]
    pm25 = hass.states.get("sensor.outdoor_air_pm2_5")
    assert pm25.attributes["unit_of_measurement"] == "μg/m³"
    # outdoor: EPA corrected values enabled
    assert hass.states.get("sensor.outdoor_air_aqi_epa_corrected") is not None
    assert hass.states.get("binary_sensor.outdoor_air_pm2_5_channel_mismatch").state == "off"
    assert hass.states.get("sensor.outdoor_air_last_restart") is not None


async def test_disabled_by_default(hass: HomeAssistant, mock_reading):
    await _setup(hass)
    registry = er.async_get(hass)
    for entity_id in (
        "sensor.outdoor_air_pm2_5_channel_b",
        "sensor.outdoor_air_gas_resistance",
        "sensor.outdoor_air_signal_strength",
        "sensor.outdoor_air_particles_0_3_microns",
    ):
        entry = registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_indoor_disables_epa(hass: HomeAssistant, mock_reading, indoor_payload):
    mock_reading.return_value = PurpleAirReading(indoor_payload)
    await _setup(hass, "Indoor Air")
    entry = er.async_get(hass).async_get("sensor.indoor_air_aqi_epa_corrected")
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_negative_temperature_and_invalid_pm(hass: HomeAssistant, mock_reading, outdoor_payload):
    outdoor_payload.update({"current_temp_f": -12, "current_dewpoint_f": -30, "pm2_5_atm": -1})
    mock_reading.return_value = PurpleAirReading(outdoor_payload)
    await _setup(hass)
    assert float(hass.states.get("sensor.outdoor_air_temperature").state) == -12
    assert float(hass.states.get("sensor.outdoor_air_dew_point").state) == -30
    assert hass.states.get("sensor.outdoor_air_pm2_5").state == "unknown"


async def test_single_channel_sensor(hass: HomeAssistant, mock_reading, outdoor_payload):
    single = {k: v for k, v in outdoor_payload.items() if not k.endswith("_b")}
    mock_reading.return_value = PurpleAirReading(single)
    await _setup(hass)
    assert hass.states.get("sensor.outdoor_air_aqi") is not None
    assert er.async_get(hass).async_get("sensor.outdoor_air_pm2_5_channel_b") is None
    assert hass.states.get("binary_sensor.outdoor_air_pm2_5_channel_mismatch") is None


async def test_channel_mismatch(hass: HomeAssistant, mock_reading, outdoor_payload):
    outdoor_payload.update({"pm2_5_atm": 40.0, "pm2_5_atm_b": 2.0, "pm2_5_cf_1": 40.0, "pm2_5_cf_1_b": 2.0})
    mock_reading.return_value = PurpleAirReading(outdoor_payload)
    await _setup(hass)
    assert hass.states.get("binary_sensor.outdoor_air_pm2_5_channel_mismatch").state == "on"
    # EPA values are withheld when the channels can't be trusted
    assert hass.states.get("sensor.outdoor_air_pm2_5_epa_corrected").state == "unknown"


async def test_rides_out_short_outage(hass: HomeAssistant, mock_reading, freezer: FrozenDateTimeFactory):
    await _setup(hass)
    mock_reading.side_effect = PurpleAirConnectionError("down")
    for _ in range(3):
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert float(hass.states.get("sensor.outdoor_air_aqi").state) == 0
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.outdoor_air_aqi").state == STATE_UNAVAILABLE


async def test_restart_time_is_stable(hass: HomeAssistant, mock_reading, outdoor_payload, freezer):
    await _setup(hass)
    first = hass.states.get("sensor.outdoor_air_last_restart").state
    outdoor_payload.update({"DateTime": "2026/09/29T15:18:56z", "uptime": outdoor_payload["uptime"] + 120})
    mock_reading.return_value = PurpleAirReading(outdoor_payload)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.outdoor_air_last_restart").state == first

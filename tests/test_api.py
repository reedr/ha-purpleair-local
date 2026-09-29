"""Local JSON client."""

import pytest

from custom_components.purpleair_local.api import (
    PurpleAirConnectionError,
    PurpleAirLocalClient,
    PurpleAirReading,
    PurpleAirResponseError,
    parse_reading,
)


async def test_get_reading(aioclient_mock, outdoor_payload, hass):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get("http://10.0.0.5/json", json=outdoor_payload)
    reading = await PurpleAirLocalClient(async_get_clientsession(hass), "10.0.0.5").async_get_reading()
    assert reading.mac == "02:00:00:00:ab:c9"
    assert reading.place == "outside"
    assert reading.has_channel_b


async def test_connection_error(aioclient_mock, hass):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get("http://10.0.0.5/json", exc=TimeoutError)
    with pytest.raises(PurpleAirConnectionError):
        await PurpleAirLocalClient(async_get_clientsession(hass), "10.0.0.5").async_get_reading()


async def test_invalid_json(aioclient_mock, hass):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get("http://10.0.0.5/json", text="<html>")
    with pytest.raises(PurpleAirResponseError):
        await PurpleAirLocalClient(async_get_clientsession(hass), "10.0.0.5").async_get_reading()


def test_parse_requires_sensor_id():
    with pytest.raises(PurpleAirResponseError):
        parse_reading({"pm2.5_aqi": 3})


def test_number_handling():
    reading = PurpleAirReading(
        {"SensorId": "x", "a": -1, "b": "7", "c": True, "d": float("nan"), "e": -4}
    )
    assert reading.non_negative("a") is None
    assert reading.number("b") is None
    assert reading.number("c") is None
    assert reading.number("d") is None
    assert reading.number("e") == -4
    assert reading.number("missing") is None

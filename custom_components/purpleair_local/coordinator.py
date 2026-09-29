"""Polling coordinator for one PurpleAir sensor."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PurpleAirError, PurpleAirLocalClient, PurpleAirReading
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, STALE_DATA_GRACE

_LOGGER = logging.getLogger(__name__)

type PurpleAirConfigEntry = ConfigEntry[PurpleAirCoordinator]


class PurpleAirCoordinator(DataUpdateCoordinator[PurpleAirReading]):
    """Polls /json; rides out short outages on the last good reading."""

    config_entry: PurpleAirConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PurpleAirConfigEntry,
        client: PurpleAirLocalClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.last_success: datetime | None = None

    async def _async_update_data(self) -> PurpleAirReading:
        try:
            reading = await self.client.async_get_reading()
        except PurpleAirError as err:
            if (
                self.data is not None
                and self.last_success is not None
                and dt_util.utcnow() - self.last_success < STALE_DATA_GRACE
            ):
                _LOGGER.debug("Keeping last reading from %s: %s", self.client.host, err)
                return self.data
            raise UpdateFailed(str(err)) from err
        self.last_success = dt_util.utcnow()
        return reading

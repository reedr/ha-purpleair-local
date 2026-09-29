"""Client for the PurpleAir sensor's local JSON endpoint."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT


class PurpleAirError(Exception):
    """Base error for PurpleAir Local."""


class PurpleAirConnectionError(PurpleAirError):
    """The sensor could not be reached."""


class PurpleAirResponseError(PurpleAirError):
    """The sensor returned something other than its JSON document."""


@dataclass(frozen=True)
class PurpleAirReading:
    """One /json document from a sensor."""

    raw: dict[str, Any]

    @property
    def mac(self) -> str:
        return str(self.raw["SensorId"]).lower()

    @property
    def geo(self) -> str | None:
        return self.raw.get("Geo")

    @property
    def place(self) -> str | None:
        return self.raw.get("place")

    @property
    def firmware(self) -> str | None:
        return self.raw.get("version")

    @property
    def hardware(self) -> str | None:
        # e.g. "3.0+OPENLOG+NO-DISK+RV3028+BME68X+PMSX003-A+PMSX003-B"
        return self.raw.get("hardwarediscovered") or self.raw.get("hardwareversion")

    @property
    def has_channel_b(self) -> bool:
        return "pm2_5_atm_b" in self.raw

    def number(self, key: str) -> float | None:
        """Return a numeric field, or None when missing or not a finite number."""
        value = self.raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
        return float(value)

    def non_negative(self, key: str) -> float | None:
        """Return a field that can't be negative; the firmware uses -1 for 'no data'."""
        value = self.number(key)
        return value if value is not None and value >= 0 else None


def parse_reading(payload: Any) -> PurpleAirReading:
    """Validate a decoded /json payload."""
    if not isinstance(payload, dict) or not payload.get("SensorId"):
        raise PurpleAirResponseError("response has no SensorId")
    return PurpleAirReading(payload)


class PurpleAirLocalClient:
    """Fetches readings from http://<host>/json."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self.host = host

    @property
    def url(self) -> str:
        return f"http://{self.host}/json"

    async def async_get_reading(self) -> PurpleAirReading:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(self.url) as resp:
                    resp.raise_for_status()
                    # note: tolerate firmware that mislabels the content type
                    payload = await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise PurpleAirConnectionError(f"{self.url}: {err!r}") from err
        except ValueError as err:
            raise PurpleAirResponseError(f"{self.url}: invalid JSON") from err
        return parse_reading(payload)

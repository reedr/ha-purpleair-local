"""Constants for PurpleAir Local."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "purpleair_local"
MANUFACTURER = "PurpleAir"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_ADOPT = "adopt"
CONF_LEGACY_PREFIX = "legacy_prefix"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

REQUEST_TIMEOUT = 15

# note: the sensors run on an ESP8266 and drop the odd request; keep serving
#       the last reading this long before the entities go unavailable.
STALE_DATA_GRACE = timedelta(minutes=5)

# Legacy-entity adoption: sensor key -> suffix appended to the legacy prefix
# (matches the common REST/template setup: sensor.x, sensor.x_temp, ...).
ADOPTABLE_SUFFIXES: dict[str, str] = {
    "aqi": "",
    "temperature": "_temp",
    "humidity": "_humidity",
    "dew_point": "_dewpoint",
    "pressure": "_pressure",
    "pm1_0": "_pm1_0",
    "pm2_5": "_pm2_5",
    "pm10_0": "_pm10",
}

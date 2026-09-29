# PurpleAir Local

A Home Assistant integration that reads a PurpleAir sensor directly over your LAN
(`http://<sensor>/json`). No PurpleAir API key or cloud access is needed.

## Entities

| Entity | Source field | Default |
|---|---|---|
| AQI | `pm2.5_aqi` (the sensor's own calculation) | enabled |
| PM1.0 / PM2.5 / PM10 | `pm*_atm`, channel A | enabled |
| Temperature, humidity, dew point, pressure | BME68x | enabled |
| PM2.5 and AQI (EPA corrected) | EPA 2021 US-wide correction on CF=1 PM2.5 (A/B average) with the sensor's humidity; AQI uses the 2024 breakpoints | enabled for outdoor sensors |
| PM2.5 channel mismatch (problem) | A and B differ by ≥5 µg/m³ and ≥70 % | enabled |
| Last restart | `DateTime` − `uptime` | enabled (diagnostic) |
| Channel B AQI/PM, particle counts, gas resistance, Wi-Fi signal | | disabled |

Entities are only created for fields the sensor actually reports, so single-laser
models get no channel-B entities.

The EPA-corrected values are withheld while the two lasers disagree. PurpleAir's
temperature reads a few degrees high because it's measured inside the housing.
It's reported as-is.

If one poll fails, the entities keep their last reading for up to 5 minutes before
going unavailable (the sensors' ESP8266 drops the occasional request).

## Install

Add this repository to HACS as a custom repository (category: Integration), install
**PurpleAir Local**, restart, then go to **Settings → Devices & services → Add
integration → PurpleAir Local** and enter the sensor's IP address.

## Migrating from REST or template sensors without losing history

Recorder history and long-term statistics are stored by entity ID. The integration
can take over your existing entity IDs, so charts and statistics continue unbroken.
It keeps each entity's area, labels, aliases and voice-assistant exposure.

1. Add the integration. In the second step, enter your existing AQI entity ID
   (e.g. `sensor.outdoor_air`). The next step matches the other sensors by suffix
   (`_temp`, `_humidity`, `_dewpoint`, `_pressure`, `_pm1_0`, `_pm2_5`, `_pm10`).
   Edit or clear any match.
2. Setup then waits (it shows *Waiting to take over …*) until nothing else
   provides those entity IDs. Remove the `rest:` sensors from YAML and reload
   **RESTful** from Developer tools → YAML. Delete any template helpers that
   used those IDs.
3. The entry retries on its own, or you can reload it. Each listed entity moves to
   the new device with its history.

Attributes the old REST sensor carried (e.g. `current_temp_f` on the AQI entity) are
not reproduced. Point templates at the new entities instead.

## Options

**Polling interval** (default 60 s). The sensor reports 2-minute averages.

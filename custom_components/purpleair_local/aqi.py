"""US EPA PurpleAir correction and PM2.5 AQI."""

from __future__ import annotations

import math

# PM2.5 breakpoints (µg/m³) and index ranges, EPA 2024 revision.
_PM25_BREAKPOINTS: tuple[tuple[float, float, int, int], ...] = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
)


def epa_corrected_pm25(pm25_cf1: float, humidity: float) -> float:
    """Apply the EPA's 2021 US-wide PurpleAir correction (smoke-extended).

    ``pm25_cf1`` is the CF=1 PM2.5 (average of channels A and B when both are
    healthy); ``humidity`` is the sensor's own relative humidity reading.
    """
    pa, rh = pm25_cf1, humidity
    if pa < 30:
        value = 0.524 * pa - 0.0862 * rh + 5.75
    elif pa < 50:
        w = pa / 20 - 3 / 2
        value = (0.786 * w + 0.524 * (1 - w)) * pa - 0.0862 * rh + 5.75
    elif pa < 210:
        value = 0.786 * pa - 0.0862 * rh + 5.75
    elif pa < 260:
        w = pa / 50 - 21 / 5
        value = (
            (0.69 * w + 0.786 * (1 - w)) * pa
            - 0.0862 * rh * (1 - w)
            + 2.966 * w
            + 5.75 * (1 - w)
            + 8.84e-4 * pa**2 * w
        )
    else:
        value = 2.966 + 0.69 * pa + 8.84e-4 * pa**2
    return max(0.0, value)


def pm25_aqi(pm25: float) -> int:
    """Return the US AQI for a PM2.5 concentration (capped at 500)."""
    # note: EPA truncates the concentration to one decimal before lookup
    c = math.floor(max(0.0, pm25) * 10) / 10
    for c_lo, c_hi, i_lo, i_hi in _PM25_BREAKPOINTS:
        if c <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo)
    return 500


def channels_disagree(a: float, b: float) -> bool:
    """PurpleAir's A/B confidence test: channels differ by ≥5 µg/m³ and ≥70 %."""
    diff = abs(a - b)
    mean = (a + b) / 2
    return diff >= 5 and mean > 0 and diff / mean >= 0.7

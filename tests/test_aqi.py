"""EPA correction and AQI math."""

import pytest

from custom_components.purpleair_local.aqi import (
    channels_disagree,
    epa_corrected_pm25,
    pm25_aqi,
)


@pytest.mark.parametrize(
    ("pm25", "aqi"),
    [
        (0.0, 0),
        (9.0, 50),
        (9.05, 50),  # truncated to 9.0
        (9.1, 51),
        (35.4, 100),
        (35.5, 101),
        (55.4, 150),
        (55.5, 151),
        (125.4, 200),
        (225.4, 300),
        (225.5, 301),
        (325.4, 500),
        (600.0, 500),
        (-3.0, 0),
    ],
)
def test_pm25_aqi(pm25, aqi):
    assert pm25_aqi(pm25) == aqi


def test_epa_correction_low_range():
    assert epa_corrected_pm25(20, 40) == pytest.approx(0.524 * 20 - 0.0862 * 40 + 5.75)


def test_epa_correction_is_continuous_across_breakpoints():
    for pa in (30, 50, 210, 260):
        below = epa_corrected_pm25(pa - 1e-6, 30)
        above = epa_corrected_pm25(pa, 30)
        assert below == pytest.approx(above, abs=1e-3), pa


def test_epa_correction_clamps_at_zero():
    assert epa_corrected_pm25(0, 90) == 0


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(0, 0, False), (1, 4, False), (10, 15, False), (10, 30, True), (2, 20, True), (100, 104, False)],
)
def test_channels_disagree(a, b, expected):
    assert channels_disagree(a, b) is expected

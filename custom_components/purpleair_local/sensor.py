"""Sensors for PurpleAir Local."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDensity,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import PurpleAirReading
from .aqi import channels_disagree, epa_corrected_pm25, pm25_aqi
from .coordinator import PurpleAirConfigEntry, PurpleAirCoordinator
from .entity import PurpleAirEntity

PARALLEL_UPDATES = 0

# note: a restart time that moves by less than this is clock jitter, not a reboot
_RESTART_JITTER = timedelta(minutes=5)


@dataclass(frozen=True, kw_only=True)
class PurpleAirSensorDescription(SensorEntityDescription):
    """Describes a PurpleAir sensor."""

    value_fn: Callable[[PurpleAirReading], float | datetime | None]
    exists_fn: Callable[[PurpleAirReading], bool] = lambda _: True
    enabled_fn: Callable[[PurpleAirReading], bool] | None = None


def _epa_pm25(reading: PurpleAirReading) -> float | None:
    """EPA-corrected PM2.5, or None when inputs are missing or channels disagree."""
    humidity = reading.non_negative("current_humidity")
    a = reading.non_negative("pm2_5_cf_1")
    if humidity is None or a is None:
        return None
    if reading.has_channel_b:
        b = reading.non_negative("pm2_5_cf_1_b")
        if b is None or channels_disagree(a, b):
            return None
        a = (a + b) / 2
    return round(epa_corrected_pm25(a, humidity), 1)


def _epa_aqi(reading: PurpleAirReading) -> float | None:
    pm25 = _epa_pm25(reading)
    return None if pm25 is None else pm25_aqi(pm25)


def _last_restart(reading: PurpleAirReading) -> datetime | None:
    uptime = reading.number("uptime")
    clock = dt_util.parse_datetime(
        str(reading.raw.get("DateTime", "")).replace("/", "-").replace("z", "Z")
    )
    if uptime is None or clock is None:
        return None
    return (clock - timedelta(seconds=uptime)).replace(microsecond=0)


def _field(key: str, *, signed: bool = False) -> Callable[[PurpleAirReading], float | None]:
    if signed:
        return lambda reading: reading.number(key)
    return lambda reading: reading.non_negative(key)


def _has(key: str) -> Callable[[PurpleAirReading], bool]:
    return lambda reading: key in reading.raw


def _pm(key: str, field: str, **kwargs) -> PurpleAirSensorDescription:
    return PurpleAirSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_field(field),
        exists_fn=_has(field),
        **kwargs,
    )


def _count(key: str, field: str) -> PurpleAirSensorDescription:
    return PurpleAirSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=_field(field),
        exists_fn=_has(field),
    )


SENSORS: tuple[PurpleAirSensorDescription, ...] = (
    PurpleAirSensorDescription(
        key="aqi",
        translation_key="aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_field("pm2.5_aqi"),
        exists_fn=_has("pm2.5_aqi"),
    ),
    PurpleAirSensorDescription(
        key="aqi_epa",
        translation_key="aqi_epa",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_epa_aqi,
        exists_fn=_has("pm2_5_cf_1"),
        # note: the EPA correction was fitted to outdoor sensors
        enabled_fn=lambda reading: reading.place != "inside",
    ),
    _pm("pm1_0", "pm1_0_atm", device_class=SensorDeviceClass.PM1),
    _pm("pm2_5", "pm2_5_atm", device_class=SensorDeviceClass.PM25),
    _pm("pm10_0", "pm10_0_atm", device_class=SensorDeviceClass.PM10),
    PurpleAirSensorDescription(
        key="pm2_5_epa",
        translation_key="pm2_5_epa",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_epa_pm25,
        exists_fn=_has("pm2_5_cf_1"),
        enabled_fn=lambda reading: reading.place != "inside",
    ),
    PurpleAirSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_field("current_temp_f", signed=True),
        exists_fn=_has("current_temp_f"),
    ),
    PurpleAirSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_field("current_humidity"),
        exists_fn=_has("current_humidity"),
    ),
    PurpleAirSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_field("current_dewpoint_f", signed=True),
        exists_fn=_has("current_dewpoint_f"),
    ),
    PurpleAirSensorDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_field("pressure"),
        exists_fn=_has("pressure"),
    ),
    PurpleAirSensorDescription(
        key="gas_resistance",
        translation_key="gas_resistance",
        native_unit_of_measurement="kΩ",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_field("gas_680"),
        exists_fn=_has("gas_680"),
    ),
    PurpleAirSensorDescription(
        key="aqi_b",
        translation_key="aqi_b",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=_field("pm2.5_aqi_b"),
        exists_fn=_has("pm2.5_aqi_b"),
    ),
    _pm("pm1_0_b", "pm1_0_atm_b", device_class=SensorDeviceClass.PM1,
        entity_registry_enabled_default=False),
    _pm("pm2_5_b", "pm2_5_atm_b", device_class=SensorDeviceClass.PM25,
        entity_registry_enabled_default=False),
    _pm("pm10_0_b", "pm10_0_atm_b", device_class=SensorDeviceClass.PM10,
        entity_registry_enabled_default=False),
    _count("particles_0_3", "p_0_3_um"),
    _count("particles_0_5", "p_0_5_um"),
    _count("particles_1_0", "p_1_0_um"),
    _count("particles_2_5", "p_2_5_um"),
    _count("particles_5_0", "p_5_0_um"),
    _count("particles_10_0", "p_10_0_um"),
    PurpleAirSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_field("rssi", signed=True),
        exists_fn=_has("rssi"),
    ),
    PurpleAirSensorDescription(
        key="last_restart",
        translation_key="last_restart",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_restart,
        exists_fn=_has("uptime"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PurpleAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    reading = coordinator.data
    async_add_entities(
        (PurpleAirRestartSensor if description.key == "last_restart" else PurpleAirSensor)(
            coordinator, description
        )
        for description in SENSORS
        if description.exists_fn(reading)
    )


class PurpleAirSensor(PurpleAirEntity, SensorEntity):
    """A value from the sensor's /json document."""

    entity_description: PurpleAirSensorDescription

    def __init__(
        self, coordinator: PurpleAirCoordinator, description: PurpleAirSensorDescription
    ) -> None:
        super().__init__(coordinator, description)
        if description.enabled_fn is not None:
            self._attr_entity_registry_enabled_default = description.enabled_fn(
                coordinator.data
            )

    @property
    def native_value(self) -> float | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)


class PurpleAirRestartSensor(PurpleAirSensor):
    """Restart time derived from uptime; holds steady against clock jitter."""

    _restart: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        value = super().native_value
        if value is not None and (
            self._restart is None or abs(value - self._restart) >= _RESTART_JITTER
        ):
            self._restart = value
        return self._restart

"""Binary sensors for PurpleAir Local."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .aqi import channels_disagree
from .coordinator import PurpleAirConfigEntry
from .entity import PurpleAirEntity

PARALLEL_UPDATES = 0

CHANNEL_MISMATCH = BinarySensorEntityDescription(
    key="channel_mismatch",
    translation_key="channel_mismatch",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PurpleAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.data.has_channel_b:
        async_add_entities([PurpleAirChannelMismatch(coordinator, CHANNEL_MISMATCH)])


class PurpleAirChannelMismatch(PurpleAirEntity, BinarySensorEntity):
    """On when the two laser counters disagree (a failing or fouled counter)."""

    @property
    def is_on(self) -> bool | None:
        reading = self.coordinator.data
        a = reading.non_negative("pm2_5_atm")
        b = reading.non_negative("pm2_5_atm_b")
        if a is None or b is None:
            return None
        return channels_disagree(a, b)

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        reading = self.coordinator.data
        return {
            "pm2_5_a": reading.non_negative("pm2_5_atm"),
            "pm2_5_b": reading.non_negative("pm2_5_atm_b"),
        }

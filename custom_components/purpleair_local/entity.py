"""Base entity for PurpleAir Local."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PurpleAirCoordinator


def entity_unique_id(mac: str, key: str) -> str:
    return f"{mac}_{key}"


class PurpleAirEntity(CoordinatorEntity[PurpleAirCoordinator]):
    """An entity backed by one sensor's readings."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PurpleAirCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        reading = coordinator.data
        self._attr_unique_id = entity_unique_id(reading.mac, description.key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, reading.mac)},
            connections={(CONNECTION_NETWORK_MAC, reading.mac)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model="Air quality sensor",
            hw_version=reading.hardware,
            sw_version=reading.firmware,
            configuration_url=f"http://{coordinator.client.host}",
        )

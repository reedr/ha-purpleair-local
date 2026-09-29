"""Config flow for PurpleAir Local."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback, valid_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .api import (
    PurpleAirConnectionError,
    PurpleAirLocalClient,
    PurpleAirReading,
    PurpleAirResponseError,
)
from .const import (
    ADOPTABLE_SUFFIXES,
    CONF_ADOPT,
    CONF_LEGACY_PREFIX,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import PurpleAirConfigEntry
from .sensor import SENSORS


class PurpleAirLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a PurpleAir sensor by host."""

    VERSION = 1

    def __init__(self) -> None:
        self._host = ""
        self._name = ""
        self._reading: PurpleAirReading | None = None
        self._prefix = ""

    async def _async_fetch(self, host: str) -> tuple[PurpleAirReading | None, str | None]:
        client = PurpleAirLocalClient(async_get_clientsession(self.hass), host)
        try:
            return await client.async_get_reading(), None
        except PurpleAirConnectionError:
            return None, "cannot_connect"
        except PurpleAirResponseError:
            return None, "invalid_response"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            reading, error = await self._async_fetch(host)
            if reading is None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(format_mac(reading.mac))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                self._host, self._reading = host, reading
                return await self.async_step_name()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str}), user_input
            ),
            errors=errors,
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._reading is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip()
            prefix = (user_input.get(CONF_LEGACY_PREFIX) or "").strip()
            if prefix and "." not in prefix:
                prefix = f"sensor.{prefix}"
            if prefix and not (prefix.startswith("sensor.") and valid_entity_id(prefix)):
                errors[CONF_LEGACY_PREFIX] = "invalid_entity_id"
            elif prefix:
                self._prefix = prefix
                return await self.async_step_adopt()
            else:
                return self._async_create()
        return self.async_show_form(
            step_id="name",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): str,
                        vol.Optional(CONF_LEGACY_PREFIX): TextSelector(),
                    }
                ),
                user_input or {CONF_NAME: self._reading.geo or "PurpleAir"},
            ),
            description_placeholders={"place": self._reading.place or "unknown"},
            errors=errors,
        )

    def _adoptable_keys(self) -> list[str]:
        assert self._reading is not None
        present = {d.key for d in SENSORS if d.exists_fn(self._reading)}
        return [key for key in ADOPTABLE_SUFFIXES if key in present]

    async def async_step_adopt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        keys = self._adoptable_keys()
        errors: dict[str, str] = {}
        if user_input is not None:
            adopt = {k: v.strip() for k, v in user_input.items() if k in keys and v and v.strip()}
            for key, entity_id in adopt.items():
                if not (entity_id.startswith("sensor.") and valid_entity_id(entity_id)):
                    errors[key] = "invalid_entity_id"
                elif list(adopt.values()).count(entity_id) > 1:
                    errors[key] = "duplicate_entity_id"
            if not errors:
                return self._async_create(adopt)

        registry = er.async_get(self.hass)
        suggestions = user_input or {
            key: f"{self._prefix}{ADOPTABLE_SUFFIXES[key]}"
            for key in keys
            if registry.async_get(f"{self._prefix}{ADOPTABLE_SUFFIXES[key]}")
            or self.hass.states.get(f"{self._prefix}{ADOPTABLE_SUFFIXES[key]}")
        }
        return self.async_show_form(
            step_id="adopt",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Optional(key): TextSelector() for key in keys}),
                suggestions,
            ),
            errors=errors,
        )

    @callback
    def _async_create(self, adopt: dict[str, str] | None = None) -> ConfigFlowResult:
        data: dict[str, Any] = {CONF_HOST: self._host}
        if adopt:
            data[CONF_ADOPT] = adopt
        return self.async_create_entry(title=self._name, data=data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            reading, error = await self._async_fetch(host)
            if reading is None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(format_mac(reading.mac))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str}),
                user_input or {CONF_HOST: entry.data[CONF_HOST]},
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: PurpleAirConfigEntry) -> PurpleAirOptionsFlow:
        return PurpleAirOptionsFlow()


class PurpleAirOptionsFlow(OptionsFlowWithReload):
    """Polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_SCAN_INTERVAL): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_SCAN_INTERVAL,
                                max=MAX_SCAN_INTERVAL,
                                step=1,
                                unit_of_measurement="s",
                                mode=NumberSelectorMode.BOX,
                            )
                        )
                    }
                ),
                {
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    )
                },
            ),
        )

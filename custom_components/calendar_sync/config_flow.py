"""Config-Flow – fragt iCloud-Zugangsdaten ab. Google kommt später."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_GOOGLE_CALENDAR_ID,
    CONF_ICLOUD_CALENDAR,
    CONF_ICLOUD_PASSWORD,
    CONF_ICLOUD_USERNAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .icloud_client import ICloudClient


class CalendarSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    _probe_icloud,
                    user_input[CONF_ICLOUD_USERNAME],
                    user_input[CONF_ICLOUD_PASSWORD],
                    user_input[CONF_ICLOUD_CALENDAR],
                )
            except Exception:  # noqa: BLE001
                errors["base"] = "icloud_auth"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_ICLOUD_USERNAME]}::"
                    f"{user_input[CONF_ICLOUD_CALENDAR]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"iCloud: {user_input[CONF_ICLOUD_CALENDAR]}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ICLOUD_USERNAME): str,
                vol.Required(CONF_ICLOUD_PASSWORD): str,
                vol.Required(CONF_ICLOUD_CALENDAR): str,
                vol.Optional(CONF_GOOGLE_CALENDAR_ID, default="primary"): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): int,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


def _probe_icloud(user: str, pw: str, cal: str) -> None:
    client = ICloudClient(user, pw, cal)
    names = client.list_calendars()
    if cal not in names:
        raise RuntimeError(f"Kalender '{cal}' nicht gefunden. Vorhanden: {names}")

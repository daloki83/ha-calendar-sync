"""Config-Flow – zweistufig: zuerst iCloud-Login, dann Kalenderauswahl."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._calendars: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Schritt 1: Zugangsdaten erfassen und Kalender holen."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                calendars = await self.hass.async_add_executor_job(
                    _list_calendars,
                    user_input[CONF_ICLOUD_USERNAME],
                    user_input[CONF_ICLOUD_PASSWORD],
                )
            except Exception:  # noqa: BLE001
                errors["base"] = "icloud_auth"
            else:
                if not calendars:
                    errors["base"] = "no_calendars"
                else:
                    self._username = user_input[CONF_ICLOUD_USERNAME]
                    self._password = user_input[CONF_ICLOUD_PASSWORD]
                    self._calendars = calendars
                    return await self.async_step_pick()

        schema = vol.Schema(
            {
                vol.Required(CONF_ICLOUD_USERNAME): str,
                vol.Required(CONF_ICLOUD_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Schritt 2: Kalender aus Dropdown wählen + Optionen."""
        assert self._username and self._password
        if user_input is not None:
            await self.async_set_unique_id(
                f"{self._username}::{user_input[CONF_ICLOUD_CALENDAR]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"iCloud: {user_input[CONF_ICLOUD_CALENDAR]}",
                data={
                    CONF_ICLOUD_USERNAME: self._username,
                    CONF_ICLOUD_PASSWORD: self._password,
                    **user_input,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_ICLOUD_CALENDAR): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._calendars,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_GOOGLE_CALENDAR_ID, default="primary"): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): int,
            }
        )
        return self.async_show_form(step_id="pick", data_schema=schema)


def _list_calendars(user: str, pw: str) -> list[str]:
    client = ICloudClient(user, pw, "")
    return client.list_calendars()

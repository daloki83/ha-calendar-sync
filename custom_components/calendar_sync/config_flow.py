"""Config-Flow – Google OAuth → iCloud-Login → Kalender wählen."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow, selector

from .const import (
    CONF_GOOGLE_CALENDAR_ID,
    CONF_ICLOUD_CALENDAR,
    CONF_ICLOUD_PASSWORD,
    CONF_ICLOUD_USERNAME,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_ENABLED,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OAUTH_SCOPES,
)
from .google_client import GoogleClient, build_credentials
from .icloud_client import ICloudClient

_LOGGER = logging.getLogger(__name__)


class CalendarSyncOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Startet mit Google-OAuth, geht dann weiter zu iCloud und Auswahl."""

    DOMAIN = DOMAIN
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return CalendarSyncOptionsFlow(entry)

    def __init__(self) -> None:
        super().__init__()
        self._token_data: dict[str, Any] | None = None
        self._google_calendars: list[dict[str, str]] = []
        self._icloud_user: str | None = None
        self._icloud_pw: str | None = None
        self._icloud_calendars: list[str] = []

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        return {
            "scope": " ".join(OAUTH_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Google-Token ist da – weiter zu iCloud.

        `data` enthält hier bereits {"auth_implementation": ..., "token": {...}}.
        Wir reichen den ganzen Block zum Eintrag weiter.
        """
        self._token_data = data
        try:
            self._google_calendars = await self.hass.async_add_executor_job(
                _list_google_calendars, data
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Google-Kalender konnten nicht gelesen werden: %s", err)
            return self.async_abort(reason="google_fetch_failed")
        return await self.async_step_icloud()

    async def async_step_icloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                calendars = await self.hass.async_add_executor_job(
                    _list_icloud_calendars,
                    user_input[CONF_ICLOUD_USERNAME],
                    user_input[CONF_ICLOUD_PASSWORD],
                )
            except Exception:  # noqa: BLE001
                errors["base"] = "icloud_auth"
            else:
                if not calendars:
                    errors["base"] = "no_calendars"
                else:
                    self._icloud_user = user_input[CONF_ICLOUD_USERNAME]
                    self._icloud_pw = user_input[CONF_ICLOUD_PASSWORD]
                    self._icloud_calendars = calendars
                    return await self.async_step_pick()

        schema = vol.Schema(
            {
                vol.Required(CONF_ICLOUD_USERNAME): str,
                vol.Required(CONF_ICLOUD_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="icloud", data_schema=schema, errors=errors
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._token_data and self._icloud_user and self._icloud_pw
        if user_input is not None:
            await self.async_set_unique_id(
                f"{self._icloud_user}::{user_input[CONF_ICLOUD_CALENDAR]}"
                f"::{user_input[CONF_GOOGLE_CALENDAR_ID]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=(
                    f"{user_input[CONF_ICLOUD_CALENDAR]} ↔ "
                    f"{_google_label(self._google_calendars, user_input[CONF_GOOGLE_CALENDAR_ID])}"
                ),
                data={
                    # auth_implementation + token aus dem OAuth-Flow übernehmen
                    **self._token_data,
                    CONF_ICLOUD_USERNAME: self._icloud_user,
                    CONF_ICLOUD_PASSWORD: self._icloud_pw,
                    CONF_ICLOUD_CALENDAR: user_input[CONF_ICLOUD_CALENDAR],
                    CONF_GOOGLE_CALENDAR_ID: user_input[CONF_GOOGLE_CALENDAR_ID],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_SYNC_ENABLED: user_input[CONF_SYNC_ENABLED],
                },
            )

        google_options = [
            selector.SelectOptionDict(value=c["id"], label=c["label"])
            for c in self._google_calendars
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_ICLOUD_CALENDAR): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._icloud_calendars,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_GOOGLE_CALENDAR_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=google_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): int,
                vol.Optional(CONF_SYNC_ENABLED, default=False): bool,
            }
        )
        return self.async_show_form(step_id="pick", data_schema=schema)


# ------- Executor-Helfer (blockierend) -------

def _list_icloud_calendars(user: str, pw: str) -> list[str]:
    return ICloudClient(user, pw, "").list_calendars()


def _list_google_calendars(token_data: dict[str, Any]) -> list[dict[str, str]]:
    creds = build_credentials(token_data)
    gc = GoogleClient.from_credentials(creds, calendar_id="primary")
    return gc.list_calendars()


def _google_label(calendars: list[dict[str, str]], cid: str) -> str:
    for c in calendars:
        if c["id"] == cid:
            return c["label"]
    return cid


class CalendarSyncOptionsFlow(OptionsFlow):
    """Menü zum Pausieren, Intervall-Ändern, Kalender-Wechseln."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._icloud_calendars: list[str] = []
        self._google_calendars: list[dict[str, str]] = []

    def _opt(self, key: str, default):
        return self._entry.options.get(key, self._entry.data.get(key, default))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hauptmenü."""
        if user_input is not None:
            # Toggle-/Intervall-Formular wurde abgesendet, oder "Kalender wechseln" gewählt
            if user_input.get("change_calendars"):
                return await self.async_step_pick_calendars()
            # Reine Options aktualisieren
            return self.async_create_entry(
                title="",
                data={
                    CONF_SYNC_ENABLED: user_input[CONF_SYNC_ENABLED],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_ICLOUD_CALENDAR: self._opt(CONF_ICLOUD_CALENDAR, ""),
                    CONF_GOOGLE_CALENDAR_ID: self._opt(CONF_GOOGLE_CALENDAR_ID, "primary"),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SYNC_ENABLED,
                    default=self._opt(CONF_SYNC_ENABLED, False),
                ): bool,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self._opt(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): int,
                vol.Optional("change_calendars", default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "icloud_calendar": self._opt(CONF_ICLOUD_CALENDAR, "?"),
                "google_calendar_id": self._opt(CONF_GOOGLE_CALENDAR_ID, "?"),
            },
        )

    async def async_step_pick_calendars(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Kalenderauswahl neu."""
        errors: dict[str, str] = {}
        if not self._icloud_calendars or not self._google_calendars:
            try:
                self._icloud_calendars = await self.hass.async_add_executor_job(
                    _list_icloud_calendars,
                    self._entry.data[CONF_ICLOUD_USERNAME],
                    self._entry.data[CONF_ICLOUD_PASSWORD],
                )
                token_data = {
                    "auth_implementation": self._entry.data.get("auth_implementation"),
                    "token": self._entry.data.get("token", {}),
                }
                self._google_calendars = await self.hass.async_add_executor_job(
                    _list_google_calendars, token_data
                )
            except Exception:  # noqa: BLE001
                return self.async_abort(reason="refetch_failed")

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SYNC_ENABLED: self._opt(CONF_SYNC_ENABLED, False),
                    CONF_SCAN_INTERVAL: self._opt(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_ICLOUD_CALENDAR: user_input[CONF_ICLOUD_CALENDAR],
                    CONF_GOOGLE_CALENDAR_ID: user_input[CONF_GOOGLE_CALENDAR_ID],
                    "reset_mapping": True,
                },
            )

        google_options = [
            selector.SelectOptionDict(value=c["id"], label=c["label"])
            for c in self._google_calendars
        ]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ICLOUD_CALENDAR,
                    default=self._opt(CONF_ICLOUD_CALENDAR, ""),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._icloud_calendars,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_GOOGLE_CALENDAR_ID,
                    default=self._opt(CONF_GOOGLE_CALENDAR_ID, "primary"),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=google_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="pick_calendars", data_schema=schema, errors=errors
        )

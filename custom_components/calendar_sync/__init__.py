"""Calendar Sync Integration – Google ↔ iCloud (bidirektional)."""
from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv

from pathlib import Path

from .const import CONF_SCAN_INTERVAL, DB_FILENAME, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import CalendarSyncCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Falls Kalender gewechselt wurde: Mapping-DB vorher wegräumen
    if entry.options.get("reset_mapping"):
        db_path = Path(hass.config.path(DOMAIN)) / DB_FILENAME
        if db_path.exists():
            try:
                db_path.unlink()
                _LOGGER.info("Mapping-DB zurückgesetzt wegen Kalenderwechsel")
            except OSError as err:
                _LOGGER.warning("Mapping-DB nicht gelöscht: %s", err)
        new_opts = {k: v for k, v in entry.options.items() if k != "reset_mapping"}
        hass.config_entries.async_update_entry(entry, options=new_opts)

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    await oauth_session.async_ensure_token_valid()

    interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    coordinator = CalendarSyncCoordinator(
        hass,
        entry,
        oauth_session=oauth_session,
        update_interval=timedelta(seconds=interval),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    if not hass.services.has_service(DOMAIN, "remove_duplicates"):
        async def _handle_remove_duplicates(call: ServiceCall) -> ServiceResponse:
            dry_run = call.data.get("dry_run", True)
            results = {}
            for entry_id, coord in hass.data.get(DOMAIN, {}).items():
                results[entry_id] = await coord.async_remove_duplicates(dry_run)
            return results

        hass.services.async_register(
            DOMAIN,
            "remove_duplicates",
            _handle_remove_duplicates,
            schema=vol.Schema({vol.Optional("dry_run", default=True): cv.boolean}),
            supports_response=SupportsResponse.OPTIONAL,
        )
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Lade den Eintrag neu, wenn Optionen sich ändern."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: CalendarSyncCoordinator | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if coordinator is not None:
        await coordinator.async_shutdown()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Beim endgültigen Entfernen die Mapping-DB mit löschen."""
    from pathlib import Path
    from .const import DB_FILENAME
    db_path = Path(hass.config.path(DOMAIN)) / DB_FILENAME
    if db_path.exists():
        try:
            db_path.unlink()
            _LOGGER.info("Mapping-DB entfernt: %s", db_path)
        except OSError as err:
            _LOGGER.warning("Konnte Mapping-DB nicht löschen: %s", err)

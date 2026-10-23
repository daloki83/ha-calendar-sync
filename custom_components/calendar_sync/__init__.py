"""Calendar Sync Integration – Google ↔ iCloud (bidirektional)."""
from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir

from pathlib import Path

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, LEGACY_DB_FILENAME
from .coordinator import CalendarSyncCoordinator, db_path_for, issue_id_for

_LOGGER = logging.getLogger(__name__)


def _unlink(path: Path, reason: str) -> None:
    if path.exists():
        try:
            path.unlink()
            _LOGGER.info("Zuordnungs-DB entfernt (%s): %s", reason, path.name)
        except OSError as err:
            _LOGGER.warning("Zuordnungs-DB nicht gelöscht: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Bis v1.0.x teilten sich alle Einträge eine DB – die ist unsicher und wird
    # verworfen. Der erste Lauf verknüpft vorhandene Termine neu und löscht nichts.
    await hass.async_add_executor_job(
        _unlink, Path(hass.config.path(DOMAIN)) / LEGACY_DB_FILENAME, "Migration"
    )

    # Kalender gewechselt: eigene DB zurücksetzen
    if entry.options.get("reset_mapping"):
        await hass.async_add_executor_job(
            _unlink, db_path_for(hass, entry.entry_id), "Kalenderwechsel"
        )
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
            if call.context.user_id:
                user = await hass.auth.async_get_user(call.context.user_id)
                if user is None or not user.is_admin:
                    raise Unauthorized(context=call.context)
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
    ir.async_delete_issue(hass, DOMAIN, issue_id_for(entry.entry_id))
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Beim endgültigen Entfernen die eigene Zuordnungs-DB mit löschen."""
    await hass.async_add_executor_job(
        _unlink, db_path_for(hass, entry.entry_id), "Eintrag entfernt"
    )

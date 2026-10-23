"""Sync-Coordinator mit Last-Write-Wins."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GOOGLE_CALENDAR_ID,
    CONF_ICLOUD_CALENDAR,
    CONF_ICLOUD_PASSWORD,
    CONF_ICLOUD_USERNAME,
    CONF_SYNC_ENABLED,
    DB_FILENAME,
    DOMAIN,
)
from .google_client import GoogleClient, build_credentials
from .icloud_client import ICloudClient
from .mapping_db import Mapping, MappingDB
from .models import SyncEvent

_LOGGER = logging.getLogger(__name__)


class CalendarSyncCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=update_interval
        )
        self._entry = entry
        self._oauth = oauth_session
        storage_dir = Path(hass.config.path(DOMAIN))
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = storage_dir / DB_FILENAME

        self._icloud = ICloudClient(
            username=entry.data[CONF_ICLOUD_USERNAME],
            password=entry.data[CONF_ICLOUD_PASSWORD],
            calendar_name=entry.data[CONF_ICLOUD_CALENDAR],
        )
        self._calendar_id = entry.data.get(CONF_GOOGLE_CALENDAR_ID, "primary")
        self._db: MappingDB | None = None

    async def _async_update_data(self) -> dict:
        if not self._entry.data.get(CONF_SYNC_ENABLED, False):
            _LOGGER.debug("Sync ist deaktiviert – überspringe Lauf")
            return {"paused": True}
        try:
            await self._oauth.async_ensure_token_valid()
            token_data = self._oauth.token
            stats = await self.hass.async_add_executor_job(
                self._sync_once, token_data
            )
            if any(v for k, v in stats.items() if k != "paused"):
                _LOGGER.info("Sync-Lauf: %s", stats)
            else:
                _LOGGER.debug("Sync-Lauf (idle): %s", stats)
            return stats
        except Exception as err:
            raise UpdateFailed(f"Sync fehlgeschlagen: {err}") from err

    async def async_shutdown(self) -> None:  # type: ignore[override]
        await super().async_shutdown()
        if self._db is not None:
            await self.hass.async_add_executor_job(self._db.close)

    # ------------------------------------------------------------------
    #  Blockierender Teil
    # ------------------------------------------------------------------
    def _sync_once(self, token_data: dict) -> dict:
        if self._db is None:
            self._db = MappingDB(self._db_path)

        self._icloud.connect()
        creds = build_credentials({"token": token_data})
        google = GoogleClient.from_credentials(creds, calendar_id=self._calendar_id)

        icloud_events = {e.icloud_uid: e for e in self._icloud.fetch_events()}
        google_events = {e.google_id: e for e in google.fetch_events()}
        _LOGGER.debug(
            "Fetched: %d Google / %d iCloud events",
            len(google_events), len(icloud_events),
        )

        stats = {"created_g": 0, "created_i": 0, "updated": 0, "deleted": 0}

        for gid, gev in google_events.items():
            mapping = self._db.get_by_google(gid)
            if mapping is None:
                uid, href = self._icloud.create_event(gev)
                self._db.upsert(Mapping(
                    google_id=gid, icloud_uid=uid, icloud_href=href,
                    google_updated=_iso(gev.updated),
                    icloud_updated=_iso(gev.updated),
                    content_hash=gev.content_hash(),
                ))
                stats["created_i"] += 1
                continue
            iev = icloud_events.get(mapping.icloud_uid)
            if iev is None:
                google.delete_event(gid)
                self._db.delete_by_google(gid)
                stats["deleted"] += 1
                continue
            self._reconcile(google, gev, iev, mapping, stats)

        for uid, iev in icloud_events.items():
            if self._db.get_by_icloud(uid) is not None:
                continue
            new_gid = google.create_event(iev)
            self._db.upsert(Mapping(
                google_id=new_gid, icloud_uid=uid,
                icloud_href=iev.extra.get("href", ""),
                google_updated=_iso(iev.updated),
                icloud_updated=_iso(iev.updated),
                content_hash=iev.content_hash(),
            ))
            stats["created_g"] += 1

        for mapping in self._db.all():
            if mapping.google_id in google_events:
                continue
            if mapping.icloud_uid in icloud_events:
                iev = icloud_events[mapping.icloud_uid]
                href = iev.extra.get("href") or mapping.icloud_href
                self._icloud.delete_event(href)
                stats["deleted"] += 1
            self._db.delete_by_google(mapping.google_id)

        return stats

    def _reconcile(
        self,
        google: GoogleClient,
        gev: SyncEvent,
        iev: SyncEvent,
        mapping: Mapping,
        stats: dict,
    ) -> None:
        g_hash = gev.content_hash()
        i_hash = iev.content_hash()
        if g_hash == i_hash == mapping.content_hash:
            return
        g_time = gev.updated or datetime.now(timezone.utc)
        i_time = iev.updated or datetime.now(timezone.utc)
        _LOGGER.debug(
            "Reconcile '%s': g_hash=%s i_hash=%s stored=%s g_time=%s i_time=%s",
            gev.summary or iev.summary,
            g_hash[:8], i_hash[:8], mapping.content_hash[:8],
            g_time, i_time,
        )
        if g_time >= i_time:
            self._icloud.update_event(mapping.icloud_href, gev, mapping.icloud_uid)
            new_hash = g_hash
        else:
            google.update_event(mapping.google_id, iev)
            new_hash = i_hash
        self._db.upsert(Mapping(
            google_id=mapping.google_id,
            icloud_uid=mapping.icloud_uid,
            icloud_href=mapping.icloud_href,
            google_updated=_iso(g_time),
            icloud_updated=_iso(i_time),
            content_hash=new_hash,
        ))
        stats["updated"] += 1


def _iso(dt: datetime | None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()

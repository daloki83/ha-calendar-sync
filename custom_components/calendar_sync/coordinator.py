"""Sync-Coordinator mit Last-Write-Wins.

Logik pro Durchlauf:
    1. Alle Events von Google und iCloud lesen.
    2. Für jedes Google-Event: Mapping suchen.
         - kein Mapping → neu auf iCloud anlegen, Mapping speichern.
         - Mapping vorhanden, Partner existiert → vergleichen (Last-Write-Wins).
         - Mapping vorhanden, Partner weg → auf Google ebenfalls löschen.
    3. Für jedes iCloud-Event: Mapping suchen.
         - kein Mapping → neu auf Google anlegen, Mapping speichern.
    4. Für Mappings, deren beide Seiten fehlen: aus DB löschen.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GOOGLE_CALENDAR_ID,
    CONF_ICLOUD_CALENDAR,
    CONF_ICLOUD_PASSWORD,
    CONF_ICLOUD_USERNAME,
    DB_FILENAME,
    DOMAIN,
    TOKEN_FILENAME,
)
from .google_client import GoogleClient
from .icloud_client import ICloudClient
from .mapping_db import Mapping, MappingDB
from .models import SyncEvent

_LOGGER = logging.getLogger(__name__)


class CalendarSyncCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=update_interval
        )
        self._entry = entry
        storage_dir = Path(hass.config.path(f"{DOMAIN}"))
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = storage_dir / DB_FILENAME
        self._token_path = storage_dir / TOKEN_FILENAME

        self._icloud = ICloudClient(
            username=entry.data[CONF_ICLOUD_USERNAME],
            password=entry.data[CONF_ICLOUD_PASSWORD],
            calendar_name=entry.data[CONF_ICLOUD_CALENDAR],
        )
        self._google = GoogleClient(
            token_path=self._token_path,
            calendar_id=entry.data.get(CONF_GOOGLE_CALENDAR_ID, "primary"),
        )
        self._db: MappingDB | None = None

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(self._sync_once)
        except Exception as err:
            raise UpdateFailed(f"Sync fehlgeschlagen: {err}") from err

    async def async_shutdown(self) -> None:  # type: ignore[override]
        await super().async_shutdown()
        if self._db is not None:
            self._db.close()

    # ------------------------------------------------------------------
    #  Alles ab hier läuft im Executor (blockierend)
    # ------------------------------------------------------------------
    def _sync_once(self) -> dict:
        if self._db is None:
            self._db = MappingDB(self._db_path)

        self._icloud.connect()
        google_available = self._token_path.exists()
        if google_available:
            self._google.connect()
        else:
            _LOGGER.info("Google-Token fehlt – überspringe Google-Seite")

        icloud_events = {e.icloud_uid: e for e in self._icloud.fetch_events()}
        google_events: dict[str, SyncEvent] = {}
        if google_available:
            google_events = {e.google_id: e for e in self._google.fetch_events()}

        stats = {"created_g": 0, "created_i": 0, "updated": 0, "deleted": 0}

        # Von Google aus
        if google_available:
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
                    # iCloud-Partner wurde gelöscht → auch Google löschen
                    self._google.delete_event(gid)
                    self._db.delete_by_google(gid)
                    stats["deleted"] += 1
                    continue
                # Beide da → Last-Write-Wins
                self._reconcile(gev, iev, mapping, stats)

        # Von iCloud aus: nur neue (ohne Mapping) nach Google kopieren
        if google_available:
            for uid, iev in icloud_events.items():
                if self._db.get_by_icloud(uid) is not None:
                    continue
                new_gid = self._google.create_event(iev)
                self._db.upsert(Mapping(
                    google_id=new_gid, icloud_uid=uid,
                    icloud_href=iev.extra.get("href", ""),
                    google_updated=_iso(iev.updated),
                    icloud_updated=_iso(iev.updated),
                    content_hash=iev.content_hash(),
                ))
                stats["created_g"] += 1
        else:
            # Google noch nicht verbunden: Mapping-DB wenigstens mit iCloud befüllen,
            # damit später kein Doppelimport passiert.
            for uid, iev in icloud_events.items():
                if self._db.get_by_icloud(uid) is None:
                    continue  # ohne Google-ID kein Mapping

        # Google-seitig gelöschte Events: iCloud-Partner nachziehen
        if google_available:
            for mapping in self._db.all():
                if mapping.google_id in google_events:
                    continue
                if mapping.icloud_uid in icloud_events:
                    self._icloud.delete_event(mapping.icloud_href)
                    stats["deleted"] += 1
                self._db.delete_by_google(mapping.google_id)

        return stats

    def _reconcile(
        self,
        gev: SyncEvent,
        iev: SyncEvent,
        mapping: Mapping,
        stats: dict,
    ) -> None:
        g_hash = gev.content_hash()
        i_hash = iev.content_hash()
        if g_hash == i_hash == mapping.content_hash:
            return  # nichts geändert
        g_time = gev.updated or datetime.now(timezone.utc)
        i_time = iev.updated or datetime.now(timezone.utc)
        if g_time >= i_time:
            # Google gewinnt
            self._icloud.update_event(mapping.icloud_href, gev, mapping.icloud_uid)
            new_hash = g_hash
        else:
            self._google.update_event(mapping.google_id, iev)
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

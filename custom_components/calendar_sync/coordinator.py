"""Sync-Coordinator mit Last-Write-Wins und Löschschutz."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DELETE_THRESHOLD,
    CONF_GOOGLE_CALENDAR_ID,
    CONF_ICLOUD_CALENDAR,
    CONF_ICLOUD_PASSWORD,
    CONF_ICLOUD_USERNAME,
    CONF_SYNC_ENABLED,
    DEFAULT_DELETE_THRESHOLD,
    DELETE_RATIO,
    DELETE_RATIO_MIN_MAPPINGS,
    DOMAIN,
    EMPTY_GUARD_MIN_MAPPINGS,
)
from .google_client import GoogleClient, build_credentials
from .icloud_client import ICloudClient
from .mapping_db import Mapping, MappingDB
from .models import SyncEvent

_LOGGER = logging.getLogger(__name__)


def db_path_for(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(DOMAIN)) / f"{entry_id}.db"


def issue_id_for(entry_id: str) -> str:
    return f"pending_deletions_{entry_id}"


@dataclass(frozen=True)
class PlannedDeletion:
    side: str  # "google" oder "icloud" – auf dieser Seite würde gelöscht
    key: str  # google_id bzw. icloud_uid
    href: str
    summary: str
    start: str

    def label(self) -> str:
        where = "Google" if self.side == "google" else "iCloud"
        return f"{self.summary or '(ohne Titel)'} – {self.start} ({where})"


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
        self._db_path = db_path_for(hass, entry.entry_id)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._icloud_calendar = entry.options.get(
            CONF_ICLOUD_CALENDAR, entry.data[CONF_ICLOUD_CALENDAR]
        )
        self._icloud = ICloudClient(
            username=entry.data[CONF_ICLOUD_USERNAME],
            password=entry.data[CONF_ICLOUD_PASSWORD],
            calendar_name=self._icloud_calendar,
        )
        self._calendar_id = entry.options.get(
            CONF_GOOGLE_CALENDAR_ID,
            entry.data.get(CONF_GOOGLE_CALENDAR_ID, "primary"),
        )
        self._delete_threshold = int(
            entry.options.get(CONF_DELETE_THRESHOLD, DEFAULT_DELETE_THRESHOLD)
        )
        self._db: MappingDB | None = None
        self.pending_deletions: list[PlannedDeletion] = []
        self._approved_keys: frozenset[str] = frozenset()

    async def _async_update_data(self) -> dict:
        sync_on = self._entry.options.get(
            CONF_SYNC_ENABLED, self._entry.data.get(CONF_SYNC_ENABLED, False)
        )
        if not sync_on:
            _LOGGER.debug("Sync ist deaktiviert – überspringe Lauf")
            return {"paused": True}
        try:
            await self._oauth.async_ensure_token_valid()
            token_data = self._oauth.token
            stats = await self.hass.async_add_executor_job(
                self._sync_once, token_data
            )
        except Exception as err:
            raise UpdateFailed(f"Sync fehlgeschlagen: {err}") from err

        self._update_issue()
        if any(v for k, v in stats.items() if k != "paused"):
            _LOGGER.info("Sync-Lauf: %s", stats)
        else:
            _LOGGER.debug("Sync-Lauf (idle): %s", stats)
        return stats

    def _update_issue(self) -> None:
        issue_id = issue_id_for(self._entry.entry_id)
        if not self.pending_deletions:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="pending_deletions",
            translation_placeholders={
                "title": self._entry.title,
                "count": str(len(self.pending_deletions)),
            },
            data={"entry_id": self._entry.entry_id},
        )

    def pending_summary(self, limit: int = 25) -> str:
        lines = [f"- {d.label()}" for d in self.pending_deletions[:limit]]
        rest = len(self.pending_deletions) - limit
        if rest > 0:
            lines.append(f"- … und {rest} weitere")
        return "\n".join(lines)

    async def async_approve_deletions(self) -> None:
        """Freigabe: der nächste Lauf darf genau diese Löschungen ausführen."""
        self._approved_keys = frozenset(f"{d.side}:{d.key}" for d in self.pending_deletions)
        await self.async_refresh()

    async def async_restore_pending(self) -> None:
        """Statt zu löschen: Zuordnungen lösen, damit fehlende Termine neu angelegt werden."""
        pending = list(self.pending_deletions)

        def _drop() -> None:
            db = self._open_db()
            for d in pending:
                if d.side == "google":
                    db.delete_by_google(d.key)
                else:
                    db.delete_by_icloud(d.key)

        await self.hass.async_add_executor_job(_drop)
        self.pending_deletions = []
        self._approved_keys = frozenset()
        await self.async_refresh()

    async def async_shutdown(self) -> None:  # type: ignore[override]
        await super().async_shutdown()
        if self._db is not None:
            await self.hass.async_add_executor_job(self._db.close)

    # ------------------------------------------------------------------
    #  Blockierender Teil
    # ------------------------------------------------------------------
    def _open_db(self) -> MappingDB:
        if self._db is None:
            self._db = MappingDB(self._db_path)
        return self._db

    def _sync_once(self, token_data: dict) -> dict:
        db = self._open_db()

        # Zuordnungen gelten nur für genau dieses Kalenderpaar
        pair = f"{self._calendar_id}|{self._icloud_calendar}"
        if db.get_meta("pair") != pair:
            if db.all():
                _LOGGER.warning("Kalenderpaar geändert – Zuordnungen verworfen")
            db.clear()
            db.set_meta("pair", pair)
        initialized = db.get_meta("initialized") == "1"

        self._icloud.connect()
        creds = build_credentials({"token": token_data})
        google = GoogleClient.from_credentials(creds, calendar_id=self._calendar_id)

        icloud_events = {e.icloud_uid: e for e in self._icloud.fetch_events()}
        google_events = {e.google_id: e for e in google.fetch_events()}
        _LOGGER.debug(
            "Fetched: %d Google / %d iCloud events",
            len(google_events), len(icloud_events),
        )

        mapped_count = len(db.all())
        if mapped_count >= EMPTY_GUARD_MIN_MAPPINGS:
            for name, events in (("Google", google_events), ("iCloud", icloud_events)):
                if not events:
                    raise RuntimeError(
                        f"{name}-Kalender liefert 0 Termine, obwohl {mapped_count} "
                        "zugeordnet sind. Lauf abgebrochen, nichts geändert "
                        "(Abruffehler, falscher Kalender oder abgelaufene Anmeldung?)."
                    )

        stats = {"created_g": 0, "created_i": 0, "updated": 0, "deleted": 0, "matched": 0}
        planned: list[PlannedDeletion] = []

        # Ungemappte iCloud-Events nach Inhalt indexieren, damit identische
        # Termine verknüpft statt kopiert werden (verhindert Duplikate nach
        # Kalenderwechsel / leerer Mapping-DB).
        mapped_i = {m.icloud_uid for m in db.all()}
        i_by_hash: dict[str, list[SyncEvent]] = {}
        for uid, e in icloud_events.items():
            if uid not in mapped_i:
                i_by_hash.setdefault(e.content_hash(), []).append(e)

        for gid, gev in google_events.items():
            mapping = db.get_by_google(gid)
            if mapping is None:
                twins = i_by_hash.get(gev.content_hash())
                if twins:
                    iev = twins.pop(0)
                    db.upsert(Mapping(
                        google_id=gid, icloud_uid=iev.icloud_uid,
                        icloud_href=iev.extra.get("href", ""),
                        google_updated=_iso(gev.updated),
                        icloud_updated=_iso(iev.updated),
                        content_hash=gev.content_hash(),
                    ))
                    stats["matched"] += 1
                    continue
                uid, href = self._icloud.create_event(gev)
                db.upsert(Mapping(
                    google_id=gid, icloud_uid=uid, icloud_href=href,
                    google_updated=_iso(gev.updated),
                    icloud_updated=_iso(gev.updated),
                    content_hash=gev.content_hash(),
                ))
                stats["created_i"] += 1
                continue
            iev = icloud_events.get(mapping.icloud_uid)
            if iev is None:
                # In iCloud gelöscht → in Google löschen (nur geplant)
                planned.append(PlannedDeletion(
                    "google", gid, "", gev.summary, gev.start.isoformat()
                ))
                continue
            self._reconcile(google, gev, iev, mapping, stats)

        for uid, iev in icloud_events.items():
            if db.get_by_icloud(uid) is not None:
                continue
            new_gid = google.create_event(iev)
            db.upsert(Mapping(
                google_id=new_gid, icloud_uid=uid,
                icloud_href=iev.extra.get("href", ""),
                google_updated=_iso(iev.updated),
                icloud_updated=_iso(iev.updated),
                content_hash=iev.content_hash(),
            ))
            stats["created_g"] += 1

        for mapping in db.all():
            if mapping.google_id in google_events:
                continue
            if mapping.icloud_uid in icloud_events:
                # In Google gelöscht → in iCloud löschen (nur geplant)
                iev = icloud_events[mapping.icloud_uid]
                planned.append(PlannedDeletion(
                    "icloud", mapping.icloud_uid,
                    iev.extra.get("href") or mapping.icloud_href,
                    iev.summary, iev.start.isoformat(),
                ))
            else:
                # Auf beiden Seiten weg: nur die Zuordnung aufräumen
                db.delete_by_google(mapping.google_id)

        self._apply_deletions(db, google, planned, mapped_count, initialized, stats)
        db.set_meta("initialized", "1")
        return stats

    def _apply_deletions(
        self,
        db: MappingDB,
        google: GoogleClient,
        planned: list[PlannedDeletion],
        mapped_count: int,
        initialized: bool,
        stats: dict,
    ) -> None:
        if not planned:
            self.pending_deletions = []
            self._approved_keys = frozenset()
            return

        if not initialized:
            # Erster Lauf eines Eintrags/Kalenderpaars löscht grundsätzlich nichts
            _LOGGER.warning(
                "Erster Lauf: %d Löschung(en) übersprungen", len(planned)
            )
            self.pending_deletions = planned
            stats["blocked_deletions"] = len(planned)
            return

        keys = frozenset(f"{d.side}:{d.key}" for d in planned)
        too_many = len(planned) > self._delete_threshold or (
            mapped_count >= DELETE_RATIO_MIN_MAPPINGS
            and len(planned) > mapped_count * DELETE_RATIO
        )
        if too_many and not keys <= self._approved_keys:
            _LOGGER.warning(
                "Löschbremse: %d Löschung(en) blockiert (Schwelle %d) – "
                "Freigabe unter Einstellungen → Reparaturen",
                len(planned), self._delete_threshold,
            )
            self.pending_deletions = planned
            stats["blocked_deletions"] = len(planned)
            return

        for d in planned:
            if d.side == "google":
                google.delete_event(d.key)
                db.delete_by_google(d.key)
            else:
                self._icloud.delete_event(d.href)
                db.delete_by_icloud(d.key)
            stats["deleted"] += 1
        self.pending_deletions = []
        self._approved_keys = frozenset()

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
        self._open_db().upsert(Mapping(
            google_id=mapping.google_id,
            icloud_uid=mapping.icloud_uid,
            icloud_href=mapping.icloud_href,
            google_updated=_iso(g_time),
            icloud_updated=_iso(i_time),
            content_hash=new_hash,
        ))
        stats["updated"] += 1

    async def async_remove_duplicates(self, dry_run: bool) -> dict:
        await self._oauth.async_ensure_token_valid()
        return await self.hass.async_add_executor_job(
            self._dedupe, self._oauth.token, dry_run
        )

    def _dedupe(self, token_data: dict, dry_run: bool) -> dict:
        """Löscht nur von der Integration erzeugte Kopien, die exakte Duplikate sind."""
        self._open_db()
        self._icloud.connect()
        creds = build_credentials({"token": token_data})
        google = GoogleClient.from_credentials(creds, calendar_id=self._calendar_id)

        mappings = self._db.all()
        google_copies = {
            m.google_id for m in mappings if not m.icloud_uid.endswith("@calendar-sync")
        }

        result: dict = {"dry_run": dry_run, "google": [], "icloud": []}

        g_groups: dict[str, list[SyncEvent]] = {}
        g_loose: dict[tuple, list[SyncEvent]] = {}
        for e in google.fetch_events():
            g_groups.setdefault(e.content_hash(), []).append(e)
            g_loose.setdefault(
                (e.summary.strip(), e.start.astimezone(timezone.utc).isoformat()), []
            ).append(e)
        if dry_run:
            result["google_similar"] = [
                [
                    {
                        "summary": e.summary,
                        "start": e.start.isoformat(),
                        "end": e.end.isoformat(),
                        "all_day": e.all_day,
                        "loc": e.location,
                        "desc_len": len(e.description or ""),
                        "rec": e.recurrence,
                        "tz": e.timezone,
                        "hash": e.content_hash()[:8],
                        "ours": bool(e.extra.get("ours")) or e.google_id in google_copies,
                    }
                    for e in evs
                ]
                for evs in g_loose.values()
                if len(evs) > 1
            ][:5]
            result["google_similar_groups"] = sum(1 for v in g_loose.values() if len(v) > 1)
        for events in g_groups.values():
            if len(events) < 2:
                continue
            ours = [e for e in events if e.extra.get("ours") or e.google_id in google_copies]
            originals = [e for e in events if e not in ours]
            if ours and originals:
                doomed = ours
            elif ours:
                doomed = ours[1:]
            else:
                # Inhaltlich identisch, Herkunft unbekannt: genau einen behalten
                doomed = events[1:]
            for e in doomed:
                result["google"].append(f"{e.summary} @ {e.start.isoformat()}")
                if not dry_run:
                    google.delete_event(e.google_id)
                    self._db.delete_by_google(e.google_id)

        i_groups: dict[str, list[SyncEvent]] = {}
        for e in self._icloud.fetch_events():
            i_groups.setdefault(e.content_hash(), []).append(e)
        for events in i_groups.values():
            if len(events) < 2:
                continue
            ours = [e for e in events if (e.icloud_uid or "").endswith("@calendar-sync")]
            originals = [e for e in events if e not in ours]
            doomed = ours if originals else ours[1:]
            for e in doomed:
                result["icloud"].append(f"{e.summary} @ {e.start.isoformat()}")
                if not dry_run:
                    self._icloud.delete_event(e.extra.get("href", ""))
                    self._db.delete_by_icloud(e.icloud_uid)

        result["google_count"] = len(result["google"])
        result["icloud_count"] = len(result["icloud"])
        _LOGGER.info(
            "Duplikat-Bereinigung (dry_run=%s): %d Google, %d iCloud",
            dry_run, result["google_count"], result["icloud_count"],
        )
        return result


def _iso(dt: datetime | None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()

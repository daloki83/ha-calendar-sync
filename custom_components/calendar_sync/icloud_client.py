"""iCloud CalDAV-Client.

Nutzt die `caldav`-Lib. Blockierende Aufrufe werden vom Coordinator per
`hass.async_add_executor_job` ausgeführt.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

import caldav
from caldav.lib.error import NotFoundError
from icalendar import Calendar, Event

from .const import ICLOUD_CALDAV_URL
from .models import SyncEvent

_LOGGER = logging.getLogger(__name__)


def _href_of(dav_event) -> str:
    """Robuste Extraktion der href-URL eines caldav-Events."""
    url = getattr(dav_event, "url", None)
    if url is None:
        return ""
    path = getattr(url, "path", None)
    if path:
        return path
    return str(url)


class ICloudClient:
    def __init__(self, username: str, password: str, calendar_name: str) -> None:
        self._username = username
        self._password = password
        self._calendar_name = calendar_name
        self._client: caldav.DAVClient | None = None
        self._calendar: caldav.Calendar | None = None

    # ---------- Connection ----------
    def connect(self) -> None:
        self._client = caldav.DAVClient(
            url=ICLOUD_CALDAV_URL,
            username=self._username,
            password=self._password,
        )
        principal = self._client.principal()
        for cal in principal.calendars():
            if cal.name == self._calendar_name:
                self._calendar = cal
                return
        raise RuntimeError(
            f"iCloud-Kalender '{self._calendar_name}' nicht gefunden"
        )

    def list_calendars(self) -> list[str]:
        """Hilfsfunktion für den Config-Flow."""
        client = caldav.DAVClient(
            url=ICLOUD_CALDAV_URL, username=self._username, password=self._password
        )
        return [c.name for c in client.principal().calendars()]

    # ---------- Read ----------
    def fetch_events(self, days_back: int = 30, days_forward: int = 365) -> list[SyncEvent]:
        assert self._calendar is not None, "connect() zuerst aufrufen"
        start = datetime.now(timezone.utc) - timedelta(days=days_back)
        end = datetime.now(timezone.utc) + timedelta(days=days_forward)
        results: list[SyncEvent] = []
        for ev in self._calendar.search(start=start, end=end, event=True, expand=False):
            try:
                results.append(self._parse(ev))
            except Exception as err:  # pragma: no cover
                _LOGGER.warning("iCloud-Event konnte nicht geparst werden: %s", err)
        return results

    @staticmethod
    def _parse(dav_event) -> SyncEvent:
        cal = Calendar.from_ical(dav_event.data)
        for comp in cal.walk("VEVENT"):
            dtstart = comp.get("DTSTART").dt
            dtend_prop = comp.get("DTEND")
            dtend = dtend_prop.dt if dtend_prop else dtstart
            all_day = not isinstance(dtstart, datetime)
            if all_day:
                dtstart = datetime.combine(dtstart, datetime.min.time(), tzinfo=timezone.utc)
                dtend = datetime.combine(dtend, datetime.min.time(), tzinfo=timezone.utc)
            else:
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=timezone.utc)
                if dtend.tzinfo is None:
                    dtend = dtend.replace(tzinfo=timezone.utc)
            last_mod = comp.get("LAST-MODIFIED") or comp.get("DTSTAMP")
            updated = last_mod.dt if last_mod else None
            return SyncEvent(
                summary=str(comp.get("SUMMARY") or ""),
                start=dtstart,
                end=dtend,
                all_day=all_day,
                location=str(comp.get("LOCATION") or ""),
                description=str(comp.get("DESCRIPTION") or ""),
                updated=updated,
                icloud_uid=str(comp.get("UID")),
                extra={"href": _href_of(dav_event)},
            )
        raise ValueError("Kein VEVENT in Resource gefunden")

    # ---------- Write ----------
    def create_event(self, ev: SyncEvent) -> tuple[str, str]:
        """Lege ein Event an. Rückgabe: (uid, href)."""
        assert self._calendar is not None
        uid = ev.icloud_uid or f"{uuid.uuid4()}@calendar-sync"
        ical = self._build_ical(ev, uid)
        dav_event = self._calendar.save_event(ical)
        return uid, _href_of(dav_event)

    def update_event(self, href: str, ev: SyncEvent, uid: str) -> None:
        """Direkter CalDAV-PUT auf die bekannte Event-URL ohne ETag-Check."""
        assert self._client is not None and self._calendar is not None
        ical = self._build_ical(ev, uid)
        if not href:
            # Fallback: Lookup per UID, dann PUT auf dessen URL
            try:
                existing = self._calendar.event_by_uid(uid)
                href = _href_of(existing)
            except NotFoundError:
                self._calendar.save_event(ical)
                return
        url = self._absolute_url(href)
        resp = self._client.put(
            url,
            ical.encode("utf-8"),
            {"Content-Type": "text/calendar; charset=utf-8"},
        )
        status = getattr(resp, "status", getattr(resp, "status_code", 0))
        if status and status >= 400:
            raise RuntimeError(
                f"iCloud PUT {url} fehlgeschlagen: HTTP {status}"
            )

    def _absolute_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        base = ICLOUD_CALDAV_URL.rstrip("/")
        return base + ("/" + href.lstrip("/"))

    def delete_event(self, href: str) -> None:
        assert self._calendar is not None
        # href wird ignoriert; wir brauchen UID
        # Fallback: Versuch per URL
        if not href:
            return
        try:
            caldav.Event(client=self._client, url=href).delete()
        except (NotFoundError, AttributeError):
            pass

    def delete_event_by_uid(self, uid: str) -> None:
        assert self._calendar is not None
        try:
            self._calendar.event_by_uid(uid).delete()
        except NotFoundError:
            pass

    @staticmethod
    def _build_ical(ev: SyncEvent, uid: str) -> str:
        cal = Calendar()
        cal.add("prodid", "-//calendar_sync//HA//DE")
        cal.add("version", "2.0")
        vevent = Event()
        vevent.add("uid", uid)
        vevent.add("summary", ev.summary)
        if ev.all_day:
            vevent.add("dtstart", ev.start.date())
            vevent.add("dtend", ev.end.date())
        else:
            vevent.add("dtstart", ev.start)
            vevent.add("dtend", ev.end)
        if ev.location:
            vevent.add("location", ev.location)
        if ev.description:
            vevent.add("description", ev.description)
        vevent.add("dtstamp", datetime.now(timezone.utc))
        vevent.add("last-modified", datetime.now(timezone.utc))
        cal.add_component(vevent)
        return cal.to_ical().decode("utf-8")

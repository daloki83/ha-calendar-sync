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
                extra={"href": dav_event.url.path if hasattr(dav_event.url, "path") else str(dav_event.url)},
            )
        raise ValueError("Kein VEVENT in Resource gefunden")

    # ---------- Write ----------
    def create_event(self, ev: SyncEvent) -> tuple[str, str]:
        """Lege ein Event an. Rückgabe: (uid, href)."""
        assert self._calendar is not None
        uid = ev.icloud_uid or f"{uuid.uuid4()}@calendar-sync"
        ical = self._build_ical(ev, uid)
        dav_event = self._calendar.save_event(ical)
        href = dav_event.url.path if hasattr(dav_event.url, "path") else str(dav_event.url)
        return uid, href

    def update_event(self, href: str, ev: SyncEvent, uid: str) -> None:
        assert self._client is not None
        ical = self._build_ical(ev, uid)
        resource = caldav.Event(client=self._client, url=href, data=ical)
        resource.save()

    def delete_event(self, href: str) -> None:
        assert self._client is not None
        try:
            caldav.Event(client=self._client, url=href).delete()
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

"""Heimatseite: iCloud-Originale werden nie geändert oder gelöscht.

Spielt _sync_once mit Fake-Clients durch, u. a. den Vorfall aus v1.1.3:
neuer iCloud-Termin wurde im selben Lauf gelöscht und aus der Google-Kopie neu angelegt.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.calendar_sync import coordinator as coord_mod
from custom_components.calendar_sync.coordinator import CalendarSyncCoordinator
from custom_components.calendar_sync.icloud_client import _ensure_own
from custom_components.calendar_sync.mapping_db import MappingDB
from custom_components.calendar_sync.models import SyncEvent

_ids = itertools.count()
START = datetime(2026, 12, 23, 9, 15, tzinfo=timezone.utc)


def _ev(summary: str, **kw) -> SyncEvent:
    return SyncEvent(summary=summary, start=START, end=START + timedelta(hours=1), **kw)


class FakeICloud:
    def __init__(self) -> None:
        self.events: dict[str, SyncEvent] = {}
        self.writes: list[tuple[str, str]] = []

    def connect(self) -> None:
        pass

    def fetch_events(self):
        return list(self.events.values())

    def add_original(self, summary: str) -> str:
        uid = f"orig-{next(_ids)}"
        self.events[uid] = _ev(summary, icloud_uid=uid, extra={"href": f"/{uid}.ics"})
        return uid

    def create_event(self, ev):
        uid = f"copy-{next(_ids)}@calendar-sync"
        self.events[uid] = _ev(ev.summary, icloud_uid=uid, extra={"href": f"/{uid}.ics"})
        self.writes.append(("create", uid))
        return uid, f"/{uid}.ics"

    def update_event(self, href, ev, uid):
        _ensure_own(uid)
        self.events[uid] = _ev(ev.summary, icloud_uid=uid, extra={"href": href})
        self.writes.append(("update", uid))

    def delete_event(self, href, uid):
        _ensure_own(uid)
        self.events.pop(uid, None)
        self.writes.append(("delete", uid))


class FakeGoogle:
    def __init__(self) -> None:
        self.events: dict[str, SyncEvent] = {}

    def fetch_events(self):
        return list(self.events.values())

    def add_original(self, summary: str) -> str:
        gid = f"g-{next(_ids)}"
        self.events[gid] = _ev(summary, google_id=gid, extra={"ours": False})
        return gid

    def create_event(self, ev):
        gid = f"g-{next(_ids)}"
        self.events[gid] = _ev(ev.summary, google_id=gid, extra={"ours": True})
        return gid

    def update_event(self, gid, ev):
        ours = self.events[gid].extra["ours"]
        self.events[gid] = _ev(ev.summary, google_id=gid, extra={"ours": ours})

    def delete_event(self, gid):
        self.events.pop(gid, None)


@pytest.fixture
def env(tmp_path, monkeypatch):
    icloud, google = FakeICloud(), FakeGoogle()
    monkeypatch.setattr(coord_mod, "build_credentials", lambda _: None)
    monkeypatch.setattr(
        coord_mod.GoogleClient, "from_credentials", staticmethod(lambda *a, **k: google)
    )
    c = CalendarSyncCoordinator.__new__(CalendarSyncCoordinator)
    c._db = MappingDB(tmp_path / "m.db")
    c._icloud, c._calendar_id, c._icloud_calendar = icloud, "g", "Familie"
    c._delete_threshold = 1
    c.pending_deletions, c._approved_keys = [], frozenset()
    c._sync_once({})  # erster Lauf: initialisiert
    return c, icloud, google


def test_new_icloud_event_is_not_deleted(env):
    c, icloud, google = env
    uid = icloud.add_original("[P] Frauenarzt")
    c._sync_once({})
    c._sync_once({})
    assert uid in icloud.events
    assert len(google.events) == 1
    assert icloud.writes == []


def test_deleted_google_copy_keeps_icloud_original(env):
    c, icloud, google = env
    uid = icloud.add_original("Zahnarzt")
    c._sync_once({})
    google.events.clear()
    c._sync_once({})
    c._sync_once({})
    assert uid in icloud.events
    assert len(google.events) == 1  # Kopie neu angelegt
    assert icloud.writes == []


def test_changed_google_copy_is_reset_from_icloud(env):
    c, icloud, google = env
    uid = icloud.add_original("Elternabend")
    c._sync_once({})
    gid = next(iter(google.events))
    google.events[gid] = _ev("anders", google_id=gid, extra={"ours": True})
    c._sync_once({})
    assert google.events[gid].summary == "Elternabend"
    assert icloud.events[uid].summary == "Elternabend"
    assert icloud.writes == []


def test_deleted_icloud_original_removes_google_copy(env):
    c, icloud, google = env
    uid = icloud.add_original("Turnen")
    c._sync_once({})
    del icloud.events[uid]
    c._sync_once({})
    assert google.events == {}


def test_google_original_flows_to_icloud_copy(env):
    c, icloud, google = env
    gid = google.add_original("Pia Training")
    c._sync_once({})
    (uid,) = icloud.events
    assert uid.endswith("@calendar-sync")
    google.events[gid] = _ev("Pia Training neu", google_id=gid, extra={"ours": False})
    c._sync_once({})
    assert icloud.events[uid].summary == "Pia Training neu"
    del google.events[gid]
    c._sync_once({})
    assert icloud.events == {}


def test_guard_refuses_icloud_original():
    with pytest.raises(RuntimeError):
        _ensure_own("ABC-123")
    _ensure_own("x@calendar-sync")

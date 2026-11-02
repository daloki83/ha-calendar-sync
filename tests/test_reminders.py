"""Erinnerungen: Die Kopie folgt dem Original, ohne dauerhaft als geändert zu gelten."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.calendar_sync.google_client import GoogleClient
from custom_components.calendar_sync.icloud_client import ICloudClient
from custom_components.calendar_sync.models import SyncEvent, normalize_reminders

from test_home_side import env  # noqa: F401  (Fixture)

START = datetime(2026, 12, 23, 9, 0, tzinfo=timezone.utc)


def _ical(*alarms: str, uid: str = "orig", dates: str = "") -> SimpleNamespace:
    times = dates or "DTSTART:20261223T090000Z\r\nDTEND:20261223T100000Z"
    body = "".join(f"BEGIN:VALARM\r\n{a}\r\nEND:VALARM\r\n" for a in alarms)
    return SimpleNamespace(
        url=None,
        data=(
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//DE\r\nBEGIN:VEVENT\r\n"
            f"UID:{uid}\r\nSUMMARY:Arzt\r\n{times}\r\n{body}END:VEVENT\r\nEND:VCALENDAR\r\n"
        ),
    )


def _google_item(reminders: dict) -> dict:
    return {
        "id": "g",
        "summary": "Arzt",
        "start": {"dateTime": "2026-12-23T09:00:00Z"},
        "end": {"dateTime": "2026-12-23T10:00:00Z"},
        "updated": "2026-11-01T00:00:00Z",
        "reminders": reminders,
    }


def test_icloud_reminder_reaches_google_copy_and_stays_stable(env):  # noqa: F811
    c, icloud, google = env
    uid = icloud.add_original("Arzt")
    icloud.events[uid].reminders = [15]
    c._sync_once({})
    (gid,) = google.events
    assert google.events[gid].reminders == [15]
    icloud.events[uid].reminders = [30, 60]
    assert c._sync_once({})["updated"] == 1
    assert google.events[gid].reminders == [30, 60]
    assert c._sync_once({})["updated"] == 0
    assert icloud.writes == []


def test_google_reminder_reaches_icloud_copy(env):  # noqa: F811
    c, icloud, google = env
    gid = google.add_original("Training")
    google.events[gid].reminders = [10]
    c._sync_once({})
    (uid,) = icloud.events
    assert icloud.events[uid].reminders == [10]
    assert c._sync_once({})["updated"] == 0


def test_reminder_in_copy_is_reset(env):  # noqa: F811
    c, icloud, google = env
    uid = icloud.add_original("Arzt")
    c._sync_once({})
    (gid,) = google.events
    google.events[gid].reminders = [5]
    c._sync_once({})
    assert google.events[gid].reminders == []
    assert icloud.events[uid].reminders == []


def test_reminders_do_not_affect_twin_matching():
    a = SyncEvent("Arzt", START, START, reminders=[15])
    b = SyncEvent("Arzt", START, START)
    assert a.content_hash() == b.content_hash()


def test_normalize_keeps_what_google_accepts():
    assert normalize_reminders([15, 15, -5, 50000, 1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_parse_icloud_triggers():
    ev = ICloudClient._parse(_ical(
        "ACTION:DISPLAY\r\nTRIGGER:-PT15M",
        "ACTION:DISPLAY\r\nTRIGGER;RELATED=END:-PT2H",
        "ACTION:DISPLAY\r\nTRIGGER;VALUE=DATE-TIME:20261223T083000Z",
    ))
    assert ev.reminders == [15, 30, 60]


def test_parse_skips_none_and_location_alarms():
    ev = ICloudClient._parse(_ical(
        "ACTION:NONE\r\nTRIGGER;VALUE=DATE-TIME:19760401T005545Z",
        "ACTION:DISPLAY\r\nTRIGGER;VALUE=DATE-TIME:19760401T005545Z",
    ))
    assert ev.reminders == []


def test_all_day_on_the_day_becomes_reminder_at_start():
    ev = ICloudClient._parse(_ical(
        "ACTION:DISPLAY\r\nTRIGGER:PT9H",
        "ACTION:DISPLAY\r\nTRIGGER:-PT15H",
        dates="DTSTART;VALUE=DATE:20261223\r\nDTEND;VALUE=DATE:20261224",
    ))
    assert ev.reminders == [0, 900]


def test_broken_alarm_does_not_lose_the_event():
    ev = ICloudClient._parse(_ical("ACTION:DISPLAY"))
    assert ev.summary == "Arzt" and ev.reminders == []


def test_apple_default_alarm_counts_only_on_originals():
    alarm = "ACTION:DISPLAY\r\nX-APPLE-DEFAULT-ALARM:TRUE\r\nTRIGGER:-PT15M"
    assert ICloudClient._parse(_ical(alarm)).reminders == [15]
    assert ICloudClient._parse(_ical(alarm, uid="x@calendar-sync")).reminders == []


def test_icloud_copy_roundtrip():
    src = SyncEvent("Arzt", START, START, reminders=[0, 10, 900])
    text = ICloudClient._build_ical(src, "x@calendar-sync")
    parsed = ICloudClient._parse(SimpleNamespace(url=None, data=text))
    assert parsed.reminders == [0, 10, 900]


def test_google_parse_uses_calendar_defaults():
    defaults = [{"method": "popup", "minutes": 30}]
    assert GoogleClient._parse(_google_item({"useDefault": True}), defaults).reminders == [30]
    item = _google_item({"useDefault": False, "overrides": [
        {"method": "email", "minutes": 10}, {"method": "popup", "minutes": 10},
    ]})
    assert GoogleClient._parse(item, defaults).reminders == [10]
    assert GoogleClient._parse(_google_item({"useDefault": False}), defaults).reminders == []


def test_google_body_is_explicit():
    body = GoogleClient._to_body(SyncEvent("Arzt", START, START, reminders=[15]))
    assert body["reminders"] == {
        "useDefault": False, "overrides": [{"method": "popup", "minutes": 15}],
    }
    assert GoogleClient._to_body(SyncEvent("Arzt", START, START))["reminders"]["overrides"] == []

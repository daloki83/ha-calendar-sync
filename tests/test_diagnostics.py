"""Diagnosen landen in öffentlichen Issues: Nur Feldnamen und Zeitstempel dürfen hinein."""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.calendar_sync.diagnostics import _icloud_fields

ICAL = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//DE\r\nBEGIN:VEVENT\r\n"
    "UID:orig\r\nSUMMARY:Geheimer Termin\r\nDTSTAMP:20261101T100000Z\r\n"
    "DTSTART:20261223T090000Z\r\nDTEND:20261223T100000Z\r\n"
    "ORGANIZER;CN=Erika:mailto:erika@example.com\r\n"
    "ATTENDEE;CN=Max:mailto:max@example.com\r\n"
    "X-APPLE-STRUCTURED-LOCATION;VALUE=URI:geo:50.1,9.1\r\n"
    "BEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER;VALUE=DATE-TIME:20261223T083000Z\r\nEND:VALARM\r\n"
    "END:VEVENT\r\nEND:VCALENDAR\r\n"
)


def test_diagnostics_show_names_but_no_personal_values():
    calendar = SimpleNamespace(search=lambda **_: [SimpleNamespace(data=ICAL)])
    icloud = SimpleNamespace(connect=lambda: None, _calendar=calendar)
    result = _icloud_fields(icloud)
    props = result["latest"][0]["props"]
    assert props["ORGANIZER"] == props["ATTENDEE"] == []
    assert props["X-APPLE-STRUCTURED-LOCATION"] == []
    assert props["DTSTAMP"] == ["20261101T100000Z"]
    text = str(result)
    for secret in ("erika", "Erika", "max@", "geo:", "Geheimer"):
        assert secret not in text

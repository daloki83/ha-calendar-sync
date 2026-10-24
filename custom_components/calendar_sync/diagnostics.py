"""Diagnose: zeigt, welche Felder iCloud pro Termin mitliefert."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from icalendar import Calendar

from .const import DOMAIN

# Felder, deren Inhalt hilft, einen Ersteller zu erkennen
_SHOW_VALUE = ("ORGANIZER", "ATTENDEE", "CREATED", "LAST-MODIFIED", "DTSTAMP")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    coord = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coord is None:
        return {"error": "Eintrag nicht geladen"}
    return await hass.async_add_executor_job(_icloud_fields, coord._icloud)


def _icloud_fields(icloud) -> dict:
    icloud.connect()
    start = datetime.now(timezone.utc) - timedelta(days=30)
    end = datetime.now(timezone.utc) + timedelta(days=365)
    events = []
    for ev in icloud._calendar.search(start=start, end=end, event=True, expand=False):
        for comp in Calendar.from_ical(ev.data).walk("VEVENT"):
            props = {}
            for name, value in comp.property_items(recursive=False):
                if name in ("BEGIN", "END"):
                    continue
                if name in _SHOW_VALUE or name.startswith("X-"):
                    props.setdefault(name, []).append(
                        value.to_ical().decode(errors="replace")
                        if hasattr(value, "to_ical") else str(value)
                    )
                else:
                    props.setdefault(name, [])
            events.append({"last_modified": str(comp.get("LAST-MODIFIED", "")), "props": props})
            break
    events.sort(key=lambda e: e["last_modified"], reverse=True)
    return {"count": len(events), "latest": events[:8]}

"""Neutrales Event-Modell, in das beide Seiten konvertieren."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SyncEvent:
    """Minimaler Satz an Feldern, die bidirektional gesynct werden."""

    summary: str
    start: datetime
    end: datetime
    all_day: bool = False
    location: str = ""
    description: str = ""
    # Serienregel als iCal-Zeilen (z. B. ["RRULE:FREQ=WEEKLY;BYDAY=MO"]);
    # bei Einzelterminen leer.
    recurrence: list[str] = field(default_factory=list)
    # IANA-TZ-Name der Quelle (z. B. "Europe/Berlin"), leer für UTC/Floating.
    timezone: str = ""
    # Zeitpunkt der letzten Änderung auf der Quellseite (UTC)
    updated: datetime | None = None
    # Herkunfts-IDs (eine davon ist gesetzt, je nach Quelle)
    google_id: str | None = None
    icloud_uid: str | None = None
    extra: dict = field(default_factory=dict)

    def content_hash(self) -> str:
        payload = "|".join(
            [
                _norm_str(self.summary),
                _norm_dt(self.start, self.all_day),
                _norm_dt(self.end, self.all_day),
                "1" if self.all_day else "0",
                _norm_str(self.location),
                _norm_str(self.description),
                _normalize_recurrence(self.recurrence),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _norm_str(s: str) -> str:
    return (s or "").strip().replace("\r\n", "\n")


def _norm_dt(dt: datetime, all_day: bool) -> str:
    if all_day:
        return dt.date().isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_recurrence(lines: list[str]) -> str:
    """Kanonisiere RRULE/RDATE/EXDATE, damit Google- und iCloud-Varianten gleich hashen."""
    canon: list[str] = []
    for raw in lines:
        name, _, value = raw.partition(":")
        name = name.strip().upper()
        # Parameter sortieren (RRULE: FREQ=WEEKLY;BYDAY=MO == BYDAY=MO;FREQ=WEEKLY)
        parts = [p.strip().upper() for p in value.strip().split(";") if p.strip()]
        parts.sort()
        canon.append(f"{name}:{';'.join(parts)}")
    canon.sort()
    return "||".join(canon)

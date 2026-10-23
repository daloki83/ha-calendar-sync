"""Neutrales Event-Modell, in das beide Seiten konvertieren."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


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
    # Zeitpunkt der letzten Änderung auf der Quellseite (UTC)
    updated: datetime | None = None
    # Herkunfts-IDs (eine davon ist gesetzt, je nach Quelle)
    google_id: str | None = None
    icloud_uid: str | None = None
    extra: dict = field(default_factory=dict)

    def content_hash(self) -> str:
        payload = "|".join(
            [
                self.summary.strip(),
                self.start.isoformat(),
                self.end.isoformat(),
                "1" if self.all_day else "0",
                self.location.strip(),
                self.description.strip(),
                ";".join(sorted(self.recurrence)),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

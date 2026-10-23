"""SQLite-Mapping zwischen Google-Events und iCloud-Events.

Spalten:
    google_id          : Google Event-ID
    icloud_uid         : iCloud VEVENT UID
    icloud_href        : CalDAV-Href der iCloud-Resource
    google_updated     : ISO-Timestamp der letzten Google-Änderung, die wir gesehen haben
    icloud_updated     : ISO-Timestamp der letzten iCloud-Änderung, die wir gesehen haben
    content_hash       : Hash des zuletzt synchronisierten Inhalts (für Change-Detection)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Mapping:
    google_id: str
    icloud_uid: str
    icloud_href: str
    google_updated: str
    icloud_updated: str
    content_hash: str


class MappingDB:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS mapping (
                google_id       TEXT PRIMARY KEY,
                icloud_uid      TEXT NOT NULL UNIQUE,
                icloud_href     TEXT NOT NULL,
                google_updated  TEXT NOT NULL,
                icloud_updated  TEXT NOT NULL,
                content_hash    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_icloud_uid ON mapping(icloud_uid);
            """
        )
        self._conn.commit()

    def upsert(self, m: Mapping) -> None:
        self._conn.execute(
            """
            INSERT INTO mapping(google_id, icloud_uid, icloud_href,
                                google_updated, icloud_updated, content_hash)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(google_id) DO UPDATE SET
                icloud_uid=excluded.icloud_uid,
                icloud_href=excluded.icloud_href,
                google_updated=excluded.google_updated,
                icloud_updated=excluded.icloud_updated,
                content_hash=excluded.content_hash
            """,
            (m.google_id, m.icloud_uid, m.icloud_href,
             m.google_updated, m.icloud_updated, m.content_hash),
        )
        self._conn.commit()

    def get_by_google(self, google_id: str) -> Mapping | None:
        row = self._conn.execute(
            "SELECT * FROM mapping WHERE google_id=?", (google_id,)
        ).fetchone()
        return Mapping(**dict(row)) if row else None

    def get_by_icloud(self, icloud_uid: str) -> Mapping | None:
        row = self._conn.execute(
            "SELECT * FROM mapping WHERE icloud_uid=?", (icloud_uid,)
        ).fetchone()
        return Mapping(**dict(row)) if row else None

    def all(self) -> list[Mapping]:
        rows = self._conn.execute("SELECT * FROM mapping").fetchall()
        return [Mapping(**dict(r)) for r in rows]

    def delete_by_google(self, google_id: str) -> None:
        self._conn.execute("DELETE FROM mapping WHERE google_id=?", (google_id,))
        self._conn.commit()

    def delete_by_icloud(self, icloud_uid: str) -> None:
        self._conn.execute("DELETE FROM mapping WHERE icloud_uid=?", (icloud_uid,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

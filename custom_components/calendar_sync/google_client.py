"""Google-Calendar-Client.

OAuth-Flow wird später (sobald das Handy da ist) scharf geschaltet.
Die Methoden hier sind so geschrieben, dass sie mit gültigen Credentials
sofort funktionieren – nur das Beschaffen der Credentials fehlt noch.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .models import SyncEvent

_LOGGER = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleClient:
    def __init__(self, token_path: Path, calendar_id: str) -> None:
        self._token_path = token_path
        self._calendar_id = calendar_id
        self._service = None

    # ---------- Connection ----------
    def connect(self) -> None:
        if not self._token_path.exists():
            raise RuntimeError(
                "Google-Token fehlt – OAuth-Flow noch nicht abgeschlossen"
            )
        data = json.loads(self._token_path.read_text("utf-8"))
        creds = Credentials.from_authorized_user_info(data, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._token_path.write_text(creds.to_json(), "utf-8")
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    # ---------- Read ----------
    def fetch_events(self, days_back: int = 30, days_forward: int = 365) -> list[SyncEvent]:
        assert self._service is not None
        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(days=days_back)).isoformat()
        time_max = (now + timedelta(days=days_forward)).isoformat()
        page_token = None
        out: list[SyncEvent] = []
        while True:
            resp = self._service.events().list(
                calendarId=self._calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=False,
                showDeleted=False,
                pageToken=page_token,
            ).execute()
            for item in resp.get("items", []):
                try:
                    out.append(self._parse(item))
                except Exception as err:  # pragma: no cover
                    _LOGGER.warning("Google-Event konnte nicht geparst werden: %s", err)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    @staticmethod
    def _parse(item: dict) -> SyncEvent:
        start_raw = item["start"]
        end_raw = item["end"]
        if "date" in start_raw:
            all_day = True
            start = datetime.fromisoformat(start_raw["date"]).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(end_raw["date"]).replace(tzinfo=timezone.utc)
        else:
            all_day = False
            start = datetime.fromisoformat(start_raw["dateTime"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_raw["dateTime"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
        return SyncEvent(
            summary=item.get("summary", ""),
            start=start,
            end=end,
            all_day=all_day,
            location=item.get("location", ""),
            description=item.get("description", ""),
            updated=updated,
            google_id=item["id"],
        )

    # ---------- Write ----------
    def create_event(self, ev: SyncEvent) -> str:
        assert self._service is not None
        body = self._to_body(ev)
        created = self._service.events().insert(
            calendarId=self._calendar_id, body=body
        ).execute()
        return created["id"]

    def update_event(self, google_id: str, ev: SyncEvent) -> None:
        assert self._service is not None
        body = self._to_body(ev)
        self._service.events().update(
            calendarId=self._calendar_id, eventId=google_id, body=body
        ).execute()

    def delete_event(self, google_id: str) -> None:
        assert self._service is not None
        self._service.events().delete(
            calendarId=self._calendar_id, eventId=google_id
        ).execute()

    @staticmethod
    def _to_body(ev: SyncEvent) -> dict:
        if ev.all_day:
            body_time = {
                "start": {"date": ev.start.date().isoformat()},
                "end": {"date": ev.end.date().isoformat()},
            }
        else:
            body_time = {
                "start": {"dateTime": ev.start.isoformat()},
                "end": {"dateTime": ev.end.isoformat()},
            }
        return {
            "summary": ev.summary,
            "location": ev.location,
            "description": ev.description,
            **body_time,
        }

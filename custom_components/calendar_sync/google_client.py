"""Google-Calendar-Client.

Credentials kommen aus HAs OAuth-Session (siehe application_credentials.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .const import OAUTH_SCOPES
from .models import SyncEvent

_LOGGER = logging.getLogger(__name__)


def build_credentials(token_data: dict[str, Any]) -> Credentials:
    """Rohes HA-OAuth-Token-Dict in google.oauth2.Credentials umwandeln."""
    tok = token_data.get("token", token_data)
    return Credentials(
        token=tok["access_token"],
        refresh_token=tok.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tok.get("client_id"),
        client_secret=tok.get("client_secret"),
        scopes=OAUTH_SCOPES,
    )


class GoogleClient:
    def __init__(self, calendar_id: str = "primary") -> None:
        self._calendar_id = calendar_id
        self._service = None
        self._creds: Credentials | None = None

    # ---------- Konstruktion ----------
    @classmethod
    def from_credentials(
        cls, creds: Credentials, calendar_id: str = "primary"
    ) -> "GoogleClient":
        obj = cls(calendar_id)
        obj._creds = creds
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        obj._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return obj

    # ---------- Hilfs-API ----------
    def list_calendars(self) -> list[dict[str, str]]:
        """Liste aller Google-Kalender des Nutzers als [{id, label}]."""
        assert self._service is not None
        out: list[dict[str, str]] = []
        page = None
        while True:
            resp = self._service.calendarList().list(pageToken=page).execute()
            for item in resp.get("items", []):
                label = item.get("summaryOverride") or item.get("summary") or item["id"]
                if item.get("primary"):
                    label = f"★ {label}"
                out.append({"id": item["id"], "label": label})
            page = resp.get("nextPageToken")
            if not page:
                break
        return out

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
                    _LOGGER.warning("Google-Event-Parse: %s", err)
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
            recurrence=list(item.get("recurrence", [])),
            updated=updated,
            google_id=item["id"],
        )

    # ---------- Write ----------
    def create_event(self, ev: SyncEvent) -> str:
        assert self._service is not None
        created = self._service.events().insert(
            calendarId=self._calendar_id, body=self._to_body(ev)
        ).execute()
        return created["id"]

    def update_event(self, google_id: str, ev: SyncEvent) -> None:
        assert self._service is not None
        self._service.events().update(
            calendarId=self._calendar_id,
            eventId=google_id,
            body=self._to_body(ev),
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
            start = ev.start if ev.start.tzinfo else ev.start.replace(tzinfo=timezone.utc)
            end = ev.end if ev.end.tzinfo else ev.end.replace(tzinfo=timezone.utc)
            body_time = {
                "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            }
        body = {
            "summary": ev.summary,
            "location": ev.location,
            "description": ev.description,
            **body_time,
        }
        if ev.recurrence:
            body["recurrence"] = list(ev.recurrence)
        return body

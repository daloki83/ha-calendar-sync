"""Konstanten für Calendar Sync."""
from __future__ import annotations

DOMAIN = "calendar_sync"

CONF_ICLOUD_USERNAME = "icloud_username"
CONF_ICLOUD_PASSWORD = "icloud_password"
CONF_ICLOUD_CALENDAR = "icloud_calendar"
CONF_GOOGLE_CALENDAR_ID = "google_calendar_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 300  # 5 Minuten

ICLOUD_CALDAV_URL = "https://caldav.icloud.com"

DB_FILENAME = "calendar_sync_mapping.db"

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

CONF_TOKEN = "token"

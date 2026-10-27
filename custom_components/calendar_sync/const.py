"""Konstanten für Calendar Sync."""
from __future__ import annotations

DOMAIN = "calendar_sync"

CONF_ICLOUD_USERNAME = "icloud_username"
CONF_ICLOUD_PASSWORD = "icloud_password"
CONF_ICLOUD_CALENDAR = "icloud_calendar"
CONF_GOOGLE_CALENDAR_ID = "google_calendar_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SYNC_ENABLED = "sync_enabled"
CONF_DELETE_THRESHOLD = "delete_threshold"
CONF_CONFIRM_SHARED = "confirm_shared"

DEFAULT_SCAN_INTERVAL = 300  # 5 Minuten
DEFAULT_DELETE_THRESHOLD = 5
# Ab so vielen Zuordnungen gilt ein leerer Kalender als Abruffehler
EMPTY_GUARD_MIN_MAPPINGS = 3
# Ab so vielen Zuordnungen greift zusätzlich die 20-%-Regel der Löschbremse
DELETE_RATIO_MIN_MAPPINGS = 10
DELETE_RATIO = 0.2

ICLOUD_CALDAV_URL = "https://caldav.icloud.com"
# UID-Endung der iCloud-Kopien, die das Tool selbst anlegt. Nur die darf es ändern oder löschen.
OWN_UID_SUFFIX = "@calendar-sync"

# Bis v1.0.x eine gemeinsame DB für alle Einträge; seit v1.1 eine pro Eintrag
LEGACY_DB_FILENAME = "calendar_sync_mapping.db"

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

CONF_TOKEN = "token"

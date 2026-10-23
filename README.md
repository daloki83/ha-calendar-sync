# Calendar Sync – Google ↔ iCloud (Home Assistant Custom Integration)

Bidirektionale Synchronisation zwischen einem privaten **Google-Kalender** und
einem **iCloud-Familienkalender**. Unabhängig von Home Assistants eingebauten
Google-/CalDAV-Integrationen – bringt eigene Clients mit.

**Status: v0.4 (stabil).**

## Features

- Bidirektionaler Sync: Titel, Zeit, Ort, Beschreibung, Ganztagsflag
- **Serien-Events** (RRULE, RDATE, EXDATE) inkl. DST-sicherer Zeitzonen
- Konfliktregel: **Last-Write-Wins** per Timestamp
- Löschungen auf einer Seite werden auf der anderen nachgezogen
- Mapping-DB (SQLite) in `config/calendar_sync/` — wird beim Entfernen des Eintrags mit gelöscht
- Pollt alle 5 Minuten (einstellbar)
- „Sync aktivieren"-Schalter zum sicheren Testen

## Noch nicht abgedeckt

- Einzelne Ausnahmen in Serien („Montag ausfallen lassen" als separates Exception-Event)
- Teilnehmer, Erinnerungen, Anhänge, Farben

## Installation via HACS

1. HACS → oben rechts das Menü → *Custom repositories*
2. URL dieses Repos eintragen, Kategorie **Integration**
3. „Calendar Sync" installieren, Home Assistant neu starten
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Calendar Sync*

## iCloud einrichten

1. [appleid.apple.com](https://appleid.apple.com) → *Sign-In and Security* →
   *App-Specific Passwords* → neues Passwort erzeugen
2. Im Config-Flow eintragen: Apple-ID, app-spezifisches Passwort, exakter
   Kalendername (wie in der Apple-Kalender-App)

## Google einrichten

1. [Google Cloud Console](https://console.cloud.google.com/) → neues Projekt oder bestehendes nutzen
2. *APIs & Services → Library* → **Google Calendar API** aktivieren
3. *APIs & Services → OAuth consent screen* → **External**, deine Mail als Testnutzer eintragen
4. *APIs & Services → Credentials → + Create credentials → OAuth client ID*
   - Application type: **Web application**
   - Authorized redirect URI: `https://my.home-assistant.io/redirect/oauth`
5. Client-ID + Client-Secret kopieren
6. In Home Assistant: *Einstellungen → Geräte & Dienste → ⋮ → Application Credentials → Add Application Credential*
   - Integration: Calendar Sync (Google ↔ iCloud)
   - Name: beliebig
   - Client ID + Secret einfügen
7. Danach *Integration hinzufügen → Calendar Sync* starten – OAuth-Dialog öffnet sich automatisch.

## Entwicklung

```
custom_components/calendar_sync/
├── __init__.py          # Entry-Setup
├── manifest.json
├── config_flow.py       # UI zum Einrichten
├── const.py
├── coordinator.py       # Sync-Logik (Last-Write-Wins)
├── google_client.py
├── icloud_client.py
├── mapping_db.py        # SQLite
├── models.py            # SyncEvent
└── translations/
```

## Lizenz

MIT

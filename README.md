# Calendar Sync – Google ↔ iCloud (Home Assistant Custom Integration)

Bidirektionale Synchronisation zwischen einem privaten **Google-Kalender** und
einem **iCloud-Familienkalender**. Unabhängig von Home Assistants eingebauten
Google-/CalDAV-Integrationen – bringt eigene Clients mit.

**Status: v0.1 (Grundgerüst, iCloud fertig, Google-OAuth folgt).**

## Features (Ziel)

- Bidirektionaler Sync: Titel, Zeit, Ort, Beschreibung, Ganztagsflag
- Konfliktregel: **Last-Write-Wins** per Timestamp
- Löschungen auf einer Seite werden auf der anderen nachgezogen
- Mapping-DB (SQLite) in `config/calendar_sync/`
- Pollt alle 5 Minuten (einstellbar)

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

*(folgt in v0.2)* – OAuth-Flow in Vorbereitung.

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

# Changelog

Entstehungsgeschichte der Integration, damit Entscheidungen und Fehlerbilder später nachvollziehbar sind.

## 1.1.0 – Löschschutz

**Vorfall:** Nach dem Einrichten eines zweiten Eintrags (gleicher iCloud-Kalender „Familie“, neuer, leerer Google-Kalender) löschte der erste Lauf 38 Termine aus dem iCloud-Kalender. Wiederhergestellt über iCloud.com → Kalender wiederherstellen.

**Ursache:** Alle Einträge teilten sich eine Zuordnungs-DB. Der neue Eintrag erbte die Zuordnungen des alten Testpaars; da die zugeordneten Google-Termine im neuen Google-Kalender fehlten, wertete der Sync sie als „in Google gelöscht“ und löschte die iCloud-Partner.

**Schutzmaßnahmen:**
1. **Eine Zuordnungs-DB pro Eintrag**, gebunden an das Kalenderpaar. Ändert sich das Paar, werden die Zuordnungen verworfen statt als Löschungen gewertet. Die alte gemeinsame DB wird beim Update entfernt.
2. **Leerer Kalender = Abbruch:** Liefert eine Seite 0 Termine, obwohl mindestens 3 zugeordnet sind, bricht der Lauf ohne Änderung ab.
3. **Löschbremse:** Mehr als 5 Löschungen pro Lauf (einstellbar) oder mehr als 20 % der Zuordnungen werden nicht ausgeführt. Unter *Einstellungen → Reparaturen* erscheint ein Hinweis mit der Liste; dort „Löschen freigeben“ oder „Wiederherstellen“.
4. **Erster Lauf löscht nie** (neuer Eintrag oder neues Kalenderpaar).
5. **Warnung beim Einrichten**, wenn ein Kalender schon von einem anderen Eintrag genutzt wird; Fortfahren nur mit Bestätigung.

## 1.0.0 – Go-Live 🚀

Erste öffentlich stabile Version. Alle bisherigen Fixes und Features sind drin, am Produktivkalender erprobt, die Dokumentation ist auf Deutsch und Englisch komplett.

Enthalten gegenüber 0.5.1:
- Zweisprachiges README mit Sprach-Picker (0.5.2).

## 0.5.0 – Sicherheitscheck und Doku

- Zugangsdaten werden nur noch an `https://…icloud.com` gesendet.
- Serienregeln werden vor dem Schreiben nach iCloud validiert (Schutz vor iCal-Injection).
- `calendar_sync.remove_duplicates` nur noch für Administratoren.
- Obergrenzen für alle Abhängigkeiten.
- Komplette Einrichtungsanleitung (README), `SECURITY.md`, dieser Changelog.

## 0.4.5 – 0.4.7 – Duplikate nach Kalenderwechsel

**Vorfall:** Nach „Kalender wechseln“ auf den produktiven Familienkalender war jeder Termin doppelt – in iCloud und in Google.

**Ursache:** Beim Wechsel wird die Zuordnungsliste geleert. Der erste Lauf behandelte danach jeden Termin als neu und kopierte ihn auf die Gegenseite, obwohl dort schon ein identischer Termin existierte.

**Behebung:**
- Sync gestoppt, Sync-Schalter auf AUS.
- Vor dem Kopieren werden jetzt inhaltsgleiche Termine auf der Gegenseite gesucht und **verknüpft** (`matched`).
- Neuer Dienst `calendar_sync.remove_duplicates` mit Probelauf (`dry_run`, Standard `true`).
- In Google angelegte Termine erhalten eine unsichtbare Herkunftsmarkierung.
- 0.4.7: Identische Google-Termine ohne Markierung (aus älteren Versionen) werden ebenfalls bereinigt; genau einer bleibt.
- Ergebnis: 38 Duplikate in iCloud und 38 in Google entfernt, danach `matched: 21`, keine neuen Duplikate.

## 0.4.1 – 0.4.4 – Bedienung

- Menü „Konfigurieren“: Sync pausieren, Intervall, Kalender wechseln – ohne Neueinrichtung.
- Eintrag wird nach Kalenderwechsel umbenannt; Google-Kalender mit Namen statt ID.
- Neuer Name „Calendar 2-way Sync – Google ↔ iCloud“ (ab 0.5.1), eigenes Icon.
- Icons liegen unter `custom_components/calendar_sync/brand/` (Brands-Proxy ab HA 2026.3; ein PR an `home-assistant/brands` wird für Custom-Integrationen nicht mehr angenommen).

## 0.4.0 – Erste stabile Version

## 0.3.0 – 0.3.5 – Serientermine

- RRULE/RDATE/EXDATE in beide Richtungen.
- Hash-Normalisierung (UTC-Zeiten, sortierte Serienregeln), damit Google- und Apple-Schreibweisen nicht als Änderung gelten („Ping-Pong“ zwischen den Seiten).
- Zeitzone der Quelle wird übernommen: Serien verschieben sich nicht mehr um 1 h beim Wechsel Sommer-/Winterzeit.
- Zuordnungsliste wird beim Entfernen des Eintrags gelöscht.

## 0.2.0 – 0.2.12 – Google und Robustheit

- Google-OAuth über die Anwendungs-Zugangsdaten von Home Assistant.
- „Synchronisation aktivieren“-Schalter (Standard AUS).
- iCloud-spezifische Workarounds: Updates und Löschungen per direktem PUT/DELETE auf die Event-URL, weil iCloud bei UID-Abfragen mit `412 Precondition Failed` antwortet.
- Zeitzonen-Pflichtfeld für Google, SQLite-Thread-Sicherheit, gelockerte Abhängigkeiten (Konflikt mit `caldav.async_davclient`).

## 0.1.0 – 0.1.1 – Grundgerüst

- HACS-Struktur, iCloud-CalDAV-Client, SQLite-Zuordnungsliste, Last-Write-Wins.
- Einrichtung in zwei Schritten mit Kalender-Auswahlliste.

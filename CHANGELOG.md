# Changelog

Entstehungsgeschichte der Integration, damit Entscheidungen und Fehlerbilder später nachvollziehbar sind.

## 1.2.0 – Heimatseite: iCloud-Originale sind tabu

**Vorfall:** Ein neu in iCloud „Familie“ angelegter Termin (23.12., „[P] Frauenarzt“) wurde gelöscht und 5 Minuten später aus der Google-Kopie neu angelegt. Erinnerungen und alle anderen Angaben, die das Tool nicht kennt, gingen verloren.

**Ursache:** Die Löschprüfung verglich die Zuordnungen mit der Google-Liste vom Anfang des Laufs. Die Google-Kopie, die im selben Lauf angelegt wurde, fehlte darin und galt deshalb als „in Google gelöscht“. Das iCloud-Original wurde gelöscht; die Löschbremse stand auf 1 und hielt eine einzelne Löschung nicht auf. Dahinter stand ein Grundproblem: Bei Abweichungen gewann die jüngere Seite, und eine Google-Kopie ist immer jünger als ihr iCloud-Original.

**Neuer Ansatz:**
1. **Heimatseite:** Jeder Termin gehört der Seite, auf der er entstanden ist. Nur von dort wird übertragen, überschrieben oder gelöscht wird immer nur die Kopie. „Die letzte Änderung gewinnt“ entfällt.
2. **iCloud-Originale sind tabu:** Fehlt die Google-Kopie, wird sie neu angelegt, das Original bleibt. Zusätzlich verweigert der iCloud-Client jedes Ändern und Löschen von Terminen ohne `@calendar-sync` in der UID.
3. **Bug behoben:** Kopien aus dem laufenden Lauf gelten nicht mehr als gelöscht.
4. **Kopien kennen ihr Original:** Neue und geänderte Kopien tragen dessen Kennung (iCloud: `X-CALSYNC-SOURCE`, Google: `source_uid`). Geht die Zuordnungsliste verloren, werden die Paare daraus wiederhergestellt statt doppelt angelegt.
5. **Kopien werden nie Quelle:** Eine Kopie ohne zugeordnetes Original wird weder weiterkopiert noch gelöscht, nur übersprungen.
6. **Tests** spielen den Vorfall, den Verlust der Zuordnungsliste und die Regeln mit Fake-Kalendern durch und laufen in der CI.

## 1.1.3 – Absturz von Home Assistant behoben

**Fehlerbild:** Ab v1.1.1 stürzte Home Assistant etwa stündlich ab (Exit-Code 139, Segfault). Laut Crash-Protokoll stand ein Thread in `MappingDB.get_meta`, während ein anderer `MappingDB.close` ausführte.

**Ursache:** Der stündliche Google-Token-Refresh ändert den Config-Eintrag. Das löste den Update-Listener aus, und der lud den Eintrag komplett neu. Beim Entladen wurde die SQLite-Verbindung geschlossen, während der gerade gestartete Sync sie noch nutzte.

**Fix:**
1. Neu geladen wird nur noch, wenn sich die Optionen wirklich ändern.
2. Sync, Duplikat-Bereinigung und das Schließen der DB laufen nacheinander unter einem Lock. Das Entladen wartet also auf einen laufenden Sync.

## 1.1.2 – Diagnose

*Diagnose herunterladen* zeigt, welche Felder iCloud pro Termin mitliefert.

## 1.1.1 – Sync-Intervall

Ohne Entitäten hatte der Coordinator keinen Listener, deshalb plante HA keine Intervall-Läufe ein. Ein leerer Listener hält das Intervall jetzt am Leben.

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

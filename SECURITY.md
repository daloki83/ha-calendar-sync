# Sicherheit

## Sicherheitscheck (v0.5.0, 2026-10-23)

Geprüft wurden der gesamte Code unter `custom_components/calendar_sync/`, die Git-Historie und die Abhängigkeiten.

### Ergebnis

| # | Bereich | Befund | Status |
|---|---|---|---|
| 1 | Geheimnisse im Repo | Git-Historie nach Tokens, Client-Secrets, Passwörtern, privaten Schlüsseln durchsucht – nichts gefunden. `.gitignore` schließt Zuordnungs-DB und Token-Dateien aus. | ✅ ok |
| 2 | Zugangsdaten an fremde Hosts | Vom Server gelieferte absolute Event-URLs wurden ungeprüft genutzt. Apple-ID und App-Passwort hätten so per Basic-Auth an einen anderen Host gehen können. | ✅ behoben: nur `https://…icloud.com` erlaubt |
| 3 | iCal-Injection | Serienregeln aus Google wurden ungeprüft als Zeilen in iCloud-Termine geschrieben. Zeilenumbrüche hätten beliebige iCal-Felder einschleusen können. | ✅ behoben: nur einzeilige `RRULE`/`RDATE`/`EXDATE`-Zeilen |
| 4 | Lösch-Dienst | `calendar_sync.remove_duplicates` war für jeden HA-Benutzer aufrufbar. | ✅ behoben: nur Administratoren |
| 5 | Abhängigkeiten | Nur Untergrenzen; ein künftiges Major-Release wäre ungeprüft installiert worden. | ✅ behoben: Obergrenzen gesetzt |
| 6 | Logging | Keine Passwörter oder Tokens im Log. Termintitel nur auf DEBUG-Level, Duplikat-Bereinigung listet Titel bewusst in der Dienst-Antwort. | ✅ ok |
| 7 | Speicherung der Zugangsdaten | iCloud-App-Passwort und Google-Token liegen im Klartext in `config/.storage/core.config_entries`. Das ist Standard für alle HA-Integrationen. | ⚠️ akzeptiert, siehe Empfehlungen |
| 8 | Google-Berechtigung | Scope `calendar` (Vollzugriff auf alle Kalender), nötig für Kalenderliste und Schreibzugriff. Ein engerer Scope würde eine Neuanmeldung aller Nutzer erfordern. | ⚠️ akzeptiert |
| 9 | Löschungen | Der Sync löscht Termine auf der Gegenseite, wenn sie auf einer Seite gelöscht wurden; die Duplikat-Bereinigung löscht identische Termine. | ⚠️ gewollt; Probelauf ist Standard, „Sync aktiv“ standardmäßig AUS |

### Empfehlungen für Nutzer

- **Nur app-spezifische Passwörter** von Apple verwenden – nie das Apple-ID-Passwort. Bei Verdacht sofort unter account.apple.com widerrufen.
- Den **Google-OAuth-Client** nur für diese Integration nutzen. Zugriff widerrufbar unter [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
- **Home-Assistant-Backups** schützen (Verschlüsselung aktivieren), da sie die Zugangsdaten enthalten.
- Vor dem ersten Sync mit einem produktiven Kalender: mit **Synchronisation AUS** einrichten und ggf. mit Testkalendern üben.

## Sicherheitslücke melden

Bitte **kein öffentliches Issue** anlegen, sondern über GitHub **Security → Report a vulnerability** in diesem Repository melden.

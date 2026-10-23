# Calendar 2-way Sync – Google ↔ iCloud

Home-Assistant-Integration (HACS), die einen **Google-Kalender** und einen **iCloud-Kalender** (z. B. einen Familienkalender) in **beide Richtungen** synchron hält.

Die Integration bringt eigene Clients für Google und iCloud mit und ist unabhängig von den eingebauten Google- und CalDAV-Integrationen von Home Assistant.

---

## Inhalt

1. [Was synchronisiert wird](#1-was-synchronisiert-wird)
2. [Voraussetzungen](#2-voraussetzungen)
3. [iCloud vorbereiten](#3-icloud-vorbereiten)
4. [Google vorbereiten](#4-google-vorbereiten)
5. [Integration installieren](#5-integration-installieren)
6. [Integration einrichten](#6-integration-einrichten)
7. [Erster Sync – sicher starten](#7-erster-sync--sicher-starten)
8. [Einstellungen ändern (Pausieren, Intervall, Kalender wechseln)](#8-einstellungen-ändern)
9. [Duplikate entfernen: `calendar_sync.remove_duplicates`](#9-duplikate-entfernen-calendar_syncremove_duplicates)
10. [So funktioniert der Sync](#10-so-funktioniert-der-sync)
11. [Fehlersuche](#11-fehlersuche)
12. [Grenzen](#12-grenzen)
13. [Sicherheit](#13-sicherheit)

---

## 1. Was synchronisiert wird

| Feld | Google → iCloud | iCloud → Google |
|---|---|---|
| Titel, Ort, Beschreibung | ✅ | ✅ |
| Start, Ende, ganztägig | ✅ | ✅ |
| Serien (RRULE, RDATE, EXDATE) | ✅ | ✅ |
| Zeitzone (sommerzeitsicher) | ✅ | ✅ |
| Neu anlegen / ändern / löschen | ✅ | ✅ |
| Teilnehmer, Erinnerungen, Anhänge, Farben | ❌ | ❌ |
| Einzeln geänderte Termine einer Serie | ❌ | ❌ |

- **Konfliktregel:** Wurde ein Termin auf beiden Seiten geändert, gewinnt die **zuletzt geänderte** Seite (Last-Write-Wins).
- **Zeitfenster:** Synchronisiert werden Termine von **30 Tagen in der Vergangenheit bis 365 Tage in der Zukunft**. Serien werden über ihren Starttermin erfasst.
- **Intervall:** Standardmäßig alle 300 Sekunden (5 Minuten), einstellbar.

---

## 2. Voraussetzungen

- Home Assistant **2026.3 oder neuer** (für das Icon; die Funktion selbst läuft ab 2024.1)
- [HACS](https://hacs.xyz/) installiert
- Eine **Apple-ID** mit Zugriff auf den iCloud-Kalender. Bei einem geteilten Familienkalender braucht die Apple-ID Schreibrechte.
- Ein **Google-Konto** und ein Google-Cloud-Projekt (kostenlos, siehe unten)

---

## 3. iCloud vorbereiten

iCloud bietet keine offizielle API. Der Zugriff läuft über **CalDAV** mit einem **app-spezifischen Passwort** – nicht mit deinem normalen Apple-Passwort.

1. Öffne [account.apple.com](https://account.apple.com) und melde dich an.
2. **Anmeldung und Sicherheit** → **App-spezifische Passwörter** → **+**.
3. Namen vergeben, z. B. `Home Assistant Calendar Sync`.
4. Das angezeigte Passwort (Format `xxxx-xxxx-xxxx-xxxx`) notieren. Es wird nur einmal angezeigt.

Das Passwort lässt sich dort jederzeit widerrufen. Danach funktioniert nur dieser Zugang nicht mehr; dein Apple-Konto ist nicht betroffen.

---

## 4. Google vorbereiten

Google erlaubt Zugriff auf private Kalender nur per **OAuth**. Dafür brauchst du einmalig ein eigenes Google-Cloud-Projekt. Das ist kostenlos; ignoriere Angebote für Guthaben oder Testphasen.

### 4.1 Projekt anlegen

1. [console.cloud.google.com](https://console.cloud.google.com/) öffnen.
2. Oben links **Projekt auswählen** → **Neues Projekt**.
3. Name: z. B. `HA Calendar Sync`, Organisation: **Keine Organisation** → **Erstellen**.
4. Oben links das neue Projekt **auswählen**. Alle folgenden Schritte müssen in diesem Projekt passieren.

### 4.2 Google Calendar API aktivieren

1. Menü → **APIs und Dienste** → **Bibliothek**.
2. Nach `Google Calendar API` suchen → öffnen → **Aktivieren**.

### 4.3 OAuth-Zustimmungsbildschirm (Google Auth Platform)

1. Menü → **APIs und Dienste** → **OAuth-Zustimmungsbildschirm** → **Jetzt starten**.
2. App-Name: z. B. `HA Calendar Sync`, Support-E-Mail: deine Adresse.
3. Zielgruppe: **Extern**.
4. Kontakt-E-Mail: deine Adresse, Nutzungsbedingungen bestätigen → **Erstellen**.
5. Links **Zielgruppe** → **Testnutzer** → **+ Add users** → **deine Google-Adresse** eintragen → Speichern.

> ⚠️ Ohne diesen Testnutzer-Eintrag bricht der Google-Login später mit **„Zugriff blockiert … Fehler 403: access_denied“** ab.

### 4.4 OAuth-Client anlegen

1. Links **Clients** → **+ Client erstellen**.
2. Anwendungstyp: **Webanwendung**, Name: `Home Assistant`.
3. **Autorisierte Weiterleitungs-URIs** → **+ URI hinzufügen**:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
4. **Erstellen** → **Client-ID** und **Clientschlüssel** kopieren.

> Hinweis: Solange die App im Status „Testing“ ist, kann Google die Anmeldung nach einigen Tagen ablaufen lassen. Home Assistant meldet das dann, und du meldest dich einmal neu an.

---

## 5. Integration installieren

1. HACS → oben rechts **⋮** → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/daloki83/ha-calendar-sync`, Typ **Integration** → **Hinzufügen**.
3. **Calendar 2-way Sync – Google ↔ iCloud** suchen → **Herunterladen**.
4. Home Assistant **neu starten**.

---

## 6. Integration einrichten

### 6.1 Google-Zugangsdaten in Home Assistant hinterlegen

1. **Einstellungen** → **Geräte & Dienste** → oben rechts **⋮** → **Anwendungs-Zugangsdaten**.
2. **+ Anwendungs-Zugangsdaten hinzufügen**:
   - Integration: **Calendar 2-way Sync – Google ↔ iCloud**
   - Name: beliebig
   - OAuth Client ID und Client Secret aus Schritt 4.4 einfügen.

### 6.2 Integration hinzufügen

1. **Einstellungen** → **Geräte & Dienste** → **+ Integration hinzufügen** → **Calendar 2-way Sync – Google ↔ iCloud**.
2. **Google:** Zugangsdaten auswählen → Google-Login öffnet sich.
   - Warnung „Google hat diese App nicht überprüft“: **Erweitert** → **… aufrufen (unsicher)**. Das ist bei eigenen Testing-Apps normal.
   - Kalenderzugriff erlauben.
3. **iCloud:** Apple-ID (E-Mail) und das app-spezifische Passwort aus Schritt 3.
4. **Kalender wählen:**
   - iCloud-Kalender (Liste)
   - Google-Kalender (Liste, ★ = Hauptkalender)
   - Sync-Intervall in Sekunden
   - **Synchronisation aktivieren** – beim ersten Mal **AUS lassen** (siehe Kapitel 7)

Der Eintrag heißt danach z. B. `Familie ↔ Familie Google`.

---

## 7. Erster Sync – sicher starten

Gerade bei einem **produktiven** Kalender (z. B. Familienkalender):

1. Einrichten mit **Synchronisation AUS**.
2. Optional zuerst mit zwei leeren **Testkalendern** ausprobieren.
3. Dann unter **Konfigurieren** den Haken **Synchronisation aktiv** setzen.

Beim ersten Lauf geschieht Folgendes:

- Termine, die es auf **beiden** Seiten schon gibt (gleicher Titel, gleiche Zeit, gleicher Ort, gleiche Beschreibung, gleiche Serie), werden **verknüpft, nicht kopiert**.
- Nur Termine, die es auf einer Seite noch nicht gibt, werden übertragen.

Das Ergebnis steht im Log (siehe [Fehlersuche](#11-fehlersuche)), z. B.:

```
Sync-Lauf: {'created_g': 0, 'created_i': 0, 'updated': 0, 'deleted': 0, 'matched': 21}
```

| Wert | Bedeutung |
|---|---|
| `created_g` | in Google neu angelegt |
| `created_i` | in iCloud neu angelegt |
| `updated` | geändert (Last-Write-Wins) |
| `deleted` | gelöscht, weil auf der anderen Seite gelöscht |
| `matched` | vorhandene gleiche Termine verknüpft |

---

## 8. Einstellungen ändern

**Einstellungen** → **Geräte & Dienste** → **Calendar 2-way Sync – Google ↔ iCloud** → **⚙ (Konfigurieren)** am Eintrag:

- **Synchronisation aktiv** – Sync pausieren oder fortsetzen. Pausiert wird nichts gelesen oder geschrieben.
- **Sync-Intervall in Sekunden**
- **Kalender wechseln** – Haken setzen → **OK** → im nächsten Schritt neue Kalender wählen.
  - Die interne Zuordnungsliste wird dabei geleert.
  - Der nächste Lauf verknüpft gleiche Termine, statt sie zu kopieren (ab v0.4.5).
  - Der Name des Eintrags wird automatisch angepasst.

Ein Neu-Einrichten ist für diese Änderungen nicht nötig.

---

## 9. Duplikate entfernen: `calendar_sync.remove_duplicates`

### Wann brauche ich das?

- Nach einem Fehler oder Versionswechsel tauchen Termine **doppelt** auf.
- Konkreter Fall aus der Entwicklung: Vor v0.4.5 hat ein **Kalenderwechsel** alle Termine auf beide Seiten kopiert, obwohl sie dort schon existierten.

### Was macht der Dienst?

Er sucht in **beiden** Kalendern nach Terminen, die **inhaltlich identisch** sind (Titel, Start, Ende, ganztägig, Ort, Beschreibung, Serie), und löscht davon die überzähligen:

- **iCloud:** Gelöscht werden nur Kopien, die die Integration selbst angelegt hat (UID endet auf `@calendar-sync`). Ein identisches Original muss übrig bleiben. Sind alle Termine einer Gruppe Kopien, bleibt genau einer.
- **Google:** Bevorzugt gelöscht werden Kopien der Integration (ab v0.4.5 unsichtbar markiert bzw. über die Zuordnungsliste erkennbar). Ist die Herkunft unbekannt, bleibt von identischen Terminen **genau einer** übrig.
- Termine, die sich in irgendeinem Feld unterscheiden, werden **nie** angefasst.

### So rufst du ihn auf

Nur **Administratoren** dürfen den Dienst ausführen.

1. **Zuerst Sync pausieren:** Konfigurieren → Haken „Synchronisation aktiv“ entfernen.
2. **Entwicklerwerkzeuge** → **Aktionen** → `calendar_sync.remove_duplicates`.
3. **Probelauf** (löscht nichts, zeigt nur an):
   ```yaml
   action: calendar_sync.remove_duplicates
   data:
     dry_run: true
   ```
   **Aktion ausführen** → unten erscheint die Antwort:
   ```yaml
   01M5M336...:
     dry_run: true
     google_count: 0
     icloud_count: 38
     icloud:
       - "Pia Geburtstag @ 2017-06-26T00:00:00+00:00"
       - "[P] Englischarbeit @ 2026-09-28T08:00:00+02:00"
       ...
     google_similar_groups: 0
   ```
   - `google_count` / `icloud_count`: so viele Termine **würden** gelöscht.
   - `google_similar`: Termine mit gleichem Titel und Start, die sich trotzdem unterscheiden (z. B. andere Beschreibung). Diese werden **nicht** gelöscht – zur manuellen Kontrolle.
4. Liste prüfen. Passt sie, **echt ausführen**:
   ```yaml
   action: calendar_sync.remove_duplicates
   data:
     dry_run: false
   ```
5. **Kontrolle:** noch einmal mit `dry_run: true` – beide Zähler sollten `0` sein.
6. Kalender in der Apple- und Google-App prüfen.
7. **Sync wieder einschalten.** Der nächste Lauf verknüpft die übrigen Termine (`matched`).

> ⚠️ Gelöschte Termine sind weg. Google behält sie etwa 30 Tage im Papierkorb des Kalenders; iCloud kann Kalender über **account.apple.com → Daten wiederherstellen** auf einen früheren Stand zurücksetzen. Den Probelauf deshalb nie überspringen.

---

## 10. So funktioniert der Sync

- **Zuordnungsliste:** Eine SQLite-Datei unter `config/calendar_sync/calendar_sync_mapping.db` merkt sich, welcher Google-Termin zu welchem iCloud-Termin gehört, plus einen Prüfwert (Hash) des zuletzt synchronisierten Inhalts.
- **Änderungserkennung:** Pro Lauf werden beide Seiten gelesen und Hashes verglichen. Zeiten werden dafür auf UTC normalisiert, Serienregeln vereinheitlicht – so erzeugen unterschiedliche Schreibweisen von Google und Apple keine Scheinänderungen.
- **Löschungen:** Fehlt ein bereits verknüpfter Termin auf einer Seite, wird er auf der anderen Seite ebenfalls gelöscht.
- **Herkunftsmarkierung:** In iCloud angelegte Kopien haben eine UID mit `@calendar-sync`, in Google angelegte Kopien eine unsichtbare Eigenschaft `calendar_sync=1`.
- **Entfernen des Eintrags** löscht auch die Zuordnungsliste. Die Kalender selbst bleiben unverändert.

---

## 11. Fehlersuche

**Logs ansehen:** Einstellungen → System → Protokolle → nach `calendar_sync` filtern.
Für Details pro Termin: Integration → **⋮** → **Debug-Protokollierung aktivieren**.

| Meldung / Symptom | Ursache | Lösung |
|---|---|---|
| Google: „Zugriff blockiert … 403 access_denied“ | Google-Adresse nicht als Testnutzer eingetragen | Schritt 4.3 Punkt 5 |
| „iCloud-Login fehlgeschlagen“ | falsches oder widerrufenes app-spezifisches Passwort | neues Passwort erzeugen (Schritt 3) |
| `KeyError: 'auth_implementation'` | Eintrag aus einer Version vor 0.2 | Eintrag löschen und neu einrichten |
| „Sync fehlgeschlagen … 401“ | iCloud-Passwort ungültig | neues app-spezifisches Passwort, Eintrag neu einrichten |
| Google-Anmeldung abgelaufen | OAuth-App im Status „Testing“ | in HA neu anmelden |
| Termine doppelt | siehe Kapitel 9 | `calendar_sync.remove_duplicates` |
| Serientermin um 1 h verschoben (Sommer-/Winterzeit) | Version vor 0.3.5 | auf aktuelle Version aktualisieren |

---

## 12. Grenzen

- Einzeln geänderte Termine einer Serie („diesen Montag 1 h später“) werden nicht übertragen; ausgelassene Termine (EXDATE) schon.
- Teilnehmer, Erinnerungen, Anhänge und Farben werden nicht synchronisiert.
- Es wird gepollt (Standard 5 Minuten), kein Echtzeit-Push.
- iCloud-CalDAV ist nicht offiziell dokumentiert; Apple kann das Verhalten ändern.
- Ein Eintrag synchronisiert genau ein Kalenderpaar. Für mehrere Paare weitere Einträge anlegen.

---

## 13. Sicherheit

Siehe [SECURITY.md](SECURITY.md). Kurzfassung:

- Apple-ID-Passwort niemals verwenden, nur **app-spezifische Passwörter**.
- Zugangsdaten liegen – wie bei allen HA-Integrationen – in `config/.storage/core.config_entries`. Backups von Home Assistant entsprechend schützen.
- Google-Zugriff jederzeit widerrufbar unter [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Lizenz

MIT

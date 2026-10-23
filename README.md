# Calendar 2-way Sync – Google ↔ iCloud

**🌐 Language / Sprache:** [🇩🇪 Deutsch](#deutsch) · [🇬🇧 English](#english)

---

<a id="deutsch"></a>

# 🇩🇪 Deutsch

Home-Assistant-Integration (HACS), die einen **Google-Kalender** und einen **iCloud-Kalender** (z. B. einen Familienkalender) in **beide Richtungen** synchron hält.

Die Integration bringt eigene Clients für Google und iCloud mit und ist unabhängig von den eingebauten Google- und CalDAV-Integrationen von Home Assistant.

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

> ⚠️ Ohne diesen Testnutzer-Eintrag bricht der Google-Login später mit **„Zugriff blockiert … Fehler 403: access_denied"** ab.

### 4.4 OAuth-Client anlegen

1. Links **Clients** → **+ Client erstellen**.
2. Anwendungstyp: **Webanwendung**, Name: `Home Assistant`.
3. **Autorisierte Weiterleitungs-URIs** → **+ URI hinzufügen**:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
4. **Erstellen** → **Client-ID** und **Clientschlüssel** kopieren.

> Hinweis: Solange die App im Status „Testing" ist, kann Google die Anmeldung nach einigen Tagen ablaufen lassen. Home Assistant meldet das dann, und du meldest dich einmal neu an.

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
   - Warnung „Google hat diese App nicht überprüft": **Erweitert** → **… aufrufen (unsicher)**. Das ist bei eigenen Testing-Apps normal.
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
- **Löschbremse** – ab wie vielen Löschungen pro Lauf um Freigabe gebeten wird (Standard 5, siehe unten).
- **Kalender wechseln** – Haken setzen → **OK** → im nächsten Schritt neue Kalender wählen.
  - Die Zuordnungen dieses Eintrags werden dabei geleert.
  - Der nächste Lauf verknüpft gleiche Termine neu und **löscht nichts**.
  - Der Name des Eintrags wird automatisch angepasst.

Ein Neu-Einrichten ist für diese Änderungen nicht nötig.

### Löschschutz

Seit v1.1 schützen mehrere Stufen davor, dass versehentlich viele Termine gelöscht werden:

| Schutz | Was passiert |
|---|---|
| **Zuordnung pro Eintrag** | Jeder Eintrag hat eine eigene Zuordnungsliste, gebunden an genau sein Kalenderpaar. Ein neuer oder geänderter Eintrag erbt nie fremde Zuordnungen. |
| **Erster Lauf** | Der erste Lauf eines Eintrags (oder nach einem Kalenderwechsel) verknüpft und legt an, löscht aber nie. |
| **Leerer Kalender** | Liefert eine Seite 0 Termine, obwohl mindestens 3 zugeordnet sind, bricht der Lauf ab, ohne etwas zu ändern. |
| **Löschbremse** | Würde ein Lauf mehr als 5 Termine (einstellbar) oder mehr als 20 % aller zugeordneten Termine löschen, wird **nichts** gelöscht. Anlegen und Ändern laufen normal weiter. |
| **Doppelt belegter Kalender** | Beim Einrichten erscheint eine Warnung, wenn ein Kalender schon von einem anderen Eintrag genutzt wird. Fortfahren nur mit Bestätigung. |

**Wenn die Löschbremse greift:**

1. Unter **Einstellungen → System → Reparaturen** erscheint „Calendar Sync: N Löschungen warten auf Freigabe“.
2. Anklicken → du siehst die Liste der betroffenen Termine.
3. Entscheiden:
   - **Löschen freigeben** – die Termine werden gelöscht (z. B. wenn du absichtlich viele Termine entfernt hast).
   - **Nicht löschen – fehlende Termine wiederherstellen** – die Termine bleiben und werden auf der Seite, auf der sie fehlen, neu angelegt.

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

1. **Zuerst Sync pausieren:** Konfigurieren → Haken „Synchronisation aktiv" entfernen.
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

> ⚠️ Gelöschte Termine sind weg. Google behält sie etwa 30 Tage im Papierkorb des Kalenders; iCloud kann Kalender über **icloud.com → Einstellungen → Kalender wiederherstellen** auf einen früheren Stand zurücksetzen. Den Probelauf deshalb nie überspringen.

---

## 10. So funktioniert der Sync

- **Zuordnungsliste:** Pro Eintrag eine SQLite-Datei unter `config/calendar_sync/<entry_id>.db`. Sie merkt sich, welcher Google-Termin zu welchem iCloud-Termin gehört, plus einen Prüfwert (Hash) des zuletzt synchronisierten Inhalts, und für welches Kalenderpaar die Zuordnungen gelten.
- **Löschungen werden erst geplant**, dann gegen den Löschschutz geprüft (siehe Kapitel 8) und erst danach ausgeführt.
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
| Google: „Zugriff blockiert … 403 access_denied" | Google-Adresse nicht als Testnutzer eingetragen | Schritt 4.3 Punkt 5 |
| „iCloud-Login fehlgeschlagen" | falsches oder widerrufenes app-spezifisches Passwort | neues Passwort erzeugen (Schritt 3) |
| `KeyError: 'auth_implementation'` | Eintrag aus einer Version vor 0.2 | Eintrag löschen und neu einrichten |
| „Sync fehlgeschlagen … 401" | iCloud-Passwort ungültig | neues app-spezifisches Passwort, Eintrag neu einrichten |
| Google-Anmeldung abgelaufen | OAuth-App im Status „Testing" | in HA neu anmelden |
| Termine doppelt | siehe Kapitel 9 | `calendar_sync.remove_duplicates` |
| Serientermin um 1 h verschoben (Sommer-/Winterzeit) | Version vor 0.3.5 | auf aktuelle Version aktualisieren |
| Reparatur „N Löschungen warten auf Freigabe“ | Löschbremse hat gegriffen | Liste prüfen, freigeben oder wiederherstellen (Kapitel 8) |
| „…-Kalender liefert 0 Termine, obwohl N zugeordnet sind“ | Abruffehler, falscher Kalender oder abgelaufene Anmeldung | Kalender in der App prüfen, ggf. neu anmelden. Wurde der Kalender absichtlich geleert: Sync pausieren, unter „Kalender wechseln“ neu wählen |
| Viele Termine versehentlich gelöscht | – | iCloud: icloud.com → Einstellungen → Kalender wiederherstellen. Google: Kalender → Papierkorb |

---

## 12. Grenzen

- Einzeln geänderte Termine einer Serie („diesen Montag 1 h später") werden nicht übertragen; ausgelassene Termine (EXDATE) schon.
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

[⬆ Nach oben](#calendar-2-way-sync--google--icloud)

---

<a id="english"></a>

# 🇬🇧 English

Home Assistant integration (HACS) that keeps a **Google calendar** and an **iCloud calendar** (e.g. a family calendar) in sync **both ways**.

The integration ships its own Google and iCloud clients and is independent of Home Assistant's built-in Google and CalDAV integrations.

## Contents

1. [What gets synced](#1-what-gets-synced)
2. [Requirements](#2-requirements)
3. [Prepare iCloud](#3-prepare-icloud)
4. [Prepare Google](#4-prepare-google)
5. [Install the integration](#5-install-the-integration)
6. [Configure the integration](#6-configure-the-integration)
7. [First sync – start safely](#7-first-sync--start-safely)
8. [Change settings (pause, interval, switch calendars)](#8-change-settings)
9. [Remove duplicates: `calendar_sync.remove_duplicates`](#9-remove-duplicates-calendar_syncremove_duplicates)
10. [How the sync works](#10-how-the-sync-works)
11. [Troubleshooting](#11-troubleshooting)
12. [Limitations](#12-limitations)
13. [Security](#13-security)

---

## 1. What gets synced

| Field | Google → iCloud | iCloud → Google |
|---|---|---|
| Title, location, description | ✅ | ✅ |
| Start, end, all-day | ✅ | ✅ |
| Recurring events (RRULE, RDATE, EXDATE) | ✅ | ✅ |
| Timezone (DST-safe) | ✅ | ✅ |
| Create / update / delete | ✅ | ✅ |
| Attendees, reminders, attachments, colors | ❌ | ❌ |
| Single modified instances of a series | ❌ | ❌ |

- **Conflict rule:** If an event was changed on both sides, the **most recently changed** side wins (last-write-wins).
- **Time window:** Events from **30 days in the past to 365 days in the future** are synced. Recurring events are picked up by their start date.
- **Interval:** Every 300 seconds (5 minutes) by default, configurable.

---

## 2. Requirements

- Home Assistant **2026.3 or newer** (for the icon; the integration itself runs on 2024.1+)
- [HACS](https://hacs.xyz/) installed
- An **Apple ID** with access to the iCloud calendar. For a shared family calendar, the Apple ID needs write permission.
- A **Google account** and a Google Cloud project (free, see below)

---

## 3. Prepare iCloud

iCloud has no official API. Access is done via **CalDAV** with an **app-specific password** – not your normal Apple password.

1. Open [account.apple.com](https://account.apple.com) and sign in.
2. **Sign-In and Security** → **App-Specific Passwords** → **+**.
3. Give it a name, e.g. `Home Assistant Calendar Sync`.
4. Note the displayed password (format `xxxx-xxxx-xxxx-xxxx`). It is shown only once.

You can revoke it at any time there. Only this access will stop working; your Apple account is not affected.

---

## 4. Prepare Google

Google only allows access to private calendars via **OAuth**. You need your own Google Cloud project for this, one-time. It is free; ignore offers for credits or trials.

### 4.1 Create a project

1. Open [console.cloud.google.com](https://console.cloud.google.com/).
2. Top left **Select project** → **New project**.
3. Name: e.g. `HA Calendar Sync`, Organization: **No organization** → **Create**.
4. Top left, **select** the new project. All following steps must happen inside this project.

### 4.2 Enable the Google Calendar API

1. Menu → **APIs & Services** → **Library**.
2. Search for `Google Calendar API` → open → **Enable**.

### 4.3 OAuth consent screen (Google Auth Platform)

1. Menu → **APIs & Services** → **OAuth consent screen** → **Get started**.
2. App name: e.g. `HA Calendar Sync`, support email: your address.
3. Audience: **External**.
4. Contact email: your address, accept the terms → **Create**.
5. Left menu **Audience** → **Test users** → **+ Add users** → enter **your Google address** → Save.

> ⚠️ Without this test user entry, the Google login will later fail with **"Access blocked … Error 403: access_denied"**.

### 4.4 Create an OAuth client

1. Left menu **Clients** → **+ Create client**.
2. Application type: **Web application**, name: `Home Assistant`.
3. **Authorized redirect URIs** → **+ Add URI**:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
4. **Create** → copy the **Client ID** and **Client Secret**.

> Note: While the app is in "Testing" status, Google may expire the login after a few days. Home Assistant will report this and you sign in once more.

---

## 5. Install the integration

1. HACS → top right **⋮** → **Custom repositories**.
2. URL `https://github.com/daloki83/ha-calendar-sync`, type **Integration** → **Add**.
3. Find **Calendar 2-way Sync – Google ↔ iCloud** → **Download**.
4. **Restart** Home Assistant.

---

## 6. Configure the integration

### 6.1 Add Google credentials to Home Assistant

1. **Settings** → **Devices & Services** → top right **⋮** → **Application Credentials**.
2. **+ Add Application Credential**:
   - Integration: **Calendar 2-way Sync – Google ↔ iCloud**
   - Name: anything
   - OAuth Client ID and Client Secret from step 4.4.

### 6.2 Add the integration

1. **Settings** → **Devices & Services** → **+ Add Integration** → **Calendar 2-way Sync – Google ↔ iCloud**.
2. **Google:** pick the credential → the Google login opens.
   - Warning "Google hasn't verified this app": **Advanced** → **Go to … (unsafe)**. This is normal for your own testing app.
   - Grant calendar access.
3. **iCloud:** Apple ID (email) and the app-specific password from step 3.
4. **Pick calendars:**
   - iCloud calendar (list)
   - Google calendar (list, ★ = primary)
   - Sync interval in seconds
   - **Enable synchronization** – leave **OFF** for the first time (see chapter 7)

The entry will then be named e.g. `Family ↔ Family Google`.

---

## 7. First sync – start safely

Especially with a **production** calendar (e.g. a family calendar):

1. Set up with **sync OFF**.
2. Optionally try with two empty **test calendars** first.
3. Then under **Configure**, tick **Sync enabled**.

On the first run the following happens:

- Events that already exist on **both** sides (same title, same time, same location, same description, same recurrence) are **linked, not copied**.
- Only events missing on one side are transferred.

The result shows up in the log (see [Troubleshooting](#11-troubleshooting)), e.g.:

```
Sync-Lauf: {'created_g': 0, 'created_i': 0, 'updated': 0, 'deleted': 0, 'matched': 21}
```

| Value | Meaning |
|---|---|
| `created_g` | newly created in Google |
| `created_i` | newly created in iCloud |
| `updated` | changed (last-write-wins) |
| `deleted` | deleted because deleted on the other side |
| `matched` | existing identical events linked |

---

## 8. Change settings

**Settings** → **Devices & Services** → **Calendar 2-way Sync – Google ↔ iCloud** → **⚙ (Configure)** on the entry:

- **Sync enabled** – pause or resume. When paused, nothing is read or written.
- **Sync interval in seconds**
- **Deletion brake** – above how many deletions per run approval is required (default 5, see below).
- **Change calendars** – tick → **OK** → pick new calendars in the next step.
  - This entry's mappings are cleared.
  - The next run re-links identical events and **deletes nothing**.
  - The entry's name is updated automatically.

Reinstalling the integration is not needed for these changes.

### Deletion protection

Since v1.1, several layers protect against accidentally deleting many events:

| Protection | What happens |
|---|---|
| **Mappings per entry** | Each entry has its own mapping list, bound to exactly its calendar pair. A new or changed entry never inherits someone else's mappings. |
| **First run** | The first run of an entry (or after a calendar switch) links and creates, but never deletes. |
| **Empty calendar** | If one side returns 0 events although at least 3 are mapped, the run aborts without changing anything. |
| **Deletion brake** | If a run would delete more than 5 events (configurable) or more than 20 % of all mapped events, **nothing** is deleted. Creating and updating keep working. |
| **Calendar used twice** | During setup, a warning appears if a calendar is already used by another entry. You can only continue after confirming. |

**When the deletion brake kicks in:**

1. Under **Settings → System → Repairs**, "Calendar Sync: N deletions awaiting approval" appears.
2. Click it → you see the list of affected events.
3. Decide:
   - **Approve deletion** – the events are deleted (e.g. if you intentionally removed many events).
   - **Don't delete – restore missing events** – the events stay and are re-created on the side where they are missing.

---

## 9. Remove duplicates: `calendar_sync.remove_duplicates`

### When do I need this?

- After a bug or version change, events show up **doubled**.
- Real-world example from development: before v0.4.5, a **calendar switch** copied every event to both sides even though they already existed there.

### What does the service do?

It searches **both** calendars for events that are **identical in content** (title, start, end, all-day, location, description, recurrence) and removes the extras:

- **iCloud:** Only copies created by the integration are deleted (UID ends with `@calendar-sync`). An identical original must remain. If a group contains only copies, exactly one is kept.
- **Google:** Copies created by the integration are deleted first (marked invisibly from v0.4.5 or identifiable through the mapping list). If the origin is unknown, exactly **one** of identical events is kept.
- Events that differ in any field are **never** touched.

### How to call it

Only **administrators** may run the service.

1. **Pause sync first:** Configure → remove the "Sync enabled" tick.
2. **Developer Tools** → **Actions** → `calendar_sync.remove_duplicates`.
3. **Dry run** (deletes nothing, just reports):
   ```yaml
   action: calendar_sync.remove_duplicates
   data:
     dry_run: true
   ```
   **Perform action** → the response shows below:
   ```yaml
   01M5M336...:
     dry_run: true
     google_count: 0
     icloud_count: 38
     icloud:
       - "Pia Birthday @ 2017-06-26T00:00:00+00:00"
       - "[P] English test @ 2026-09-28T08:00:00+02:00"
       ...
     google_similar_groups: 0
   ```
   - `google_count` / `icloud_count`: this many events **would** be deleted.
   - `google_similar`: events with the same title and start that still differ (e.g. different description). These are **not** deleted – shown for manual review.
4. Review the list. If it is correct, **run for real**:
   ```yaml
   action: calendar_sync.remove_duplicates
   data:
     dry_run: false
   ```
5. **Verify:** another dry run – both counts should be `0`.
6. Check the calendar in the Apple and Google apps.
7. **Re-enable sync.** The next run links the remaining events (`matched`).

> ⚠️ Deleted events are gone. Google keeps them in the calendar's trash for about 30 days; iCloud can restore calendars to an earlier state via **icloud.com → Settings → Restore calendars**. Never skip the dry run.

---

## 10. How the sync works

- **Mapping list:** One SQLite file per entry at `config/calendar_sync/<entry_id>.db`. It remembers which Google event matches which iCloud event, a checksum (hash) of the last synced content, and which calendar pair the mappings belong to.
- **Deletions are planned first**, checked against the deletion protection (see chapter 8), and only then executed.
- **Change detection:** On every run, both sides are read and hashes compared. Times are normalized to UTC and recurrence rules canonicalized – so different notations by Google and Apple do not produce fake changes.
- **Deletions:** If an already-linked event is missing on one side, it is also deleted on the other.
- **Origin marker:** Copies created in iCloud have a UID with `@calendar-sync`; copies created in Google have an invisible property `calendar_sync=1`.
- **Removing the entry** also deletes the mapping list. The calendars themselves stay unchanged.

---

## 11. Troubleshooting

**View logs:** Settings → System → Logs → filter for `calendar_sync`.
For per-event detail: Integration → **⋮** → **Enable debug logging**.

| Message / Symptom | Cause | Fix |
|---|---|---|
| Google: "Access blocked … 403 access_denied" | Google address not added as a test user | Step 4.3 point 5 |
| "iCloud login failed" | Wrong or revoked app-specific password | Create a new password (step 3) |
| `KeyError: 'auth_implementation'` | Entry from a pre-0.2 version | Delete the entry and set it up again |
| "Sync failed … 401" | iCloud password invalid | New app-specific password, re-add the entry |
| Google login expired | OAuth app in "Testing" status | Sign in again in HA |
| Duplicate events | See chapter 9 | `calendar_sync.remove_duplicates` |
| Recurring event shifted by 1 h (DST) | Version before 0.3.5 | Update to the current version |
| Repair "N deletions awaiting approval" | Deletion brake kicked in | Review the list, approve or restore (chapter 8) |
| "…calendar returns 0 events although N are mapped" | Fetch error, wrong calendar, or expired login | Check the calendar in the app, sign in again if needed. If you emptied the calendar on purpose: pause sync, re-select under "Change calendars" |
| Many events deleted by accident | – | iCloud: icloud.com → Settings → Restore calendars. Google: Calendar → Trash |

---

## 12. Limitations

- Single modified instances of a series ("this Monday 1 h later") are not transferred; skipped instances (EXDATE) are.
- Attendees, reminders, attachments and colors are not synced.
- The integration polls (default every 5 minutes); no real-time push.
- iCloud CalDAV is not officially documented; Apple can change the behavior.
- One entry syncs exactly one pair of calendars. For more pairs, add more entries.

---

## 13. Security

See [SECURITY.md](SECURITY.md). Short version:

- Never use the Apple ID password, only **app-specific passwords**.
- Credentials are stored – like with every HA integration – in `config/.storage/core.config_entries`. Protect your Home Assistant backups accordingly.
- Google access can be revoked at any time at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## License

MIT

[⬆ Back to top](#calendar-2-way-sync--google--icloud)

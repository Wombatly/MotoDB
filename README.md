# MotoDB

[![CI](https://github.com/Wombatly/MotoDB/actions/workflows/ci.yml/badge.svg)](https://github.com/Wombatly/MotoDB/actions/workflows/ci.yml)

MotoDB ist eine Flask-Webanwendung zur Verwaltung von Motorrädern,
Serviceeinträgen, technischen Daten, Checklisten, Dokumenten und Belegen. Das
Projekt ist auf den privaten Werkstatt- und Fuhrparkbetrieb ausgelegt:
Motorräder können erfasst, Wartungen dokumentiert, Checklisten gepflegt und
Serviceeinträge auch offline vorbereitet werden.

Die Anwendung läuft lokal standardmäßig auf Port `5001` und kann für den
Betrieb auf einem Raspberry Pi per Docker und Nginx bereitgestellt werden.

## Inhalt

- [Funktionsumfang](#funktionsumfang)
- [Technik-Stack](#technik-stack)
- [Projektstruktur](#projektstruktur)
- [Lokale Entwicklung](#lokale-entwicklung)
- [Konfiguration](#konfiguration)
- [Datenhaltung](#datenhaltung)
- [Benutzeroberfläche](#benutzeroberfläche)
- [Checklisten](#checklisten)
- [Technische Daten](#technische-daten)
- [Dokumente](#dokumente)
- [Offline-Sync](#offline-sync)
- [API-Endpunkte](#api-endpunkte)
- [Uploads und Belege](#uploads-und-belege)
- [Backups](#backups)
- [Docker und Raspberry-Pi-Deployment](#docker-und-raspberry-pi-deployment)
- [Wartung und Fehlersuche](#wartung-und-fehlersuche)
- [Lizenz](#lizenz)

## Funktionsumfang

### Motorradverwaltung

- Motorräder mit Marke, Modell, Baujahr, Kilometerstand, Kaufdaten,
  Zulassung, Kennzeichen, VIN, Farbe, Hubraum, Leistung und Notizen anlegen.
- Motorräder bearbeiten und löschen.
- Motorradbilder hochladen und entfernen; mehrere Bilder pro Motorrad mit
  Titelbild-Auswahl und Galerie-Ansicht.
- Kauf- und Verkaufsdaten (Datum, Preis) erfassen.
- Automatische Aktualisierung des Kilometerstands anhand der neuesten
  Service- oder Checklistenhistorie.

### Service- und Kostenhistorie

- Serviceeinträge pro Motorrad erfassen.
- Kategorien wie Wartung, Ersatzteile, Reifen, Versicherung, Steuer, TÜV/HU,
  Kraftstoff, Zubehör, Reparatur und Sonstiges verwenden.
- Datum, Kilometerstand, Beschreibung, Kosten, nächste Service-Kilometer und
  nächste Service-Termine speichern.
- Belege hochladen und dem Serviceeintrag zuordnen.

### Technische Daten

- Technische Spezifikationen pro Motorrad erfassen.
- Daten nach Kategorien wie Motor, Antrieb, Fahrwerk, Bremsen, Reifen, Maße
  und Elektrik strukturieren.
- Werte, Einheiten und Quellen dokumentieren.
- Daten per CSV einlesen oder direkt im Datenblatt inline pflegen.
- CSV-Vorlage für technische Daten herunterladen.
- Einträge und Kategorien per Drag & Drop neu anordnen; Reihenfolge wird
  serverseitig gespeichert.

### Service-Checklisten

- Checklisten als Vorlagen erstellen.
- Vorgefertigte Presets nutzen, zum Beispiel:
  - 1.000 km Einfahrkontrolle
  - 10.000 km Service
  - 20.000 km großer Service
  - Saisoncheck
- Checklistenpunkte mit Kommentaren und Hinweisen pflegen.
- Punktelisten über eine eigene Importseite einlesen.
- Checklisten als erledigte Wartungsnachweise speichern.
- Erledigte Punkte und Anmerkungen pro Durchführung erfassen.

### Dokumente

- Beliebige Dateien (PDF, Bilder, Belege) pro Motorrad speichern.
- Kategorisierung und Benennung über die Upload-Seite.
- Dokumente über den Reiter „Dokumente" in der Motorrad-Detailansicht
  einsehen und löschen.

### Offline-Unterstützung

- Serviceformulare können offline im Browser gespeichert werden.
- Offline-Daten landen in IndexedDB, gebunden an das angemeldete Konto.
- Über den Sync-Button werden offene Einträge später an den Server übertragen;
  nur vom Server bestätigte Einträge werden lokal entfernt.

### PWA-Grundlagen

- Webmanifest unter `/manifest.webmanifest`.
- Service Worker unter `/service-worker.js`.
- App-ähnliche Nutzung auf mobilen Geräten möglich.

## Technik-Stack

- Python 3.12
- Flask 3
- Flask-SQLAlchemy
- SQLite
- Pillow für Bildoptimierung
- fpdf2 für PDF-Erstellung (Backup-Zusammenfassung)
- Gunicorn für Containerbetrieb
- Docker für Deployment
- Nginx als Reverse Proxy auf dem Raspberry Pi
- Vanilla JavaScript für Menü, Offline-Speicher und Sync
- IndexedDB für lokale Offline-Wartungseinträge

Die Python-Abhängigkeiten stehen in `requirements.txt`:

```txt
Flask==3.1.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.3.0
Pillow==12.2.0
pypdf==6.13.2
fpdf2==2.8.7
gunicorn==26.0.0
Werkzeug==3.1.8
```

## Projektstruktur

```text
.
├── app/
│   ├── __init__.py              # Flask-App-Factory, Datenbank, Schema-Migrationen, Startup-Sperre
│   ├── models.py                # SQLAlchemy-Modelle
│   ├── routes.py                # Views, API, Import, Sync, Backup, Hilfslogik
│   ├── auth.py                  # Login/Registrierung, Rate-Limit, Admin, ZIP-Export
│   ├── export_pdf.py            # PDF-Zusammenfassung pro Motorrad (ZIP-Export)
│   ├── help_content.py          # Hilfetexte (?-Button und /hilfe)
│   ├── timeutils.py             # utcnow() als naives UTC-datetime
│   ├── utils.py                 # Parser, Uploads, Presets, Konstanten
│   ├── static/
│   │   ├── css/app.css          # Styling (Themes über CSS-Variablen, @font-face)
│   │   ├── fonts/               # IBM Plex Sans/Mono (WOFF2, OFL-Lizenz) für das Logbuch-Theme
│   │   ├── js/app.js            # UI-Verhalten (Tabs, Drag&Drop, Galerie, Datenblatt)
│   │   ├── js/help.js           # Hilfe-Panel
│   │   ├── js/theme.js          # Farbschema-Umschaltung (localStorage)
│   │   ├── js/indexeddb.js      # Offline-Datenbank im Browser
│   │   ├── js/sync.js           # Sync-Logik
│   │   ├── manifest.webmanifest # PWA-Manifest
│   │   └── service-worker.js    # Service Worker
│   └── templates/
│       ├── base.html
│       ├── _macros.html         # Wiederverwendbare Jinja-Makros
│       ├── help.html            # Übersicht aller Hilfethemen
│       ├── privacy.html         # Datenschutzhinweise
│       ├── settings.html        # Profil / Einstellungen
│       ├── admin/               # Nutzerverwaltung
│       ├── auth/                # Login, Registrierung, Passwort, Konto löschen
│       ├── motorcycles/
│       │   ├── detail.html      # Tabs: Historie / Datenblatt / Dokumente
│       │   └── ...
│       ├── service/
│       ├── checklists/
│       └── documents/
│           └── form.html        # Dokumentenupload-Seite
├── deploy/
│   ├── README_RASPI.md          # Raspberry-Pi-Anleitung
│   ├── UPDATE_RASPI.md          # Update-Ablauf auf dem Pi
│   ├── nginx/
│   └── update-on-pi.sh
├── instance/                    # lokale Laufzeitdaten (nicht im Repo)
│   ├── motorcycle_service.sqlite3
│   └── uploads/
├── tests/
│   ├── __init__.py
│   ├── test_security.py
│   └── test_input_validation.py
├── .github/workflows/ci.yml     # GitHub Actions: pyflakes, Tests, Docker-Build
├── AUDIT_REPORT.md              # Letzter Audit-Stand (behoben / offen)
├── LICENSE                      # MIT
├── .env.example
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── run.py
└── start_handytest.command
```

Der Ordner `instance/` enthält lokale Laufzeitdaten. Dazu gehören die
SQLite-Datenbank, hochgeladene Bilder und Belege. Diese Daten sollten bei
Deployments und Backups besonders geschützt werden.

## Lokale Entwicklung

### Voraussetzungen

- Python 3.12
- `pip`
- Optional: virtuelles Environment

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### App starten

```bash
python3 run.py
```

Danach ist die App unter dieser Adresse erreichbar:

```text
http://127.0.0.1:5001
```

Wichtig: Die HTML-Dateien in `app/templates/` sind Jinja-Templates und sollten
nicht direkt im Browser geöffnet werden. Die Anwendung muss über Flask laufen,
damit Routing, Datenbankzugriff, statische Dateien und Template-Rendering
funktionieren.

### Alternative: Start per Command-Datei

Auf macOS kann auch diese Datei gestartet werden:

```bash
./start_handytest.command
```

Sie wechselt in den Projektordner und führt `python3 run.py` aus.

## Konfiguration

Die Anwendung liest mehrere Einstellungen aus Umgebungsvariablen.

| Variable | Zweck | Standard |
| --- | --- | --- |
| `SECRET_KEY` | Flask Secret Key für Sessions und Sicherheit | `dev-change-me` |
| `DATABASE_URL` | SQLAlchemy-Datenbank-URL | `sqlite:///motorcycle_service.sqlite3` |
| `MOTORRAD_INSTANCE_PATH` | Pfad für Flask-Instance-Daten | Flask-Default `instance/` |
| `MOTORRAD_UPLOAD_FOLDER` | Upload-Ziel für Bilder und Belege | `<instance>/uploads` |
| `MOTODB_PUBLIC_HOSTING` | Aktiviert HTTPS-Cookies, HSTS und Public-Hosting-Checks | `false` |
| `MOTODB_TRUST_PROXY_HEADERS` | Vertraut genau einem vorgeschalteten Reverse Proxy | `false` |
| `MOTODB_ALLOW_REGISTRATION` | Erlaubt Selbstregistrierung | lokal `true`, öffentlich `false` |
| `MOTODB_ADMIN_USERNAME` | Benutzername für den ersten Admin einer neuen DB | leer |
| `MOTODB_ADMIN_EMAIL` | Email für den ersten Admin einer neuen DB | leer |
| `MOTODB_ADMIN_PASSWORD` | Passwort für den ersten Admin einer neuen DB | leer |
| `MOTODB_MAX_STORAGE_MB` | Upload-Speicherlimit pro Konto in MB | `500` |
| `MOTODB_CONTROLLER_NAME` | Verantwortlicher auf der Datenschutzseite | `Betreiber dieser MotoDB-Installation` |
| `MOTODB_CONTROLLER_CONTACT` | Kontakt auf der Datenschutzseite | `ueber den Administrator dieser Installation` |

Eine Beispielkonfiguration liegt in `.env.example`:

```env
SECRET_KEY=bitte-durch-einen-langen-zufaelligen-wert-ersetzen
```

Im lokalen Entwicklungsmodus ist die Standardkonfiguration ausreichend. Für
Produktivbetrieb muss `SECRET_KEY` immer durch einen langen zufälligen Wert
ersetzt werden.

Im lokalen Modus legt eine leere Datenbank weiterhin den Entwicklungsadmin
`admin@localhost` mit Passwort `change-me-please` an. Mit
`MOTODB_PUBLIC_HOSTING=true` startet die App nicht mit diesem bekannten
Passwort. Für eine neue öffentliche Datenbank wird der erste Admin stattdessen
einmalig über `MOTODB_ADMIN_USERNAME`, `MOTODB_ADMIN_EMAIL` und
`MOTODB_ADMIN_PASSWORD` erzeugt. Das Bootstrap-Passwort muss mindestens 12
Zeichen lang sein.

Hinweis zu `MOTODB_TRUST_PROXY_HEADERS`: Hinter einem Reverse Proxy (Nginx)
sieht die App ohne diese Einstellung alle Anfragen von `127.0.0.1`. Das
IP-basierte Login-Rate-Limit wird dann automatisch deaktiviert (es bleibt das
Limit pro E-Mail), und beim Start erscheint eine Warnung im Log. Den Wert
deshalb immer setzen, wenn ein Proxy davor steht – und den App-Port dann nie
direkt exponieren.

## Datenhaltung

Die Datenbank wird über SQLAlchemy verwaltet. Beim Start erstellt die App die
Tabellen automatisch, falls sie fehlen. Zusätzlich führt `ensure_schema_updates`
kleine Schema-Nachziehungen für bestehende Datenbanken aus (ALTER TABLE,
Backfill-Queries), damit alte Instanzen ohne Datenverlust aktualisiert werden
können.

### Hauptmodelle

#### `Motorcycle`

Speichert Stammdaten zu einem Motorrad:

- Marke und Modell
- Baujahr und Kilometerstand
- Kaufpreis, Kaufdatum, Verkaufspreis und Verkaufsdatum
- Hubraum, PS, Farbe
- Kennzeichen, VIN, Erstzulassung
- Notizen
- Bildpfad (Titelbild; Galerie über `MotorcycleImage`)

Verknüpfungen: `services`, `technical_specs`, `checklists`, `images`,
`documents`

#### `MotorcycleImage`

Speichert einzelne Bilder eines Motorrads:

- `path` — relativer Pfad unterhalb des Upload-Ordners
- `original_name`
- `position` — Sortierreihenfolge in der Galerie
- `created_at`

#### `MotorcycleDocument`

Speichert Dokumente (PDF, Bilder, Belege) zu einem Motorrad:

- `titel` — frei wählbarer Name
- `kategorie`
- `path` — relativer Pfad unterhalb des Upload-Ordners
- `original_name`
- `created_at`, `updated_at`

#### `ServiceEntry`

Speichert Wartungs-, Kosten- und Ereigniseinträge:

- Titel, Datum, Kilometerstand, Beschreibung, Kosten, Kategorie
- Belegpfad und Originalname
- nächste Service-Kilometer und nächstes Service-Datum

#### `TechnicalSpec`

Speichert technische Daten pro Motorrad:

- Name, Wert, Einheit, Kategorie, Quelle
- `position` — Sortierreihenfolge innerhalb der Kategorie; wird per
  Drag & Drop in der Detailansicht verändert

#### `ServiceChecklist`

Speichert Checklisten. Eine Checkliste kann entweder Vorlage oder erledigter
Nachweis sein.

Wichtige Felder:

- Titel, Intervall in Kilometern, Intervall in Monaten
- Datum, Kilometerstand, Anmerkungen
- `is_template`, `source_template_id`, `completed_at`

#### `ServiceChecklistItem`

Speichert einzelne Prüfpunkte einer Checkliste:

- Position, Text, Kommentarvorlage
- `erledigt`, Anmerkung

#### `AppSetting`

Speichert einfache Schlüssel-Wert-Einstellungen. Aktuell wird vor allem der
Backup-Pfad unter dem Schlüssel `backup_path` verwendet.

## Benutzeroberfläche

Die Anwendung rendert serverseitig mit Jinja2-Templates. Das Grundlayout liegt
in `app/templates/base.html`; gemeinsame Makros (Seitenkopf,
Motorrad-Selektor) sind in `app/templates/_macros.html` definiert.

### Farbschema

Die App startet standardmäßig im Dark-Theme „Nachtschicht". Das Farbschema
kann in den Einstellungen gewählt werden:

- **Nachtschicht** — dunkles Theme (Standard)
- **Hell** — helles Theme
- **Werkstatt-Logbuch** — helles Papier-Theme mit IBM Plex Sans/Mono
- **System** — folgt dem Betriebssystem-Modus (`prefers-color-scheme`)

Die Auswahl wird in `localStorage` unter dem Schlüssel `motodb-theme`
gespeichert und beim nächsten Seitenaufruf sofort angewandt, bevor das erste
Pixel gerendert wird (`app/static/js/theme.js`). Das CSS nutzt CSS-Variablen
(`--page`, `--surface`, `--text`, …); die Themes überschreiben diese über
`[data-theme="light"]` bzw. `[data-theme="logbuch"]` auf dem `<html>`-Element.
Die Schriften des Logbuch-Themes liegen als WOFF2 unter `app/static/fonts/`
(SIL Open Font License) und werden selbst ausgeliefert – es gibt keinen
externen Font-Abruf.

**Wichtig für Entwicklung:** Die Content-Security-Policy (`script-src 'self'`
und `style-src 'self'`) lässt keine Inline-`<script>`-Tags und keine
`style=""`-Attribute zu. Neue JS-Logik gehört immer in externe `.js`-Dateien,
neue Styles in `app.css`.

### Navigation

Die Fußleiste enthält drei Einträge:

- **Übersicht** — Motorradliste
- **+** (FAB) — neues Motorrad anlegen
- **Profil** — Einstellungen / Konto

### Motorrad-Detailansicht

Die Detailseite (`/motorrad/<id>`) ist in drei Reiter aufgeteilt:

| Reiter | Inhalt |
| --- | --- |
| **Historie** | Chronologische Liste aller Services und abgeschlossenen Checklisten |
| **Datenblatt** | Technische Daten; inline editierbar; Kategorien und Einträge per Drag & Drop sortierbar |
| **Dokumente** | Hochgeladene Dokumente; Direktlink zur Upload-Seite |

### Einstellungen

Die Einstellungsseite (`/einstellungen`) ist in Gruppen unterteilt:

- **Darstellung** — Farbschema-Umschalter
- **Konto** — Passwort ändern, Abmelden; Admin: Nutzerverwaltung
- **Daten und Backup** — Speicherbelegung, ZIP-Export („Backup herunterladen“);
  Admin: Sicherungsort und „Backup jetzt erstellen“
- **Vorlagen und Import** — CSV-Vorlage und Import für Checklisten und
  Datenblatt
- **Gefahrenzone** — Konto samt aller Daten löschen

## Checklisten

Checklisten können direkt in der Anwendung, über Presets oder per CSV angelegt
werden.

Punktelisten können über eigene Importseiten hochgeladen werden:

```text
/checklisten/import
/motorrad/<id>/checklisten/import
```

### Presets

Die Presets stehen in `app/utils.py` unter `SERVICE_CHECKLIST_PRESETS`.

Vorhandene Presets:

- `1000`: 1.000 km Einfahrkontrolle
- `10000`: 10.000 km Service
- `20000`: 20.000 km großer Service
- `season`: Saisoncheck

### CSV-Vorlage

Die Checklisten-Vorlage kann unter `Einstellungen → Vorlagen und Import` oder
direkt über diese Route heruntergeladen werden:

```text
/checklisten/csv-vorlage
```

### CSV-Format für Checklisten

Die Anwendung erkennt Semikolon- und Komma-getrennte CSV-Dateien. Empfohlen ist
dieses Format:

```csv
Motorrad;Titel;km;Intervall;Position;Pruefpunkt;Kommentar
BMW R 1250 GS;Jahresservice;10000;12;1;Oelstand pruefen;Motor warmfahren und auf ebenem Untergrund pruefen
BMW R 1250 GS;Jahresservice;10000;12;2;Bremsbelaege pruefen;Vorne und hinten Sichtpruefung durchfuehren
BMW R 1250 GS;Jahresservice;10000;12;3;Reifendruck pruefen;Herstellerangaben beachten
```

Erkannte Spaltennamen:

- `Motorrad` oder `Motorcycle`
- `MotorradID` oder `MotorcycleID`
- `Titel` oder `Title`
- `km` oder `IntervallKm`
- `Intervall` oder `Monate`
- `Position` oder `Pos`
- `Pruefpunkt`, `Prüfpunkt`, `Punkt` oder `Item`
- `Kommentar` oder `Comment`

Damit ein CSV-Eintrag importiert wird, müssen mindestens Titel und Prüfpunkt
vorhanden sein. Das zugehörige Motorrad wird entweder über die ID oder über den
Namen gesucht.

### Checkliste durchführen

Eine Vorlage wird beim Durchführen nicht überschrieben. Stattdessen erzeugt die
App einen neuen `ServiceChecklist`-Datensatz mit `is_template=False`. Dadurch
bleibt die Vorlage wiederverwendbar, während die Durchführung mit Datum,
Kilometerstand, erledigten Punkten und Anmerkungen dokumentiert wird.

## Technische Daten

Technische Daten können pro Motorrad gepflegt werden. Es gibt globale und
fahrzeugbezogene Einstiege:

```text
/technik
/motorrad/<id>/technik
```

Im Reiter **Datenblatt** der Motorrad-Detailansicht können die Werte direkt
inline bearbeitet werden (Autosave). Die Reihenfolge von Kategorien und
Einträgen innerhalb einer Kategorie lässt sich per Drag & Drop verändern; die
neue Reihenfolge wird sofort an den Server gesendet
(`POST /motorrad/<id>/datenblatt/reihenfolge`).

### CSV-Vorlage

Die Route `/technik/csv-vorlage` liefert ein ZIP mit `datenblatt.csv` und
einer README:

```csv
Kategorie;Eintrag;Wert;Einheit
Motor;Hubraum;583;ccm
Motor;Leistung;50;PS
Motor;Drehmoment;53;Nm
Antrieb;Getriebe;5-Gang;
Reifen;Reifen vorne;90/90-21;
Reifen;Reifen hinten;130/80-17;
```

Eine optionale fünfte Spalte `Quelle` (z. B. `Fahrzeugschein`) wird beim
Import ebenfalls übernommen. Semikolon oder Komma als Trennzeichen werden
automatisch erkannt.

Beim Speichern ersetzt die App die bisherigen technischen Daten des jeweiligen
Motorrads durch die neu zusammengeführten Zeilen (gleiche Namen werden
zusammengefasst, der letzte Wert gewinnt).

## Dokumente

Dokumente werden pro Motorrad über den Reiter **Dokumente** der
Motorrad-Detailansicht („Dokument hinzufügen“) oder direkt über diese Route
hochgeladen:

```text
/motorrad/<id>/dokumente/neu
```

Auf der Upload-Seite können Titel, Kategorie und Datei angegeben werden. Die
Datei wird im Upload-Ordner unter `<motorrad_id>/documents/` abgelegt.

Vorhandene Dokumente werden im Reiter **Dokumente** der Motorrad-Detailansicht
aufgelistet und können dort geöffnet oder gelöscht werden.

## Offline-Sync

Die Offline-Funktion nutzt IndexedDB im Browser. Die Logik ist aufgeteilt in:

- `app/static/js/indexeddb.js`: lokale Browserdatenbank
- `app/static/js/sync.js`: Speichern und Synchronisieren

Offline gespeicherte freie Serviceeinträge landen im Object Store
`pendingServices`.

Offline gespeicherte Checklisten-Serviceeinträge landen im Object Store
`pendingChecklistServices`.

Jeder Offline-Eintrag wird mit der ID des angemeldeten Nutzers gespeichert.
Der Sync sendet nur Einträge des aktuell angemeldeten Kontos; Einträge anderer
Konten im selben Browser bleiben liegen, bis sich deren Besitzer anmeldet.

Beim Klick auf `Sync` sendet der Browser die offenen Daten an:

```text
POST /api/sync
```

Der Server bestätigt jeden Eintrag einzeln (`accepted`/`rejected`, siehe
API-Endpunkte). Nur bestätigte Einträge werden aus IndexedDB gelöscht.
Abgelehnte Einträge (z. B. gelöschtes Motorrad, ungültiges Datum) bleiben
markiert erhalten: der automatische Sync überspringt sie, beim manuellen Sync
fragt die App, ob sie verworfen werden sollen.

Wenn der Browser wieder online geht, versucht die App automatisch eine
Synchronisierung.

## API-Endpunkte

Die Anwendung bietet einige JSON-Endpunkte für Offline- und Sync-Funktionen.

### Motorräder abrufen

```http
GET /api/motorcycles
```

Antwort:

```json
[
  {
    "id": 1,
    "marke": "BMW",
    "modell": "R 1250 GS",
    "baujahr": 2020,
    "kilometerstand": 25000,
    "updated_at": "2026-05-19T12:00:00"
  }
]
```

### Services eines Motorrads abrufen

```http
GET /api/motorcycles/<motorrad_id>/services
```

Antwort:

```json
[
  {
    "id": 10,
    "motorrad_id": 1,
    "titel": "Jahresservice",
    "datum": "2026-05-19",
    "kilometerstand": 25000,
    "beschreibung": "Oel und Filter gewechselt",
    "kosten": 180,
    "kategorie": "Wartung / Service",
    "updated_at": "2026-05-19T12:00:00"
  }
]
```

### Service per API anlegen

```http
POST /api/services
Content-Type: application/json
```

Beispiel:

```json
{
  "motorrad_id": 1,
  "titel": "Reifenwechsel",
  "datum": "2026-05-19",
  "kilometerstand": "25000",
  "beschreibung": "Neue Reifen montiert",
  "kosten": "320",
  "kategorie": "Reifen",
  "naechster_service_km": "30000",
  "naechster_service_datum": "2027-05-19"
}
```

### Offline-Daten synchronisieren

```http
POST /api/sync
Content-Type: application/json
```

Payload:

```json
{
  "services": [],
  "checklist_services": []
}
```

Antwort:

```json
{
  "created": [],
  "checklist_services": [],
  "accepted": { "services": [0], "checklist_services": [] },
  "rejected": { "services": [1], "checklist_services": [] }
}
```

`accepted` und `rejected` enthalten die Indizes der gesendeten Listen. Ein
Eintrag wird abgelehnt, wenn das Motorrad nicht dem angemeldeten Nutzer gehört,
die Checklisten-Vorlage nicht zum Motorrad passt oder ein Datum nicht im Format
`YYYY-MM-DD` vorliegt. Ungültige Bodies (kein JSON-Objekt) liefern `400`.

## Uploads und Belege

Uploads werden unterhalb des konfigurierten Upload-Ordners gespeichert. Lokal
ist das standardmäßig:

```text
instance/uploads/
```

Die Pfade sind pro Motorrad organisiert:

```text
instance/uploads/<motorrad_id>/images/
instance/uploads/<motorrad_id>/receipts/
instance/uploads/<motorrad_id>/documents/
```

Für Bilder wird Pillow verwendet. Beim Upload werden Bilder:

- anhand der EXIF-Orientierung ausgerichtet,
- auf maximal `1600 x 1200` verkleinert,
- als `.jpg` mit Qualität `82` gespeichert,
- progressiv und optimiert geschrieben.

Belege werden als Datei gespeichert und mit dem Originalnamen im
Serviceeintrag referenziert. Bildbelege werden ebenfalls als `.jpg`
normalisiert. Uploads sind auf maximal `32 MB` begrenzt.

## Backups

Der Backup-Pfad wird in der App unter `Einstellungen → Daten und Backup`
gepflegt. Intern liegt er als `AppSetting` mit dem Schlüssel `backup_path`
in der Datenbank.

Admins können unter `Einstellungen → Daten und Backup` mit **Backup jetzt
erstellen** einen Sicherungsordner im hinterlegten Pfad anlegen
(`POST /settings/backup`):

```text
motorrad_service_backup_<YYYYMMDD_HHMMSS>/
├── motorcycle_service.sqlite3   # konsistente Kopie über die SQLite-Backup-API
└── uploads/                     # kompletter Upload-Ordner
```

Der Offline-Sync erstellt kein Backup mehr.

### Manuelles Backup (ZIP-Download)

Über `Einstellungen → Daten und Backup` kann ein ZIP-Archiv heruntergeladen
werden. Es enthält für jedes Motorrad einen eigenen Unterordner mit:

- `daten.json` — vollständige Daten des Motorrads im JSON-Format
- `zusammenfassung.pdf` — lesbare PDF-Zusammenfassung mit:
  - Titelbild des Motorrads (wenn vorhanden)
  - Seite 1: Fahrzeugdaten (Stammdaten, Kaufpreis, Kennzeichen usw.)
  - Seite 2: Technische Daten in zweispaltigem Raster pro Kategorie
  - Seite 3: Servicehistorie (alle Services und abgeschlossene Checklisten)
- `profil.json` — Nutzerprofil

Zusätzlich liegen alle hochgeladenen Bilder, Belege und Dokumente im Archiv.

Die PDF wird von `app/export_pdf.py` erzeugt. Technische Grundlage ist
`fpdf2` (Version siehe `requirements.txt`) mit den Kernschriften, daher
latin-1-Zeichensatz; Sonderzeichen wie `€` werden ersetzt.

Auf dem Raspberry Pi ist als Backup-Pfad vorgesehen:

```text
/data/backups
```

Im Host-Dateisystem entspricht das:

```text
/srv/motorrad-service/data/backups
```

## Docker und Raspberry-Pi-Deployment

Das Projekt enthält einen `Dockerfile` und eine `compose.yaml`.

### Container bauen und starten

```bash
docker compose up -d --build
```

Die App wird im Container mit Gunicorn gestartet:

```text
gunicorn --bind 0.0.0.0:5001 --workers 2 --threads 4 --timeout 120 run:app
```

### Compose-Konfiguration

Die Compose-Datei bindet den Dienst lokal auf Port `5001`:

```yaml
ports:
  - "127.0.0.1:5001:5001"
```

Die persistenten Daten liegen im Produktivbetrieb unter:

```text
/srv/motorrad-service/data
```

Im Container wird dieser Pfad als `/data` eingebunden. Dadurch liegen
Datenbank, Uploads und Backups außerhalb des Containers und bleiben bei
Updates erhalten.

### Nicht-Root, Healthcheck und Test-Stage

Der Container läuft als Benutzer `motodb` mit UID/GID `1000` (per Build-Arg
`APP_UID`/`APP_GID` änderbar). Das Daten-Volume muss dieser UID gehören –
einmalig auf dem Host, ohne `sudo`:

```bash
docker run --rm -v /srv/motorrad-service/data:/data alpine chown -R 1000:1000 /data
```

`HEALTHCHECK` ruft alle 30 s `GET /health` auf; die Route antwortet ohne
Login mit `{"status": "ok"}` und prüft dabei die Datenbankverbindung
(`503`, wenn sie fehlschlägt). `docker ps` zeigt den Zustand als
`healthy`/`unhealthy`.

Das Dockerfile ist mehrstufig. Die Stage `test` führt `pyflakes` und alle
Unit-Tests im Image aus (die Runtime-Stage enthält keine Tests):

```bash
docker build --target test .
```

### Continuous Integration

`.github/workflows/ci.yml` läuft bei jedem Push auf `main` und bei Pull
Requests: `pyflakes` + Unit-Tests unter Python 3.12, danach Docker-Build der
Test-Stage und des Runtime-Images inklusive Start als Nicht-Root und Warten
auf `healthy`.

### Raspberry Pi

Eine ausführliche Deployment-Anleitung steht in:

```text
deploy/README_RASPI.md
```

Darin beschrieben sind:

- Debian-Grundinstallation
- Docker-Installation
- Verzeichnisstruktur unter `/srv/motorrad-service`
- Kopieren per `rsync`
- Migration vorhandener Daten
- `.env` auf dem Pi
- Docker-Start
- Nginx-Konfiguration
- Firewall
- Backup-Pfad
- Update-Ablauf

### Öffentliches Hosting

Für einen öffentlichen HTTPS-Zugang sollte die App weiter hinter Gunicorn und
einem Reverse Proxy laufen. Vor dem Start der öffentlichen Instanz:

1. `.env` mit einem langen `SECRET_KEY` füllen.
2. `MOTODB_PUBLIC_HOSTING=true` setzen.
3. Bei einem Reverse Proxy `MOTODB_TRUST_PROXY_HEADERS=true` setzen.
4. Den ersten Admin einer neuen Datenbank einmalig über
   `MOTODB_ADMIN_USERNAME`, `MOTODB_ADMIN_EMAIL` und
   `MOTODB_ADMIN_PASSWORD` bootstrappen.
5. Selbstregistrierung nur bewusst mit `MOTODB_ALLOW_REGISTRATION=true`
   aktivieren.
6. Die öffentliche URL ausschließlich über HTTPS bereitstellen, zum Beispiel
   per Tunnel oder TLS-terminierendem Reverse Proxy.

Der Public-Hosting-Modus aktiviert sichere Session-Cookies, HSTS,
Sicherheitsheader, CSRF-Schutz für Formulare und JSON-POSTs sowie Startchecks
gegen den Entwicklungs-Secret-Key und das bekannte Default-Admin-Passwort.
Uploads werden nur noch nach Login und Eigentümerprüfung ausgeliefert.

HTTP-Deployments im Heimnetz dürfen `MOTODB_PUBLIC_HOSTING` nicht aktivieren.
Sichere Session-Cookies werden über HTTP vom Browser nicht gespeichert; der
Login kann dann nicht abgeschlossen werden.

## Wichtige Routen

| Route | Zweck |
| --- | --- |
| `/` | Motorradübersicht (Garage) |
| `/motorrad/neu` | Motorrad anlegen |
| `/motorrad/<id>` | Motorrad-Detailansicht (Tabs: Historie / Datenblatt / Dokumente) |
| `/motorrad/<id>/bearbeiten` | Motorrad bearbeiten |
| `/motorrad/<id>/service/neu` | Serviceeintrag anlegen |
| `/service/<id>/bearbeiten` | Serviceeintrag bearbeiten |
| `/service/<id>/ansicht` | Serviceeintrag anzeigen |
| `/motorrad/<id>/technik` | Technische Daten für ein Motorrad (CSV-Import) |
| `/motorrad/<id>/datenblatt` | Technische Daten inline speichern (POST) |
| `/motorrad/<id>/datenblatt/reihenfolge` | Reihenfolge per Drag & Drop speichern (POST JSON) |
| `/technik` | CSV-Import technischer Daten mit Motorrad-Auswahl |
| `/technik/csv-vorlage` | CSV-Vorlage für technische Daten |
| `/motorrad/<id>/dokumente/neu` | Dokument hochladen |
| `/dokumente` | Dokumente hochladen (POST) |
| `/dokumente/<id>/loeschen` | Dokument löschen (POST) |
| `/checklisten/neu` | Checkliste global anlegen |
| `/checklisten/import` | Punkteliste global importieren |
| `/motorrad/<id>/checklisten` | Checklisten eines Motorrads |
| `/motorrad/<id>/checklisten/neu` | Checkliste für ein Motorrad anlegen |
| `/motorrad/<id>/checklisten/import` | Punkteliste für ein Motorrad importieren |
| `/checklisten/<id>` | Vorlage ausfüllen (erzeugt Datensatz) bzw. Datensatz anzeigen |
| `/checklisten/<id>/vorlage-bearbeiten` | Vorlage bearbeiten |
| `/checklisten/<id>/loeschen` | Checkliste/Datensatz löschen (POST) |
| `/checklisten/csv-vorlage` | CSV-Vorlage für Checklisten |
| `/einstellungen` | Profil und Einstellungen |
| `/settings/backup-path` | Sicherungsort speichern (POST, Admin) |
| `/settings/backup` | Server-Backup erstellen (POST, Admin) |
| `/hilfe` | Übersicht aller Hilfethemen |
| `/datenschutz` | Datenschutzhinweise (ohne Login) |
| `/health` | Healthcheck (ohne Login, prüft DB-Verbindung) |
| `/login`, `/logout`, `/register` | Anmeldung, Abmeldung (POST), Registrierung |
| `/account/password` | Passwort ändern |
| `/user/export` | ZIP-Export der eigenen Daten |
| `/user/delete` | Eigenes Konto löschen |
| `/admin/users` | Nutzerverwaltung (Admin) |
| `/uploads/<pfad>` | Hochgeladene Dateien ausliefern |
| `/manifest.webmanifest` | PWA-Manifest |
| `/service-worker.js` | Service Worker |

## Wartung und Fehlersuche

### Port 5001 ist belegt

Wenn beim Start diese Meldung erscheint:

```text
Address already in use
Port 5001 is in use by another program.
```

dann läuft entweder bereits eine Instanz der App oder ein anderer Prozess
verwendet den Port.

Prüfen:

```bash
lsof -i :5001
```

### Datenbank wird nicht gefunden

Die Standard-Datenbank liegt im Flask-Instance-Ordner. Lokal ist das in diesem
Projekt normalerweise:

```text
instance/motorcycle_service.sqlite3
```

Im Dockerbetrieb liegt die Datenbank unter:

```text
/data/motorcycle_service.sqlite3
```

### Login bleibt im Public-Hosting-Modus stehen

Wenn die Login-Seite meldet, dass Public Hosting HTTPS erwartet, wird die App
über HTTP geöffnet, während `MOTODB_PUBLIC_HOSTING=true` gesetzt ist. Für ein
lokales HTTP-Deployment diese Variable aus `.env` entfernen oder auskommentiert
lassen. Für öffentliches Hosting die App ausschließlich über HTTPS öffnen und
bei einem Reverse Proxy `MOTODB_TRUST_PROXY_HEADERS=true` setzen.

### Uploads fehlen nach Deployment

Beim Deployment müssen neben dem Code auch die Laufzeitdaten migriert werden:

```bash
rsync -av instance/motorcycle_service.sqlite3 <benutzer>@<pi-adresse>:/srv/motorrad-service/data/
rsync -av instance/uploads/ <benutzer>@<pi-adresse>:/srv/motorrad-service/data/uploads/
```

### Sync funktioniert nicht

Mögliche Ursachen:

- Server ist nicht erreichbar.
- Browser ist offline.
- IndexedDB enthält keine offenen Einträge des angemeldeten Kontos.
- Das Motorrad aus einem Offline-Eintrag wurde inzwischen gelöscht oder gehört
  einem anderen Konto (Eintrag wird als abgelehnt markiert).

Der Sync-Button zeigt Statusmeldungen über die Toast-Komponente der App.

### Checklisten-CSV importiert nichts

Prüfen:

- Enthält die Datei eine Kopfzeile?
- Sind `Titel` und `Pruefpunkt` oder `Prüfpunkt` vorhanden?
- Passt `Motorrad` exakt zu Marke/Modell oder ist `MotorradID` gesetzt?
- Ist das Trennzeichen konsistent?
- Ist die Datei UTF-8 oder UTF-8 mit BOM?

### Technische Daten werden ersetzt

Beim Speichern technischer Daten (CSV-Import, Datenblatt) löscht die App zunächst alle
vorhandenen technischen Daten des Motorrads und legt die neu importierten Werte
an. Die per Drag & Drop gespeicherte Reihenfolge bleibt durch `position`-Werte
erhalten. Vor größeren Importen ist ein Backup sinnvoll.

## Entwicklungsnotizen

- Manuelle Schemaänderungen werden beim App-Start in `ensure_schema_updates`
  durchgeführt (ALTER TABLE + Backfill). Für größere Datenbankänderungen wäre
  langfristig eine Migration mit Alembic oder Flask-Migrate sinnvoll.
- Die JSON-API ist auf Offline- und Sync-Funktionen ausgelegt und noch keine
  vollständige öffentliche REST-API.
- Löschen eines Motorrads entfernt auch die zugehörigen Uploads.
- Serviceeinträge und Checklistenhistorien beeinflussen den angezeigten
  Kilometerstand.
- Die CSP (`script-src 'self'`, `style-src 'self'`) lässt keine
  Inline-`<script>`-Tags und keine `style=""`-Attribute zu. Alle JS-Ergänzungen
  gehören in externe `.js`-Dateien, alle Styles in `app.css`.
- Bei Produktivbetrieb sollte die App ausschließlich hinter Gunicorn und Nginx
  laufen, nicht mit dem Flask-Debug-Server.

## Kurzübersicht für den Alltag

Lokale App starten:

```bash
python3 run.py
```

Im Browser öffnen:

```text
http://127.0.0.1:5001
```

Docker neu bauen und starten:

```bash
docker compose up -d --build
```

Logs anzeigen:

```bash
docker compose logs -f
```

Raspberry-Pi-Anleitung öffnen:

```text
deploy/README_RASPI.md
```

## Lizenz

MotoDB steht unter der [MIT-Lizenz](LICENSE). Die mitgelieferten Schriften
IBM Plex Sans/Mono (`app/static/fonts/`) stehen unter der SIL Open Font
License 1.1 (siehe `app/static/fonts/LICENSE.txt`).

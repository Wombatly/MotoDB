# MotoDB

MotoDB ist eine kleine Flask-Webanwendung zur Verwaltung von Motorrädern,
Serviceeinträgen, technischen Daten, Checklisten und Belegen. Das Projekt ist
auf den privaten Werkstatt- und Fuhrparkbetrieb ausgelegt: Motorräder können
erfasst, Wartungen dokumentiert, Checklisten gepflegt und Serviceeinträge auch
offline vorbereitet werden.

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
- [Offline-Sync](#offline-sync)
- [API-Endpunkte](#api-endpunkte)
- [Uploads und Belege](#uploads-und-belege)
- [Backups](#backups)
- [Docker und Raspberry-Pi-Deployment](#docker-und-raspberry-pi-deployment)
- [Wartung und Fehlersuche](#wartung-und-fehlersuche)

## Funktionsumfang

### Motorradverwaltung

- Motorräder mit Marke, Modell, Baujahr, Kilometerstand, Kaufdaten,
  Zulassung, Kennzeichen, VIN, Farbe, Hubraum, Leistung und Notizen anlegen.
- Motorräder bearbeiten und löschen.
- Motorradbilder hochladen und entfernen.
- Aktive und verkaufte Motorräder verwalten.
- Automatische Aktualisierung des Kilometerstands anhand der neuesten
  Service- oder Checklistenhistorie.

### Service- und Kostenhistorie

- Serviceeinträge pro Motorrad erfassen.
- Kategorien wie Wartung, Ersatzteile, Reifen, Versicherung, Steuer, TÜV/HU,
  Kraftstoff, Zubehör, Reparatur und Sonstiges verwenden.
- Datum, Kilometerstand, Beschreibung, Kosten, nächste Service-Kilometer und
  nächste Service-Termine speichern.
- Belege hochladen und dem Serviceeintrag zuordnen.
- Kosten nach Kategorie in der Detailansicht auswerten.

### Technische Daten

- Technische Spezifikationen pro Motorrad erfassen.
- Daten nach Kategorien wie Motor, Antrieb, Fahrwerk, Bremsen, Reifen, Maße
  und Elektrik strukturieren.
- Werte, Einheiten und Quellen dokumentieren.
- Daten per Freitext, JSON-artigem Import oder CSV übernehmen.
- CSV-Vorlage für technische Daten herunterladen.

### Service-Checklisten

- Checklisten als Vorlagen erstellen.
- Vorgefertigte Presets nutzen, zum Beispiel:
  - 1.000 km Einfahrkontrolle
  - 10.000 km Service
  - 20.000 km großer Service
  - Saisoncheck
- Checklistenpunkte mit Kommentaren und Hinweisen pflegen.
- Checklisten aus CSV importieren.
- Checklisten als erledigte Wartungsnachweise speichern.
- Erledigte Punkte und Anmerkungen pro Durchführung erfassen.

### Offline-Unterstützung

- Serviceformulare können offline im Browser gespeichert werden.
- Offline-Daten landen in IndexedDB.
- Über den Sync-Button werden offene Einträge später an den Server übertragen.
- Vor einem Sync wird optional ein Backup der bestehenden Daten erstellt.

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
- Gunicorn für Containerbetrieb
- Docker Compose für Deployment
- Nginx als Reverse Proxy auf dem Raspberry Pi
- Vanilla JavaScript für Menü, Offline-Speicher und Sync
- IndexedDB für lokale Offline-Wartungseinträge

Die Python-Abhängigkeiten stehen in `requirements.txt`:

```txt
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Pillow==10.4.0
gunicorn==22.0.0
```

## Projektstruktur

```text
.
├── app/
│   ├── __init__.py              # Flask-App-Factory, Datenbank, Defaults
│   ├── models.py                # SQLAlchemy-Modelle
│   ├── routes.py                # Views, API, Import, Sync, Hilfslogik
│   ├── utils.py                 # Parser, Uploads, Presets, Konstanten
│   ├── static/
│   │   ├── css/app.css          # Styling
│   │   ├── js/app.js            # UI-Verhalten
│   │   ├── js/indexeddb.js      # Offline-Datenbank im Browser
│   │   ├── js/sync.js           # Sync-Logik
│   │   ├── manifest.webmanifest # PWA-Manifest
│   │   └── service-worker.js    # Service Worker
│   └── templates/
│       ├── base.html
│       ├── settings.html
│       ├── motorcycles/
│       ├── service/
│       └── checklists/
├── deploy/
│   ├── README_RASPI.md          # Raspberry-Pi-Anleitung
│   ├── nginx/
│   └── update-on-pi.sh
├── instance/
│   ├── motorcycle_service.sqlite3
│   └── uploads/
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

- Python 3.12 oder kompatible Python-3-Version
- `pip`
- Optional: virtuelles Environment

### Installation

```bash
cd /Users/gregor/Documents/Codex/MotoDB
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Falls bereits ein passendes Environment existiert, reicht es, dieses zu
aktivieren und die Abhängigkeiten zu installieren.

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

## Datenhaltung

Die Datenbank wird über SQLAlchemy verwaltet. Beim Start erstellt die App die
Tabellen automatisch, falls sie fehlen. Zusätzlich führt `ensure_schema_updates`
kleine Schema-Nachziehungen für bestehende Datenbanken aus.

### Hauptmodelle

#### `Motorcycle`

Speichert Stammdaten zu einem Motorrad:

- Marke und Modell
- Baujahr und Kilometerstand
- Kaufpreis, Kaufdatum, Verkaufspreis und Verkaufsdatum
- Hubraum, PS, Farbe
- Kennzeichen, VIN, Erstzulassung
- Status `aktiv`
- Notizen
- Bildpfad

Verknüpfungen:

- `services`
- `technical_specs`
- `checklists`

#### `ServiceEntry`

Speichert Wartungs-, Kosten- und Ereigniseinträge:

- Motorrad-ID
- Titel
- Datum
- Kilometerstand
- Beschreibung
- Kosten
- Kategorie
- Belegpfad und Originalname
- nächste Service-Kilometer
- nächstes Service-Datum

#### `TechnicalSpec`

Speichert technische Daten pro Motorrad:

- Name
- Wert
- Einheit
- Kategorie
- Quelle

#### `ServiceChecklist`

Speichert Checklisten. Eine Checkliste kann entweder Vorlage oder erledigter
Nachweis sein.

Wichtige Felder:

- Titel
- Intervall in Kilometern
- Intervall in Monaten
- Datum
- Kilometerstand
- Anmerkungen
- `is_template`
- `source_template_id`
- `completed_at`

#### `ServiceChecklistItem`

Speichert einzelne Prüfpunkte einer Checkliste:

- Position
- Text
- Kommentarvorlage
- erledigt/nicht erledigt
- Anmerkung

#### `AppSetting`

Speichert einfache Schlüssel-Wert-Einstellungen. Aktuell wird vor allem der
Backup-Pfad unter dem Schlüssel `backup_path` verwendet.

## Benutzeroberfläche

Die Anwendung rendert serverseitig mit Jinja-Templates. Das Grundlayout liegt
in `app/templates/base.html`.

Hauptnavigation:

- MotoDB-Startseite
- Einstellungen
- Sync

Die App ist für mobile Nutzung gedacht. Das Menü ist kompakt gehalten und wird
über `app/static/js/app.js` gesteuert.

## Checklisten

Checklisten können direkt in der Anwendung, über Presets oder per CSV angelegt
werden.

### Presets

Die Presets stehen in `app/utils.py` unter `SERVICE_CHECKLIST_PRESETS`.

Vorhandene Presets:

- `1000`: 1.000 km Einfahrkontrolle
- `10000`: 10.000 km Service
- `20000`: 20.000 km großer Service
- `season`: Saisoncheck

### CSV-Vorlage

Die Checklisten-Vorlage kann unter `Einstellungen` oder direkt über diese Route
heruntergeladen werden:

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

### CSV-Vorlage

Die Route `/technik/csv-vorlage` liefert eine Vorlage:

```csv
Kategorie;Eintrag;Wert;Einheit;Quelle
Motor;Hubraum;583;ccm;Fahrzeugschein
Motor;Leistung;50;PS;Fahrzeugschein
Motor;Drehmoment;53;Nm;Werkstatthandbuch
Antrieb;Getriebe;5-Gang;;Werkstatthandbuch
Reifen;Reifen vorne;90/90-21;;Handbuch
Reifen;Reifen hinten;130/80-17;;Handbuch
```

### Freitext-Import

Der Import akzeptiert einfache Zeilen mit Doppelpunkt oder Gleichheitszeichen:

```text
Hubraum: 583 ccm
Leistung: 50 PS
Tankinhalt = 17 l
```

Alternativ kann ein einfaches JSON-Objekt importiert werden:

```json
{
  "Hubraum": "583 ccm",
  "Leistung": "50 PS",
  "Tankinhalt": "17 l"
}
```

Beim Speichern ersetzt die App die bisherigen technischen Daten des jeweiligen
Motorrads durch die neu zusammengeführten Zeilen.

## Offline-Sync

Die Offline-Funktion nutzt IndexedDB im Browser. Die Logik ist aufgeteilt in:

- `app/static/js/indexeddb.js`: lokale Browserdatenbank
- `app/static/js/sync.js`: Speichern und Synchronisieren

Offline gespeicherte freie Serviceeinträge landen im Object Store
`pendingServices`.

Offline gespeicherte Checklisten-Serviceeinträge landen im Object Store
`pendingChecklistServices`.

Beim Klick auf `Sync` sendet der Browser die offenen Daten an:

```text
POST /api/sync
```

Die App erstellt vor der Synchronisierung ein Backup, sofern in den
Einstellungen ein gültiger Backup-Pfad hinterlegt ist. Anschließend werden die
neuen Serviceeinträge und Checklistenhistorien serverseitig gespeichert.

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

Die Antwort enthält neu angelegte Serviceeinträge und neu angelegte
Checklistenhistorien.

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
```

Für Bilder wird Pillow verwendet. Beim Upload werden Bilder:

- anhand der EXIF-Orientierung ausgerichtet,
- auf maximal `1600 x 1200` verkleinert,
- als JPEG mit Qualität `82` gespeichert,
- progressiv und optimiert geschrieben.

Belege werden als Datei gespeichert und mit dem Originalnamen im
Serviceeintrag referenziert.

## Backups

Der Backup-Pfad wird in der App unter `Einstellungen` gepflegt. Intern liegt er
als `AppSetting` mit dem Schlüssel `backup_path` in der Datenbank.

Wenn ein gültiger Pfad gesetzt ist, erstellt `POST /api/sync` vor der
Übernahme von Offline-Daten einen Sicherungsordner:

```text
motorrad_service_sync_<YYYYMMDD_HHMMSS>/
```

Darin landen:

- `motorcycle_service.sqlite3`
- eine Kopie des Upload-Ordners

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
- Docker-Compose-Start
- Nginx-Konfiguration
- Firewall
- Backup-Pfad
- Update-Ablauf

### Öffentliches Hosting

Für einen öffentlichen HTTPS-Zugang sollte die App weiter hinter Gunicorn und
einem Reverse Proxy laufen. Vor dem Start der öffentlichen Instanz:

1. `.env` mit einem langen `SECRET_KEY` füllen.
2. `MOTODB_PUBLIC_HOSTING=true` setzen.
3. Bei einem Reverse Proxy `MOTODB_TRUST_PROXY_HEADERS=true` setzen. Die
   mitgelieferte `compose.yaml` setzt diesen Wert für den Nginx-Pfad bereits.
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

## Wichtige Routen

| Route | Zweck |
| --- | --- |
| `/` | Motorradübersicht mit Suche und Sortierung |
| `/motorrad/neu` | Motorrad anlegen |
| `/motorrad/<id>` | Motorrad-Detailansicht |
| `/motorrad/<id>/bearbeiten` | Motorrad bearbeiten |
| `/motorrad/<id>/service/neu` | Serviceeintrag anlegen |
| `/service/<id>/bearbeiten` | Serviceeintrag bearbeiten |
| `/technik` | Technische Daten global bearbeiten |
| `/motorrad/<id>/technik` | Technische Daten für ein Motorrad |
| `/technik/csv-vorlage` | CSV-Vorlage für technische Daten |
| `/checklisten/neu` | Checkliste global anlegen |
| `/motorrad/<id>/checklisten` | Checklisten eines Motorrads |
| `/motorrad/<id>/checklisten/neu` | Checkliste für ein Motorrad anlegen |
| `/checklisten/<id>` | Checkliste anzeigen oder durchführen |
| `/checklisten/csv-vorlage` | CSV-Vorlage für Checklisten |
| `/einstellungen` | App-Einstellungen |
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

### Uploads fehlen nach Deployment

Beim Deployment müssen neben dem Code auch die Laufzeitdaten migriert werden:

```bash
rsync -av instance/motorcycle_service.sqlite3 gregor@192.168.178.102:/srv/motorrad-service/data/
rsync -av instance/uploads/ gregor@192.168.178.102:/srv/motorrad-service/data/uploads/
```

### Sync funktioniert nicht

Mögliche Ursachen:

- Server ist nicht erreichbar.
- Browser ist offline.
- IndexedDB enthält keine offenen Einträge.
- Backup-Pfad ist ungültig oder nicht beschreibbar.
- Das Motorrad aus einem Offline-Eintrag wurde inzwischen gelöscht.

Der Sync-Button zeigt Statusmeldungen über die Toast-Komponente der App.

### Checklisten-CSV importiert nichts

Prüfen:

- Enthält die Datei eine Kopfzeile?
- Sind `Titel` und `Pruefpunkt` oder `Prüfpunkt` vorhanden?
- Passt `Motorrad` exakt zu Marke/Modell oder ist `MotorradID` gesetzt?
- Ist das Trennzeichen konsistent?
- Ist die Datei UTF-8 oder UTF-8 mit BOM?

### Technische Daten werden ersetzt

Beim Speichern technischer Daten löscht die App zunächst alle vorhandenen
technischen Daten des Motorrads und legt anschließend die neu importierten oder
eingegebenen Werte an. Vor größeren Importen ist ein Backup sinnvoll.

## Entwicklungsnotizen

- Manuelle Schemaänderungen werden aktuell direkt beim App-Start in
  `ensure_schema_updates` durchgeführt.
- Für größere Datenbankänderungen wäre langfristig eine Migration mit Alembic
  oder Flask-Migrate sinnvoll.
- Die JSON-API ist auf Offline- und Sync-Funktionen ausgelegt und noch keine
  vollständige öffentliche REST-API.
- Löschen eines Motorrads entfernt auch die zugehörigen Uploads.
- Serviceeinträge und Checklistenhistorien beeinflussen den angezeigten
  Kilometerstand.
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

# MotoDB Audit-Report

Datum: 2026-06-07
Umfang: Security, Performance/Skalierung, Code-Qualität und Wartbarkeit.
Vorheriger Report: 2026-05-25 (dieser Report ersetzt ihn).

## Kurzfazit

Seit dem letzten Audit wurden die wichtigsten Punkte behoben: Dependencies sind
aktuell und laut OSV ohne bekannte Schwachstellen, die Upload-Verarbeitung wurde
deutlich gehärtet (echte Bildformat-Prüfung, PDF-Limits), App-seitiges
Rate-Limiting ist vorhanden, und der offene Referrer-Redirect ist beseitigt.

Die verbleibenden Punkte sind überwiegend **niedrige Risiken** und
**Performance-/Wartbarkeitsthemen**, die für den aktuellen Privatbetrieb (wenige
Nutzer, Zugriff über LAN/Tailscale) unkritisch sind, aber bei wachsender Nutzung
oder öffentlicher Exposition angegangen werden sollten.

## Verifikation

- `python -m unittest tests.test_security`: **17 Tests OK** (nach Fix eines durch UI-Änderung veralteten Tests, siehe unten).
- OSV-Abfrage am 2026-06-07 über `https://api.osv.dev/v1/querybatch` für alle Pakete aus `requirements.txt`: **keine Treffer**.
- Installierte Versionen (Laufzeit-Container): Flask 3.1.3, Werkzeug 3.1.8, Pillow 12.2.0, pypdf 6.12.2, gunicorn 22.0.0, Flask-WTF 1.2.1, Flask-Login 0.6.3, Flask-SQLAlchemy 3.1.1.
- Quellcode-Durchsicht von `app/__init__.py`, `app/routes.py`, `app/auth.py`, `app/utils.py`, `app/models.py`.

## Seit dem letzten Audit behoben

- **Verwundbare Dependencies** → aktualisiert; OSV meldet keine bekannten Schwachstellen mehr (vorher Flask/Werkzeug/Pillow/pypdf betroffen).
- **Upload-Typprüfung nur per Endung** → `save_upload` nutzt jetzt `secure_filename`, eine Endungs-Allowlist je Ordner und temporäre Dateien; Bilder werden mit `Image.open(..., formats=ALLOWED_IMAGE_FORMATS)` + `image.verify()` echt validiert (`app/utils.py:501`, `app/utils.py:554`).
- **Bild unter falscher Endung als JPEG gespeichert** → Bilder werden nun konsequent als `.jpg` gespeichert (`stored_extension`, `app/utils.py:518`).
- **PDF-Parsing unbegrenzt** → Limits aktiv: max. 2 MB Datei, 20 Seiten, 100 000 Zeichen, Magic-Header- und Encrypted-Prüfung (`app/utils.py:24`, `app/utils.py:375`).
- **Login-Rate-Limit nur in Nginx** → App-seitiges Rate-Limiting pro IP/E-Mail (`app/auth.py:19`, `app/auth.py:54`).
- **Offene Referrer-Weiterleitung** → `backup_path_update` leitet fest auf `main.settings` (`app/routes.py:253`).
- **Pfad-Traversal bei Uploads** → mehrschichtig abgesichert: Ownership-Check, `resolve_upload_path` (`relative_to(root)`) und `send_from_directory` (`app/routes.py:798`, `app/routes.py:1035`).

## Security (offen)

### Niedrig: Rate-Limiting ist In-Memory und pro Worker

Fundstelle: `app/auth.py:19` (`AUTH_ATTEMPTS = {}`)

Das Rate-Limit liegt in einem Prozess-Dictionary. Bei `gunicorn --workers 2` hat
jeder Worker einen eigenen Zähler (effektiv ~2× Limit), und Neustarts setzen die
Zähler zurück. Für wenige Nutzer ausreichend; bei härterem Brute-Force-Schutz
einen gemeinsamen Speicher (z. B. Redis) oder `flask-limiter` nutzen.

### Niedrig: ProxyFix dauerhaft aktiv

Fundstelle: `compose.yaml`, `app/__init__.py:71`

`MOTODB_TRUST_PROXY_HEADERS` ist aktiv, damit Flask hinter Nginx das echte Schema/
die echte IP sieht. Das ist nur sicher, solange der App-Port **nicht** direkt
öffentlich erreichbar ist (aktuell `127.0.0.1:5001`). Als Deployment-Annahme
festhalten: App-Port nie direkt exponieren, wenn Proxy-Header vertraut werden.

### Niedrig: `request.get_json(force=True)` ignoriert Content-Type

Fundstelle: `app/routes.py:862`, `app/routes.py:891`

`force=True` parst den Body auch ohne `application/json`. CSRF greift weiterhin
(die Endpunkte sind nicht von CSRFProtect ausgenommen, `sync.js` sendet den
`X-CSRFToken`-Header), daher kein CSRF-Loch. Sauberer wäre `silent=True` mit
expliziter Fehlerbehandlung statt `force`.

### Hinweis: Laufzeit-Deployment ohne Public-Hosting-Modus

Der aktiv laufende Container nutzt `MOTODB_PUBLIC_HOSTING=false`, damit Login auch
über HTTP (LAN/Tailscale) funktioniert. Das ist für den privaten Zugriff über das
verschlüsselte Tailscale-Netz vertretbar. Bei echter öffentlicher Exposition
muss `MOTODB_PUBLIC_HOSTING=true` mit HTTPS gesetzt werden (erzwingt Secure-Cookies,
HSTS, CSRF-über-HTTP-Block). `compose.yaml`/`.env` und der Laufzeit-Container
sollten konsolidiert werden, damit beide denselben Modus beschreiben.

## Performance und Skalierung

### `latest_service_mileage` lädt alle Kandidaten in Python

Fundstelle: `app/routes.py:1005`

Lädt alle Service- und Checklisten-Datensätze und bildet das Maximum in Python.
Wird bei Detail-/Edit-Aufrufen und nach Mutationen genutzt. Zudem schreibt
`ensure_motorcycle_mileage_is_current` bei Abweichung per `commit()` **während eines
GET-Requests** (`app/routes.py:998`). Empfehlung: per SQL `ORDER BY ... LIMIT 1`
oder denormalisierten Kilometerstand gezielt beim Schreiben aktualisieren.

### Detailseite lädt komplette Service-Historie

Fundstelle: `app/routes.py:457`

Alle Services und technischen Daten werden geladen, Kostenaggregation passiert in
Python. Bei langer Historie wächst die Seite. Empfehlung: paginieren/begrenzen,
Aggregation per SQL.

### User-Export: N+1-Abfragen und ZIP komplett im RAM

Fundstelle: `app/auth.py:234`

Pro Motorrad werden Bilder, Services, Dokumente, Specs und Checklisten separat
abgefragt; das ZIP entsteht vollständig in `BytesIO`. Empfehlung: Beziehungen
eager-loaden (`selectinload`) und ZIP bei großen Exports in eine temporäre Datei
streamen.

### Sync-Backup kopiert vor jedem Sync den gesamten Upload-Baum

Fundstelle: `app/routes.py:1427` (`create_sync_backup`)

Bei gesetztem Backup-Pfad werden SQLite-Datei und kompletter Upload-Ordner vor
jedem Sync kopiert (blockierend im Request). Bei vielen Bildern/PDFs teuer und
speicherintensiv. Empfehlung: entkoppeln, inkrementell oder nach Zeit/Größe drosseln.

### Disk-Usage wird global in alle Templates injiziert

Fundstelle: `app/routes.py:144` (`inject_settings`)

`get_disk_usage()` (ruft `shutil.disk_usage`) läuft per Context-Processor auf
**jeder** Seite, obwohl es nur in Admin-/Settings-Ansichten angezeigt wird.
Empfehlung: nur dort berechnen, wo es gebraucht wird.

## Code-Qualität und Wartbarkeit

### Test war nicht mehr synchron mit der UI (in diesem Audit behoben)

`tests/test_security.py:245` prüfte auf den Text „Garage herunterladen", der beim
UI-Umbau (Karte „Daten auf mein Gerät sichern") entfernt wurde. Der Test wurde auf
die stabile Export-Route `"/user/export"` umgestellt; alle 17 Tests sind grün.

### Tests werden nicht ins Docker-Image kopiert

Fundstelle: `Dockerfile` (kopiert nur `app` und `run.py`)

Dadurch lassen sich Tests nicht direkt im Build/Container ausführen. Für CI/lokale
Verifikation `tests/` einbeziehen oder einen separaten Test-Build vorsehen.

### Ungenutzter Code

- `AuditLog`-Modell ist definiert, hat aber keine Schreibstelle (`app/models.py`).
- `split_lines` wird nirgends aufgerufen (`app/routes.py:1099`).
- Legacy-Route `/motorrad/<id>/bild-loeschen` existiert neben der Galerie-Route `/motorrad/<id>/bilder/<image_id>/loeschen` (`app/routes.py:517` vs. `:537`).

Empfehlung: entfernen oder bewusst als Kompatibilität dokumentieren.

### SQLAlchemy Legacy-API

`Model.query.get(...)` (Legacy) wird noch verwendet: 2× in `app/__init__.py`,
6× in `app/routes.py`. Empfehlung: schrittweise auf `db.session.get(Model, id)`
umstellen.

### `routes.py` ist sehr groß

Fundstelle: `app/routes.py` (~1445 Zeilen) mischt Views, API, Import, Backup und
Upload-Helfer. Empfehlung: in Module aufteilen (`views/`, `services/uploads.py`,
`services/backups.py`, `services/mileage.py`).

### Manuelle Schema-Migrationen

`ensure_schema_updates` führt Raw-SQL-Migrationen beim Start aus
(`app/__init__.py`). Pragmatisch für SQLite, aber bei mehr Änderungen schwer
rückrollbar. Ab der nächsten größeren Änderung Alembic/Flask-Migrate erwägen.

## Empfohlene Reihenfolge

1. Verbleibende Performance-Hotspots: `latest_service_mileage` (SQL statt Python, kein Commit im GET), Disk-Usage nur in Admin-Views.
2. Ungenutzten Code bereinigen (`AuditLog`, `split_lines`, Legacy-Bildroute).
3. `compose.yaml`/`.env` mit dem realen Laufzeit-Modus konsolidieren und Deployment-Annahmen dokumentieren.
4. Sync-Backup vom Request entkoppeln/drosseln; User-Export eager-loaden/streamen.
5. Schrittweise `db.session.get(...)` und ggf. versionierte Migrationen einführen.

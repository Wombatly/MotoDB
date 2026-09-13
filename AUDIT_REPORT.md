# MotoDB Audit-Report

Datum: 2026-09-13
Umfang: Security, Korrektheit, Konsistenz (Code ↔ Doku ↔ Betrieb) und
Veröffentlichungsreife.
Vorheriger Report: 2026-06-07 (dieser Report ersetzt ihn).

## Kurzfazit

Die Punkte des Juni-Audits zu Dependencies, Upload-Härtung und Pfad-Traversal
sind weiterhin sauber. Dieses Audit hat den kompletten Code (Backend,
Templates, JS, Service Worker, Deploy-Dateien, Git-Historie) durchgesehen und
verdächtige Stellen mit einem Probe-Skript gegen den Test-Client verifiziert.

Ergebnis: **elf Befunde wurden in diesem Audit behoben** (Abschnitt „Behoben“),
darunter zwei Betriebsrisiken (Login-Sperre für alle Nutzer; Vollbackup pro
Sekunde durch jeden Nutzer auslösbar) und mehrere 500er durch ungeprüfte
Eingaben. Verbleibend sind Doku-Inkonsistenzen, interne Daten im Repo und
Punkte, die für eine Veröffentlichung noch fehlen (Lizenz, CI, non-root
Container).

## Verifikation

- `python -m unittest tests.test_security tests.test_input_validation`
  im Laufzeit-Image: **32 Tests OK** (17 bestehende + 15 neue).
- Smoke-Test über 33 GET-Routen nach den Änderungen: alle 200.
- Sync-Logik (`sync.js`) mit gemockter IndexedDB/fetch in Node geprüft.
- Git-Historie: keine `.env`, keine SQLite-Datei, keine Secrets committet.
- Laufender Container (`motorrad-service-http`) am 2026-09-13:
  `MOTODB_PUBLIC_HOSTING=false`, `MOTODB_TRUST_PROXY_HEADERS=false`,
  `MOTODB_ALLOW_REGISTRATION=true`, `MOTODB_MAX_STORAGE_MB=200`.

## In diesem Audit behoben

### Hoch

1. **Login-Sperre traf alle Nutzer gleichzeitig.** Hinter Nginx ohne
   `MOTODB_TRUST_PROXY_HEADERS` ist `remote_addr` für alle `127.0.0.1`; fünf
   Fehlversuche von irgendjemandem sperrten den Login für alle 15 Minuten.
   Fix: IP-Key wird nur genutzt, wenn Proxy-Header vertraut werden oder die
   Adresse keine Loopback-Adresse ist; sonst nur das Limit pro E-Mail. Beim
   Start erscheint eine Warnung im Log (`app/auth.py`, `app/__init__.py`).
   **Betrieb:** zusätzlich `MOTODB_TRUST_PROXY_HEADERS=true` in `.env.http`
   setzen (siehe „Offene Punkte → Betrieb“).
2. **Jeder Nutzer konnte per `POST /api/sync` ein Vollbackup (DB + alle
   Uploads) pro Sekunde auslösen** – Disk-Fill-DoS, dazu inkonsistente Kopie
   der Live-SQLite per `shutil.copy2`. Fix: Sync erstellt kein Backup mehr;
   Admins haben „Backup jetzt erstellen“ (`POST /settings/backup`) mit
   SQLite-Backup-API (`create_server_backup`, `app/routes.py`).
3. **500er durch ungeprüfte Eingaben.** `parse_date` warf `ValueError`
   (Formulare und JSON-API), `get_json(force=True)` akzeptierte Nicht-Dicts,
   fehlende `motorrad_id` crashte. Fix: `InvalidDateError` + Blueprint-
   Errorhandler (Formular: Flash + Redirect zurück, API: JSON 400),
   `get_json(silent=True)` mit Typprüfung, `parse_int` für IDs; `/api/sync`
   überspringt ungültige Einzel-Einträge und meldet sie (`rejected`).

### Mittel

4. **Datenblatt-Autosave hängte die Einheit bei jedem Speichern erneut an**
   („583 ccm ccm“). Fix: Eingabefeld enthält nur den Wert, Einheit steht als
   Text daneben; `strip_unit_suffix` bereinigt Alt-Eingaben; einmalige
   Bereinigung vorhandener Daten in `ensure_schema_updates`.
5. **Checklisten-Intervall wurde als Kilometerstand übernommen** (Motorrad mit
   500 km → „10.000 km Service“ ohne km-Angabe → 10.000 km). Fix: nur echte
   km-Angaben zählen; `latest_service_mileage` per SQL (`LIMIT 1`) statt
   Python-Maximum; kein `commit()` mehr im GET; Abgleich aller Kilometerstände
   einmal beim Start (`reconcile_all_motorcycle_mileages`); Nachziehen auch
   beim Ausfüllen über `/checklisten/<id>` und beim Löschen von Datensätzen.
6. **Offline-Einträge gingen bei Nutzerwechsel im selben Browser verloren.**
   Fix: Einträge tragen die Nutzer-ID, Sync sendet nur eigene Einträge; Server
   bestätigt pro Eintrag (`accepted`/`rejected` als Indizes), Client löscht nur
   Bestätigtes; Abgelehntes bleibt markiert, Auto-Sync überspringt es, manueller
   Sync fragt vor dem Verwerfen (`sync.js`, `indexeddb.js`, `api_sync`).
7. **Google Fonts wurden von der eigenen CSP blockiert** (Logbuch-Theme fiel
   still auf Systemschrift zurück; bei Freigabe DSGVO-relevanter externer
   Request). Fix: IBM Plex Sans/Mono als Latin1-WOFF2 selbst gehostet
   (`app/static/fonts/`, OFL-Lizenz beiliegend, 156 KB), `@font-face` in
   `app.css`, MIME-Typen registriert, Service-Worker-Precache ergänzt.
8. **Speicherlimit-Meldung hardcoded „500 MB“**, Betrieb hat 200 MB. Fix:
   `storage_limit_message` leitet den Wert aus `MAX_USER_STORAGE_BYTES` ab.
9. **Registrierung ohne E-Mail-Validierung und ohne Einwilligung.** Fix:
   Formatprüfung + Normalisierung (Kleinschreibung, Längen wie DB-Spalten),
   Pflicht-Checkbox für die Datenschutzhinweise, `consent_accepted_at` wird
   gesetzt; Login und Duplikatprüfung sind jetzt case-insensitiv.
10. **`safe_next_url` ließ `/\evil.example` durch** (Browser normalisieren zu
    `//evil.example`). Fix: `startswith(("//", "/\\"))`.
11. **Schema-Migration lief in jedem Gunicorn-Worker parallel** (Race bei
    `ALTER TABLE`). Fix: `fcntl.flock`-Sperre (`startup_lock`) um
    `create_all` + Migrationen + Abgleich.

Doku/Hilfe wurden für die geänderten Verhalten (Sync, Backup, API-Antwort)
angepasst; Service-Worker-Cache auf `motodb-v48`.

## Offene Punkte

### Betrieb (sofort, außerhalb des Repos)

- **`MOTODB_TRUST_PROXY_HEADERS=true` in `/srv/motorrad-service/.env.http`
  setzen** und den Container per `apply-config.sh` neu starten. Ohne diesen
  Wert gilt nur das E-Mail-basierte Login-Limit (Nginx limitiert `/login`
  zusätzlich mit 10 r/min).
- `MOTODB_ALLOW_REGISTRATION=true` im Heimnetz-Betrieb: jeder im Netz
  kann sich registrieren und 200 MB belegen. Bewusst entscheiden.
- `compose.yaml`/`deploy/update-on-pi.sh` beschreiben einen Compose-Betrieb,
  real läuft `docker run` + `.env.http` (Audit-Punkt aus dem Juni, weiterhin
  offen). Eine der beiden Varianten als verbindlich festlegen.

### Security (niedrig)

- Rate-Limit ist In-Memory und pro Worker (Juni-Punkt, unverändert).
- Kein Sitzungs-Timeout (bewusst verschoben, unverändert).
- Dokument-Kategorie wird nicht gegen `DOCUMENT_CATEGORIES` validiert;
  String-Längen werden von SQLite nicht erzwungen. Unkritisch.
- Der Sicherungsort ist ein frei wählbarer Serverpfad (nur Admin). Für
  Public Hosting auf ein festes Verzeichnis unterhalb `/data` einschränken.

### Inkonsistenzen und toter Code

- `Motorcycle.aktiv`: Model und `fill_motorcycle` unterstützen es, kein
  Formular bietet es an; README bewirbt „Aktive und verkaufte Motorräder
  verwalten“. Entweder Feld ins Formular oder aus README streichen.
- `index()` unterstützt `q`/`sort` ohne UI; `import_text`
  (Freitext/JSON-Import technischer Daten) wird verarbeitet, kommt in keinem
  Template vor, ist aber im README dokumentiert.
- `AuditLog` ohne Schreibstelle, `split_lines` ungenutzt, Legacy-Route
  `/motorrad/<id>/bild-loeschen` neben der Galerie-Route (Juni-Punkte).
- `disk_usage` wird per Context-Processor auf jeder Seite berechnet und in
  `admin_users` nochmals; genutzt nur in `admin/users.html`.
- Hilfetext „Motorrad anlegen“ nennt ein Kilometerstand-Feld, das Formular hat
  keines (Kilometerstand wird aus Services/Checklisten abgeleitet).
- `parse_int` streicht alle Nicht-Ziffern: `1.500,50` → `150050`. Die UI
  normalisiert sichtbar beim Verlassen des Felds, die API nicht. Beträge sind
  bewusst ganze Euro – in der Hilfe erwähnen.
- Service Worker: Fallback `caches.match("/")` kann nie treffen, da `/` nicht
  gecacht wird; nach Offline-Speichern wird auf eine nicht gecachte Seite
  umgeleitet. Manifest hat `icons: []` → PWA nicht installierbar.

### Veröffentlichung

- ~~Interne Daten im Repo~~ (behoben 2026-09-13: `run.py`, `README.md` und
  `deploy/README_RASPI.md` nutzen Platzhalter statt privater IPs/Benutzer).
- ~~README veraltet~~ (behoben 2026-09-13: requirements-Block, Farbschema,
  FAB, Einstellungen, Dokumente, Datenblatt-CSV, Konfig-Tabelle,
  Projektstruktur, Routen-Tabelle). Nicht vorhandene UI (`aktiv`, Suche,
  Freitext-Import) ist jetzt als solche gekennzeichnet statt beworben.
- **Fehlt:** `LICENSE`, CI (Tests laufen nur manuell; Dockerfile kopiert
  `tests/` nicht), `HEALTHCHECK` und non-root `USER` im Dockerfile.
- `run.py` startet mit `debug=True` (Werkzeug-Debugger = Remote-Code-Execution,
  falls jemand das produktiv nutzt). Aus `FLASK_DEBUG` lesen.
- `AUDIT_REPORT.md` für ein öffentliches Repo ggf. nach `docs/` verschieben
  oder kürzen.

## Empfohlene Reihenfolge

1. `.env.http` anpassen und Container neu bauen/starten (die Fixes aus diesem
   Audit sind erst nach `docker build` + `apply-config.sh` aktiv).
2. `LICENSE` ergänzen (README und interne IPs/Namen sind bereinigt).
3. Toten Code entfernen (`aktiv`, `import_text`, `AuditLog`, `split_lines`,
   Legacy-Bildroute, doppelte `disk_usage`).
4. Dockerfile: non-root User, `HEALTHCHECK`, Tests im Build ausführbar; CI.
5. PWA-Manifest-Icons und Service-Worker-Fallback.

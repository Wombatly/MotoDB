# MotoDB Audit-Report

Datum: 2026-05-25  
Umfang: Security, potenziell ungenutzter Code, verwaiste/inkonsistente Links und Dokumentation, Performance.

## Kurzfazit

Die App hat bereits einige gute Schutzmechanismen: CSRF ist aktiv und in den Formularen eingebunden, Uploads sind auf User-/Motorrad-Eigentum geprüft, Security-Header werden gesetzt, Public-Hosting erzwingt einen anderen `SECRET_KEY`, und die Tests decken zentrale Sicherheitsflüsse ab.

Die wichtigsten offenen Punkte liegen bei veralteten bzw. verwundbaren Dependencies, Datei-/PDF-Verarbeitung, einer wahrscheinlich unbeabsichtigten Offline-Submit-Logik und mehreren Skalierungsstellen durch vollständige Tabellen-/Dateibaum-Verarbeitung.

## Verifikation

- `python3 -m unittest tests.test_security`: 14 Tests OK.
- `PYTHONPYCACHEPREFIX=/private/tmp/motodb-pycache python3 -m compileall -q app tests`: OK.
- `python3 -m pytest -q`: nicht ausführbar, weil `pytest` in der lokalen Umgebung nicht installiert ist.
- OSV-Abfrage am 2026-05-25 über `https://api.osv.dev/v1/querybatch` für alle Pakete aus `requirements.txt`.
- Routenkarte per Flask-App-Factory mit temporärer Datenbank erzeugt.

## Security

### Hoch: Verwundbare Dependencies

Fundstelle: `requirements.txt:1`, `requirements.txt:5`, `requirements.txt:6`, `requirements.txt:8`

OSV meldet verwundbare Versionen:

- `Flask==3.0.3`: `GHSA-68rp-wp8r-4726` / `CVE-2026-27205`, fix laut Advisory ab `3.1.3`. Risiko vor allem bei Caching-Proxies ohne passende `Cache-Control`.
- `Werkzeug==3.0.3`: `GHSA-q34m-jh98-gwm2` / `CVE-2024-49767`, fix ab `3.0.6`. Relevant, weil MotoDB `multipart/form-data` Uploads verarbeitet.
- `Pillow==10.4.0`: mehrere Advisories, u. a. PSD/FITS/Font-DoS bzw. Speicherfehler; fixes laut OSV/Pillow-Advisories überwiegend ab `12.2.0`.
- `pypdf==5.7.0`: OSV meldet zahlreiche Advisories für diese Version. Das ist besonders relevant, weil PDFs serverseitig synchron im Request geparst werden.

Empfehlung: Dependencies aktualisieren, danach Upload-/PDF-Tests erneut laufen lassen. Mindestziel: `Flask>=3.1.3`, `Werkzeug>=3.0.6` oder aktueller 3.1.x-Zweig, `Pillow>=12.2.0`, `pypdf` auf aktuelle 6.x-Version prüfen. Quellen: [OSV API](https://osv.dev), [Flask Advisory](https://github.com/pallets/flask/security/advisories/GHSA-68rp-wp8r-4726), [Werkzeug Advisory](https://github.com/pallets/werkzeug/security/advisories/GHSA-q34m-jh98-gwm2), [Pillow 12.2.0 Release](https://github.com/python-pillow/Pillow/releases/tag/12.2.0).

### Hoch: Upload-Typprüfung basiert nur auf Dateiendung

Fundstelle: `app/utils.py:470` bis `app/utils.py:490`

`save_upload` akzeptiert Dateien anhand der Endung. Für Bilder wird anschließend `Image.open(path)` aufgerufen. Eine Datei mit `.jpg`-Endung kann trotzdem ein anderes Format enthalten; bei verwundbaren Pillow-Versionen kann das genau die betroffenen Decoder erreichen. Außerdem bleiben ungültige Bilddateien liegen, wenn `optimize_image` eine Exception schluckt.

Empfehlung: Bildinhalt per Pillow verifizieren und explizit nur `JPEG`, `PNG`, `WEBP` erlauben, z. B. mit `Image.open(..., formats=(...))`, danach erst final speichern. Für PDFs mindestens Magic-Header und Größen-/Seitenlimits prüfen.

### Mittel: Bildoptimierung speichert immer JPEG unter alter Endung

Fundstelle: `app/utils.py:484`, `app/utils.py:494` bis `app/utils.py:504`; Dokumentation in `README.md:568` bis `README.md:573`

Bei `.png` oder `.webp` bleibt der Dateiname unverändert, aber `optimize_image` schreibt JPEG-Inhalt in dieselbe Datei. Mit `X-Content-Type-Options: nosniff` kann der Browser die Datei als falschen MIME-Typ behandeln. Das kann Bilder brechen und erschwert Debugging.

Empfehlung: Entweder wirklich im Ursprungsformat speichern oder beim Konvertieren Dateiendung/Pfad auf `.jpg` ändern und DB-Pfad entsprechend setzen.

### Mittel: PDF-Parsing ist synchron und unlimitiert

Fundstelle: `app/utils.py:344` bis `app/utils.py:380`

Checklisten-Punktelisten können als PDF hochgeladen werden. Der Code liest die komplette Datei in den Speicher, erstellt einen `PdfReader` und iteriert über alle Seiten ohne Seitenlimit, Textlimit oder Timeout. Zusammen mit den pypdf-Advisories ist das ein DoS-Risiko.

Empfehlung: PDF-Import begrenzen: maximale Dateigröße deutlich unter globalem Upload-Limit, maximale Seitenanzahl, maximale extrahierte Zeichen, Abbruch bei verschlüsselten/kaputten PDFs. Optional PDF-Parsing in einen Hintergrundjob mit Timeout verschieben.

### Mittel: Login-Rate-Limit nur in Nginx-Konfig, nicht in der App

Fundstelle: `deploy/nginx/motorrad-service.conf:1`, `deploy/nginx/motorrad-service.conf:18` bis `deploy/nginx/motorrad-service.conf:30`; Login in `app/auth.py:107` bis `app/auth.py:130`

Die Nginx-Konfig limitiert `/login` und `/register`. Wer die Flask-App direkt betreibt oder eine andere Proxy-Konfig nutzt, hat kein App-seitiges Rate-Limit.

Empfehlung: App-seitig Rate-Limiting ergänzen, z. B. pro IP/E-Mail auf `/login`, oder die Produktionsanforderung klar als Deployment-Check dokumentieren.

### Niedrig: Offene Referrer-Weiterleitung nach Admin-POST

Fundstelle: `app/routes.py:243` bis `app/routes.py:253`

`backup_path_update` leitet auf `request.referrer` zurück. Mit gültigem CSRF-Token ist das praktisch nur für angemeldete Admin-Flüsse relevant, aber ein fester interner Redirect wäre robuster.

Empfehlung: Nach `url_for("main.settings")` oder validiertem Same-Origin-Referrer weiterleiten.

### Niedrig: ProxyFix ist per Compose dauerhaft aktiv

Fundstelle: `compose.yaml:13`, `compose.yaml:17`; `app/__init__.py:71` bis `app/__init__.py:72`

`MOTODB_TRUST_PROXY_HEADERS` ist im Compose-Setup aktiv. Der Port ist zwar nur auf `127.0.0.1` gebunden, daher passt das für das dokumentierte Nginx-Setup. Falls diese Bindung später gelockert wird, könnten direkte Clients Forwarded-Header fälschen.

Empfehlung: In Deployment-Doku als Sicherheitsannahme festhalten: App-Port nie direkt öffentlich exponieren, wenn Proxy-Header vertraut werden.

## Potenziell ungenutzter oder verwaister Code

### `AuditLog` ist definiert, aber nicht verwendet

Fundstelle: `app/models.py:32` bis `app/models.py:39`

Es gibt ein Audit-Log-Modell und eine Beziehung am User, aber keine Schreibstellen. Das ist entweder ein unfertiges Feature oder toter Code.

Empfehlung: Entweder echte Audit-Events für Admin- und Löschaktionen schreiben oder Modell entfernen.

### Alte Bild-Löschroute ohne UI-Nutzung

Fundstelle: `app/routes.py:493` bis `app/routes.py:510`; aktuelle Gallery-Forms in `app/templates/motorcycles/form.html:162` bis `app/templates/motorcycles/form.html:170`

`/motorrad/<id>/bild-loeschen` scheint durch die Galerie-spezifische Route ersetzt worden zu sein. In den Templates wird sie nicht mehr verlinkt.

Empfehlung: Falls keine alten Clients diese Route brauchen, entfernen oder als Legacy-Kompatibilität dokumentieren.

### Service-Löschroute ohne sichtbaren Link/Button

Fundstelle: `app/routes.py:740` bis `app/routes.py:753`

`service_delete` existiert, aber im Service-Formular ist kein Löschbutton vorhanden. Dadurch ist die Route technisch erreichbar, aber für Nutzer praktisch verwaist.

Empfehlung: Entweder UI ergänzen oder Route entfernen.

### Nicht genutzte Menü-JS-Logik

Fundstelle: `app/static/js/app.js:17` bis `app/static/js/app.js:30`

Die Selektoren `[data-menu-toggle]` und `[data-menu]` kommen in den Templates nicht vor. Dieser Block wirkt wie Restcode aus einer früheren Navigation.

Empfehlung: Entfernen, wenn keine geplante Navigation mehr darauf aufbaut.

### `split_lines` wird nicht aufgerufen

Fundstelle: `app/routes.py:1057` bis `app/routes.py:1058`

Die Funktion ist statisch im Projekt nicht referenziert.

Empfehlung: Entfernen oder in den passenden Parser verschieben, falls sie geplant ist.

### API-Endpunkte wirken first-party ungenutzt

Fundstelle: `app/routes.py:781` bis `app/routes.py:841`

`/api/motorcycles`, `/api/motorcycles/<id>/services` und `/api/services` werden von den aktuellen statischen JS-Dateien nicht verwendet; nur `/api/sync` wird aktiv benutzt.

Empfehlung: Wenn die API öffentlich für externe Clients gedacht ist, dokumentieren und testen. Falls nicht, entfernen oder hinter denselben Nutzungspfad wie Sync legen.

## Verwaiste Links und Inkonsistenzen

### Keine kaputten internen Template-Links gefunden

Alle geprüften `url_for(...)`-Aufrufe passen zu registrierten Flask-Routen. Auch statische Dateien wie `/manifest.webmanifest`, `/service-worker.js`, CSS und JS sind als Routen bzw. Dateien vorhanden.

### Service-Worker-Fallback verweist auf nicht gecachte Startseite

Fundstelle: `app/static/service-worker.js:2` bis `app/static/service-worker.js:8`, `app/static/service-worker.js:43`

Der Fallback nutzt `caches.match("/")`, aber `/` ist nicht in `APP_SHELL` enthalten und dynamische Seiten werden nicht gecacht. Offline-Fallbacks für App-Shell-Requests können daher leer ausgehen.

Empfehlung: Entweder `/` bewusst cachen oder auf eine eigene Offline-Seite/ein echtes Shell-Dokument umstellen.

### README beschreibt technische CSV-Vorlage anders als der Code

Fundstelle: `README.md:398` bis `README.md:410`; Code-Vorlage in `app/routes.py:102` bis `app/routes.py:111`; Tests erwarten ohne `Quelle`.

Die README zeigt eine technische CSV mit Spalte `Quelle`, die ausgelieferte Vorlage enthält aktuell nur `Kategorie;Eintrag;Wert;Einheit`. Der Parser kann zwar eine fünfte Spalte verarbeiten, aber Vorlage, Test und README sind nicht deckungsgleich.

Empfehlung: Entscheiden, ob `Quelle` offiziell Teil der Vorlage sein soll. Dann Code/Test/README angleichen.

### Upload-Limit ist zwischen Flask und Nginx unterschiedlich

Fundstelle: `app/__init__.py:46`, `deploy/nginx/motorrad-service.conf:7`

Flask erlaubt 64 MB, Nginx nur 32 MB. Das führt im Deployment zu anderem Verhalten als lokal.

Empfehlung: Limits angleichen und in README dokumentieren.

## Performance und Skalierung

### Motorrad-Detail lädt komplette Service-Historie

Fundstelle: `app/routes.py:433` bis `app/routes.py:445`

Die Detailseite lädt alle Services und alle technischen Daten. Bei langer Historie wird die Seite schwerer und die Kostenaggregation passiert in Python.

Empfehlung: Historie paginieren oder begrenzen, Kostenaggregation per SQL berechnen.

### Kilometerstand-Ermittlung lädt alle Kandidaten

Fundstelle: `app/routes.py:963` bis `app/routes.py:986`

`latest_service_mileage` lädt alle Service- und Checklistendatensätze und berechnet das Maximum in Python. Die Funktion wird bei Detail-/Edit-Aufrufen und nach Mutationen genutzt.

Empfehlung: Per SQL sortieren/limitieren oder einen denormalisierten aktuellen Kilometerstand gezielt bei Schreiboperationen aktualisieren.

### User-Export erzeugt N+1-Abfragen und komplettes ZIP im RAM

Fundstelle: `app/auth.py:177` bis `app/auth.py:390`

Für jedes Motorrad werden Bilder, Services, Dokumente, Specs und Checklisten separat abgefragt; Checklisten-Items werden über Lazy Loading nachgeladen. Das ZIP entsteht vollständig in `BytesIO`.

Empfehlung: Beziehungen eager-loaden (`selectinload`) und bei großen Exports Streaming oder temporäre Dateien nutzen.

### Sync-Backup kopiert kompletten Upload-Baum vor jedem Sync

Fundstelle: `app/routes.py:1385` bis `app/routes.py:1401`

Vor jedem erfolgreichen Sync wird bei gesetztem Backup-Pfad die SQLite-Datei und der komplette Upload-Ordner kopiert. Bei vielen Bildern/PDFs blockiert das den Request und verbraucht schnell Speicherplatz.

Empfehlung: Backups entkoppeln, inkrementell arbeiten oder nach Zeit/Größe drosseln.

### Neue Service-Formulare werden immer offline gespeichert

Fundstelle: `app/templates/service/form.html:13`, `app/static/js/sync.js:67` bis `app/static/js/sync.js:72`

Das JS verhindert das normale Submit für neue Services immer und schreibt den Eintrag in IndexedDB. Auch online wird erst später über Sync an den Server übertragen. Belege werden dabei entfernt (`app/static/js/sync.js:43`).

Empfehlung: Online normal per POST speichern und nur bei fehlender Verbindung/offline explizit in IndexedDB fallen. Beleg-Uploads für Offline-Flows entweder deaktivieren oder klar markieren.

### Disk-Usage wird global in Templates injiziert

Fundstelle: `app/routes.py:144` bis `app/routes.py:148`, `app/routes.py:1368` bis `app/routes.py:1382`

`get_disk_usage()` wird über den Context Processor grundsätzlich verfügbar gemacht. Je nach Template-Nutzung kann das unnötige `shutil.disk_usage`-Aufrufe auf normalen Seiten auslösen.

Empfehlung: Disk-Usage nur auf Admin-/Settings-Seiten laden, wo sie wirklich angezeigt wird.

## Wartbarkeit

### `routes.py` ist sehr groß

Fundstelle: `app/routes.py` mit 1403 Zeilen.

Die Datei mischt Views, API, Importlogik, Backup, Upload-Helfer und Business-Logik. Das erschwert gezielte Tests und Review.

Empfehlung: Schrittweise aufteilen: `views/motorcycles.py`, `views/checklists.py`, `views/api.py`, `services/uploads.py`, `services/backups.py`, `services/mileage.py`.

### Manuelle Schema-Migrationen

Fundstelle: `app/__init__.py:146` bis `app/__init__.py:205`

`ensure_schema_updates` führt Migrationen per Raw SQL beim Start aus. Für kleine SQLite-Deployments ist das pragmatisch, aber bei mehr Änderungen riskant und schwer rückrollbar.

Empfehlung: Ab einer nächsten größeren Änderung Flask-Migrate/Alembic oder zumindest versionierte Migrationsschritte einführen.

### SQLAlchemy Legacy-Warnungen

Beim Testlauf erschienen `LegacyAPIWarning`-Meldungen für `Query.get()`.

Fundstellen u. a.: `app/__init__.py:85`, `app/routes.py:247`, `app/routes.py:807`, `app/routes.py:820`

Empfehlung: Schrittweise auf `db.session.get(Model, id)` umstellen.

## Empfohlene Reihenfolge

1. Dependencies aktualisieren und Upload-/PDF-Regressionstests laufen lassen.
2. Upload-Validierung härten: echte MIME-/Formatprüfung, PDF-Limits, Bild-Endung korrigieren.
3. Offline-Service-Submit korrigieren, damit Online-Speichern wieder direkt serverseitig passiert.
4. Verwaiste Routen/JS-Blöcke bereinigen oder bewusst dokumentieren.
5. Performance-Hotspots angehen: Detail-Historie, `latest_service_mileage`, Export und Sync-Backup.
6. README/Deployment-Inkonsistenzen angleichen.

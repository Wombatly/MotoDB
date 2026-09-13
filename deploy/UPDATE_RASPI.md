# MotoDB auf dem Raspberry Pi aktualisieren

Diese Anleitung aktualisiert nur den App-Code. Datenbank, Uploads und Backups
bleiben in `/srv/motorrad-service/data` erhalten.

## Variante A: Pi-App ist ein Git-Checkout

Auf dem Raspberry Pi:

```bash
cd /srv/motorrad-service/app
docker compose down
git fetch origin
git reset --hard origin/main
docker compose up -d --build
docker compose ps
```

Logs prüfen:

```bash
docker compose logs -f
```

## Variante B: App-Ordner komplett ersetzen

Nutze diese Variante, wenn `/srv/motorrad-service/app` kein Git-Checkout ist.

Auf dem Raspberry Pi:

```bash
cd /srv/motorrad-service
docker compose -f app/compose.yaml down
mv app app.backup.$(date +%Y%m%d-%H%M%S)
git clone https://github.com/Wombatly/MotoDB.git app
cd app
cp ../app.backup.*/.env .env 2>/dev/null || true
docker compose up -d --build
docker compose ps
```

Logs prüfen:

```bash
docker compose logs -f
```

## Schnelltest

```bash
curl -I http://127.0.0.1:5001
```

Im Heimnetz anschließend die normale MotoDB-Adresse öffnen.

## Einmalig: Daten-Volume für den Nicht-Root-Container

Seit 2026-09 läuft der Container als Benutzer `motodb` (UID/GID 1000). Vor dem
ersten Start der neuen Version müssen alle Dateien im Daten-Volume dieser UID
gehören (Dateien, die ein früherer Root-Container angelegt hat, gehören noch
`root`):

```bash
docker run --rm -v /srv/motorrad-service/data:/data alpine chown -R 1000:1000 /data
```

Danach zeigt `docker ps` den Container nach ca. 20 s als `healthy`.

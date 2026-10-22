# MotoDB auf dem Raspberry Pi aktualisieren

Diese Anleitung aktualisiert nur den App-Code. Datenbank, Uploads und Backups
bleiben in `/srv/motorrad-service/data` erhalten.

## Vor jedem Update: Sicherung

Datenbank über die SQLite-Backup-API kopieren (konsistent auch bei laufendem
Container), Environment-Datei dazulegen und das bisherige Image für einen
Rollback markieren:

```bash
TS=$(date +%Y%m%d_%H%M%S)
B=/srv/motorrad-service/data/backups/pre-update_$TS
mkdir -p "$B"
python3 -c 'import sqlite3, sys; s = sqlite3.connect("file:/srv/motorrad-service/data/motorcycle_service.sqlite3?mode=ro", uri=True); d = sqlite3.connect(sys.argv[1]); s.backup(d); print(d.execute("PRAGMA integrity_check").fetchone()[0])' "$B/motorcycle_service.sqlite3"
cp -p /srv/motorrad-service/app/.env "$B/env" && chmod 600 "$B/env"
git -C /srv/motorrad-service/app rev-parse --short HEAD > "$B/INFO.txt"
docker tag app-motorrad-service app-motorrad-service:pre-update-$TS
```

Die Integritätsprüfung muss `ok` ausgeben. Läuft der Container per
`docker run` mit eigener env-Datei (z. B. `.env.http`), diese statt `.env`
sichern. Uploads werden beim Update nicht angefasst und brauchen keine Kopie.

## Variante A: Pi-App ist ein Git-Checkout

Auf dem Raspberry Pi:

```bash
cd /srv/motorrad-service/app
docker compose down
git fetch origin
git reset --hard origin/main
docker compose build --pull
docker compose up -d
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

`--pull` holt auch ein neues Python-Basis-Image (z. B. beim Wechsel von
3.12 auf 3.14 im Oktober 2026); ein zusätzlicher Schritt ist dafür nicht nötig.

## Schnelltest

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/health
docker ps --format '{{.Names}}\t{{.Status}}'
```

`/health` muss `200` liefern, der Container nach ca. 20 s `healthy` sein. Im
Heimnetz anschließend die normale MotoDB-Adresse öffnen.

## Rollback

Startet die neue Version nicht sauber, das markierte Image zurückholen und
den Container neu erstellen:

```bash
docker tag app-motorrad-service:pre-update-<TS> app-motorrad-service
docker compose up -d --no-build
```

Hat die neue Version die Datenbank bereits verändert, vorher die Sicherung
zurückkopieren (Container gestoppt):

```bash
cp /srv/motorrad-service/data/backups/pre-update_<TS>/motorcycle_service.sqlite3 /srv/motorrad-service/data/
```

Ältere Rollback-Tags aufräumen, sobald die neue Version ein paar Tage läuft:
`docker image ls app-motorrad-service` und `docker rmi app-motorrad-service:pre-update-<TS>`.

## Pi-System und Portainer aktualisieren

Unabhängig von App-Updates regelmäßig (etwa monatlich) die Systempakete
einspielen. Die Container starten nach dem Neustart über ihre Restart-Policy
von selbst:

```bash
sudo apt update
sudo apt full-upgrade
sudo reboot
```

Danach prüfen, ob noch etwas aussteht (`apt list --upgradable`,
`ls /var/run/reboot-required`) und den Schnelltest oben ausführen.

Portainer hat Zugriff auf den Docker-Socket und damit root-Rechte auf dem Pi;
es sollte daher aktuell gehalten und nur an die Tailscale-IP gebunden werden.
Update mit Sicherung des Daten-Volumes:

```bash
TS=$(date +%Y%m%d_%H%M%S)
docker run --rm -v portainer_data:/data:ro -v /srv/motorrad-service/data/backups:/backup alpine \
  sh -c "tar czf /backup/portainer_data_$TS.tar.gz -C /data . && chown 1000:1000 /backup/portainer_data_$TS.tar.gz && chmod 600 /backup/portainer_data_$TS.tar.gz"
docker tag portainer/portainer-ce:latest portainer/portainer-ce:pre-update-$TS
docker pull portainer/portainer-ce:latest
docker stop portainer && docker rm portainer
docker run -d --name portainer --restart=always -p <tailscale-ip>:9443:9443 \
  -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data \
  portainer/portainer-ce:latest
curl -sk https://<tailscale-ip>:9443/api/system/status
```

Die Antwort zeigt die neue Version; die `InstanceID` muss gleich bleiben
(sonst wurde das Volume nicht übernommen). Portainer migriert seine Datenbank
beim ersten Start, ein Rollback auf das alte Image braucht deshalb zusätzlich
die Volume-Sicherung.

## Einmalig: Daten-Volume für den Nicht-Root-Container

Seit 2026-09 läuft der Container als Benutzer `motodb` (UID/GID 1000). Vor dem
ersten Start der neuen Version müssen alle Dateien im Daten-Volume dieser UID
gehören (Dateien, die ein früherer Root-Container angelegt hat, gehören noch
`root`):

```bash
docker run --rm -v /srv/motorrad-service/data:/data alpine chown -R 1000:1000 /data
```

Danach zeigt `docker ps` den Container nach ca. 20 s als `healthy`.

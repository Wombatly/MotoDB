# Motorrad Service auf Raspberry Pi 4B

Zielsystem: Debian 13 `trixie`, `aarch64`, Benutzer `gregor`, Host `rabbithole`.

## 1. Grundsystem

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Danach neu per SSH einloggen.

```bash
sudo apt install -y ca-certificates curl git rsync nano nginx ufw
```

## 2. Docker installieren

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker gregor
```

Einmal abmelden und neu anmelden. Test:

```bash
docker run hello-world
```

### Memory-Cgroups aktivieren

Raspberry Pi OS deaktiviert den Memory-Controller des Kernels standardmäßig.
Ohne ihn zeigt `docker stats` für alle Container `0B` Speicher an und
RAM-Limits für Container (z. B. `--memory`) werden ignoriert. Aktivieren:

```bash
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.backup
sudo sed -i '1s/$/ cgroup_enable=memory cgroup_memory=1/' /boot/firmware/cmdline.txt
sudo reboot
```

Wichtig: `cmdline.txt` muss eine einzige Zeile bleiben, die Parameter werden
am Zeilenende angehängt.

Nach dem Neustart prüfen:

```bash
cat /sys/fs/cgroup/cgroup.controllers   # muss "memory" enthalten
docker stats --no-stream                # zeigt jetzt echte RAM-Werte
```

## 3. Server-Verzeichnisse

```bash
sudo mkdir -p /srv/motorrad-service/app
sudo mkdir -p /srv/motorrad-service/data/uploads
sudo mkdir -p /srv/motorrad-service/data/backups
sudo chown -R gregor:gregor /srv/motorrad-service
```

## 4. App auf den Pi kopieren

Vom Mac aus im Projektordner:

```bash
rsync -av --delete \
  --exclude ".git" \
  --exclude ".DS_Store" \
  --exclude "__pycache__" \
  --exclude "instance" \
  ./ gregor@192.168.178.102:/srv/motorrad-service/app/
```

## 5. Bestehende Daten migrieren

Vom Mac aus im Projektordner:

```bash
rsync -av instance/motorcycle_service.sqlite3 gregor@192.168.178.102:/srv/motorrad-service/data/
rsync -av instance/uploads/ gregor@192.168.178.102:/srv/motorrad-service/data/uploads/
```

## 6. Environment-Datei auf dem Pi

Auf dem Pi:

```bash
cd /srv/motorrad-service/app
cp .env.example .env
nano .env
```

`SECRET_KEY` durch einen langen zufälligen Wert ersetzen.

Beispiel zum Erzeugen:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Wenn diese Instanz öffentlich über HTTPS erreichbar sein soll, zusätzlich in
`.env` setzen:

```env
MOTODB_PUBLIC_HOSTING=true
MOTODB_TRUST_PROXY_HEADERS=true
MOTODB_ADMIN_USERNAME=admin
MOTODB_ADMIN_EMAIL=admin@example.com
MOTODB_ADMIN_PASSWORD=bitte-mindestens-12-zeichen
```

Die drei `MOTODB_ADMIN_*` Werte werden nur für den ersten Admin einer neuen
Datenbank benötigt. Öffentliche Selbstregistrierung bleibt im Public-Hosting-
Modus deaktiviert, solange `MOTODB_ALLOW_REGISTRATION=true` nicht bewusst
gesetzt wird.

Wenn die Pi-Instanz im Heimnetz nur über HTTP erreichbar ist, die Public-
Hosting-Zeilen auskommentiert lassen. Sonst werden die sicheren Session-Cookies
vom Browser nicht gespeichert und der Login kann nicht abgeschlossen werden.

## 7. Container starten

```bash
cd /srv/motorrad-service/app
docker compose up -d --build
docker compose logs -f
```

App intern prüfen:

```bash
curl -I http://127.0.0.1:5001
```

## 8. Nginx einrichten

```bash
sudo cp /srv/motorrad-service/app/deploy/nginx/motorrad-service.conf /etc/nginx/sites-available/motorrad-service.conf
sudo ln -sf /etc/nginx/sites-available/motorrad-service.conf /etc/nginx/sites-enabled/motorrad-service.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Danach im Heimnetz öffnen:

```text
http://192.168.178.102/
```

Diese HTTP-Adresse ist für den Heimnetz-Betrieb ohne
`MOTODB_PUBLIC_HOSTING=true` gedacht. Für Public Hosting muss die externe URL
über HTTPS bereitstehen.

## 9. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 10. App-Backup-Pfad

In der App unter `Menü > Einstellungen` diesen Sicherungsort eintragen:

```text
/data/backups
```

Im Container entspricht das auf dem Pi:

```text
/srv/motorrad-service/data/backups
```

## 11. Updates einspielen

Vom Mac wieder per `rsync` kopieren, dann auf dem Pi:

```bash
cd /srv/motorrad-service/app
docker compose up -d --build
```

## 12. Nützliche Befehle

```bash
docker compose ps
docker compose logs -f
docker compose restart
docker compose down
```

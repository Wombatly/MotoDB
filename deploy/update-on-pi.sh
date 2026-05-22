#!/usr/bin/env bash
set -euo pipefail

cd /srv/motorrad-service/app
docker compose up -d --build
docker compose ps

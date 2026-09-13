# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

# --- Test-Stage: `docker build --target test .` fuehrt die Tests im Image aus ---
FROM base AS test
RUN pip install --no-cache-dir pyflakes
COPY tests ./tests
RUN python -m pyflakes app run.py tests \
    && python -m unittest discover -s tests -t .

# --- Runtime-Stage (Standardziel) ---
FROM base AS runtime

# Nicht als root laufen. UID/GID 1000 entspricht dem Standard-Benutzer auf dem
# Pi, damit die Dateien im Daten-Volume auch auf dem Host lesbar bleiben.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" motodb \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /usr/sbin/nologin motodb \
    && mkdir -p /data/uploads \
    && chown -R motodb:motodb /data

USER motodb

# Laufzeitdaten liegen im Volume /data; env-file oder Compose koennen die
# Werte weiterhin ueberschreiben.
ENV MOTORRAD_INSTANCE_PATH=/data \
    MOTORRAD_UPLOAD_FOLDER=/data/uploads \
    DATABASE_URL=sqlite:////data/motorcycle_service.sqlite3

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5001/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "4", "--timeout", "120", "run:app"]

FROM python:3.12-slim

LABEL maintainer="LRC Checker"
LABEL description="Verificador de archivos .lrc con sincronización real contra audio"

WORKDIR /app

# Instalar mutagen para extraer duración de archivos de audio
RUN pip install --no-cache-dir mutagen

COPY version_servidor/lrc_checker_server.py /app/lrc_checker.py

# Crear directorios
RUN mkdir -p /music /reports

# Script de entrada que ejecuta el checker en loop con intervalo configurable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV MUSIC_DIR=/music
ENV OUTPUT_DIR=/reports
ENV INTERVAL_MINUTES=60
ENV SYNC_TOLERANCE_SEC=5.0
ENV CHECK_ORPHANS=true
ENV VERBOSE=true

ENTRYPOINT ["/entrypoint.sh"]

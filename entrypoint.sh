#!/bin/sh
set -e

# Script de entrada del contenedor LRC Checker v4 (modo servidor, bajo demanda)
#
# CAMBIO IMPORTANTE respecto a versiones anteriores: ya NO hay un loop que
# re-escanea cada INTERVAL_MINUTES. Ahora el contenedor hace UN escaneo
# inicial al arrancar y después queda corriendo el servidor HTTP que atiende
# los botones "Reparar" y "Escanear ahora" del reporte HTML. Si querés volver
# a tener escaneos periódicos automáticos, hay que agregarlo aparte (por
# ejemplo, un cron externo que le pegue a POST /escanear) — no está incluido.

echo "========================================"
echo "  LRC Checker v4 (modo servidor)"
echo "========================================"
echo "Directorio de música: $MUSIC_DIR"
echo "Directorio de reportes: $OUTPUT_DIR"
echo "Tolerancia de sync: ${SYNC_TOLERANCE_SEC:-5.0} segundos"
echo "Umbral de revisión (posible outro): ${REVIEW_THRESHOLD_SEC:-60.0} segundos"
echo "Verificar huérfanos: $CHECK_ORPHANS"
echo "Verbose: $VERBOSE"
echo "URL pública del servidor (para los botones del HTML): ${SERVER_URL:-http://localhost:8080}"
echo "========================================"

if [ -z "$SERVER_URL" ]; then
    echo "ADVERTENCIA: no configuraste SERVER_URL. El botón Reparar va a usar"
    echo "http://localhost:8080, que solo funciona si abrís el HTML desde la"
    echo "misma máquina donde corre este contenedor. Si abrís el reporte por"
    echo "SMB/red desde otra PC, configurá SERVER_URL con la IP o hostname"
    echo "real de este servidor, por ejemplo: http://192.168.1.50:8080"
fi

# Validar que el directorio de música existe
if [ ! -d "$MUSIC_DIR" ]; then
    echo "ERROR: El directorio de música '$MUSIC_DIR' no existe."
    echo "Asegúrate de montar el volumen correctamente en docker-compose."
    exit 1
fi

# Armamos los argumentos con "set --" (positional params) en vez de una
# variable de texto: si concatenáramos strings y expandiéramos sin comillas,
# un valor con espacios (como SIGNED_MARKER="Oct4vyus Kandle") se partiría
# en dos argumentos sueltos por el word-splitting del shell. "set --" preserva
# cada argumento como una unidad, tenga o no espacios.
set -- "$MUSIC_DIR" --html --json -o "$OUTPUT_DIR" \
    --server-url "${SERVER_URL:-http://localhost:8080}" \
    --tolerance "${SYNC_TOLERANCE_SEC:-5.0}" \
    --review-threshold "${REVIEW_THRESHOLD_SEC:-60.0}" \
    --exit-zero --serve

if [ -n "$SIGNED_MARKER" ]; then
    set -- "$@" --signed-marker "$SIGNED_MARKER"
fi

if [ "$VERBOSE" = "true" ]; then
    set -- "$@" --verbose
fi

if [ "$CHECK_ORPHANS" != "true" ]; then
    set -- "$@" --no-orphans
fi

# --serve hace el escaneo inicial, genera los reportes, y luego se queda
# corriendo el servidor HTTP (no vuelve al shell).
exec python /app/lrc_checker.py "$@"

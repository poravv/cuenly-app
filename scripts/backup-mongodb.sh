#!/bin/bash
# =============================================================================
# MongoDB Backup Script — CuenlyApp
# Ejecutar con cron o como CronJob de Kubernetes.
# Variables de entorno requeridas:
#   MONGODB_URL — URI de conexión a MongoDB
#   BACKUP_DIR — Directorio destino (default: /backups)
#   BACKUP_RETENTION_DAYS — Días de retención (default: 7)
# =============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/mongodb_${TIMESTAMP}"

echo "[$(date)] Iniciando backup de MongoDB..."

# Verificar MONGODB_URL
if [ -z "${MONGODB_URL:-}" ]; then
    echo "[ERROR] MONGODB_URL no configurado"
    exit 1
fi

# Crear directorio si no existe
mkdir -p "${BACKUP_DIR}"

# Ejecutar mongodump
mongodump --uri="${MONGODB_URL}" --out="${BACKUP_PATH}" --gzip 2>&1

if [ $? -eq 0 ]; then
    echo "[OK] Backup completado: ${BACKUP_PATH}"

    # Calcular tamaño
    SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
    echo "[INFO] Tamaño del backup: ${SIZE}"
else
    echo "[ERROR] Backup fallido"
    exit 1
fi

# Limpiar backups antiguos
echo "[INFO] Limpiando backups con más de ${RETENTION_DAYS} días..."
find "${BACKUP_DIR}" -name "mongodb_*" -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} + 2>/dev/null || true

REMAINING=$(ls -d "${BACKUP_DIR}"/mongodb_* 2>/dev/null | wc -l)
echo "[INFO] Backups disponibles: ${REMAINING}"
echo "[$(date)] Backup finalizado exitosamente."

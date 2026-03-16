#!/bin/sh
# SupplyShock — Daily database backup
# Runs inside the backup container at 03:00 UTC
# Uploads to S3-compatible object storage

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="supplyshock_${DATE}.sql.gz"
TEMP_FILE="/tmp/${BACKUP_FILE}"
LOCAL_BACKUP_DIR="/backups"

echo "[backup] Starting backup: ${DATE}"

# Dump and compress
pg_dump -h db -U "${POSTGRES_USER:-supplyshock}" supplyshock | gzip > "${TEMP_FILE}"
SIZE=$(du -sh "${TEMP_FILE}" | cut -f1)
echo "[backup] Dump complete: ${SIZE}"

# Always keep a local copy
mkdir -p "${LOCAL_BACKUP_DIR}"
cp "${TEMP_FILE}" "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}"
echo "[backup] Local copy saved: ${LOCAL_BACKUP_DIR}/${BACKUP_FILE}"

# Upload to S3 if aws cli is available and bucket is configured
if command -v aws > /dev/null 2>&1 && [ -n "${BACKUP_S3_BUCKET}" ]; then
  aws s3 cp "${TEMP_FILE}" \
    "s3://${BACKUP_S3_BUCKET}/${BACKUP_FILE}" \
    --endpoint-url "${BACKUP_S3_ENDPOINT}" \
    --region auto
  echo "[backup] Uploaded to S3: ${BACKUP_FILE}"

  # Delete remote backups older than 7 days
  CUTOFF=$(date -d '7 days ago' +%Y%m%d 2>/dev/null || date -v-7d +%Y%m%d)
  aws s3 ls "s3://${BACKUP_S3_BUCKET}/" \
    --endpoint-url "${BACKUP_S3_ENDPOINT}" | \
    awk '{print $4}' | \
    while read -r file; do
      FILE_DATE=$(echo "${file}" | grep -o '[0-9]\{8\}' | head -1)
      if [ -n "${FILE_DATE}" ] && [ "${FILE_DATE}" -lt "${CUTOFF}" ]; then
        aws s3 rm "s3://${BACKUP_S3_BUCKET}/${file}" \
          --endpoint-url "${BACKUP_S3_ENDPOINT}"
        echo "[backup] Deleted old remote backup: ${file}"
      fi
    done
else
  echo "[backup] S3 not configured or aws cli missing — local backup only"
fi

# Delete local backups older than 14 days
find "${LOCAL_BACKUP_DIR}" -name "supplyshock_*.sql.gz" -mtime +14 -delete 2>/dev/null || true

# Cleanup temp file
rm -f "${TEMP_FILE}"

echo "[backup] Done"

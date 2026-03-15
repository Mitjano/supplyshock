#!/bin/sh
# SupplyShock — Daily database backup
# Runs inside the backup container at 03:00 UTC
# Uploads to S3-compatible object storage

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="supplyshock_${DATE}.sql.gz"
TEMP_FILE="/tmp/${BACKUP_FILE}"

echo "[backup] Starting backup: ${DATE}"

# Dump and compress
pg_dump -h db -U "${POSTGRES_USER:-supplyshock}" supplyshock | gzip > "${TEMP_FILE}"
SIZE=$(du -sh "${TEMP_FILE}" | cut -f1)
echo "[backup] Dump complete: ${SIZE}"

# Upload to S3 (using aws cli or mc)
if command -v aws > /dev/null 2>&1; then
  aws s3 cp "${TEMP_FILE}" \
    "s3://${BACKUP_S3_BUCKET}/${BACKUP_FILE}" \
    --endpoint-url "${BACKUP_S3_ENDPOINT}" \
    --region auto
  echo "[backup] Uploaded to S3: ${BACKUP_FILE}"
else
  echo "[backup] WARNING: aws cli not found, backup saved locally only"
fi

# Cleanup temp file
rm -f "${TEMP_FILE}"

# Delete backups older than 7 days
if command -v aws > /dev/null 2>&1; then
  CUTOFF=$(date -d '7 days ago' +%Y%m%d 2>/dev/null || date -v-7d +%Y%m%d)
  aws s3 ls "s3://${BACKUP_S3_BUCKET}/" \
    --endpoint-url "${BACKUP_S3_ENDPOINT}" | \
    awk '{print $4}' | \
    while read -r file; do
      FILE_DATE=$(echo "${file}" | grep -o '[0-9]\{8\}' | head -1)
      if [ -n "${FILE_DATE}" ] && [ "${FILE_DATE}" -lt "${CUTOFF}" ]; then
        aws s3 rm "s3://${BACKUP_S3_BUCKET}/${file}" \
          --endpoint-url "${BACKUP_S3_ENDPOINT}"
        echo "[backup] Deleted old backup: ${file}"
      fi
    done
fi

echo "[backup] Done"

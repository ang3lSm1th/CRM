#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./deploy/backup_databases.sh [output_dir] [env_file]
#
# Defaults:
#   output_dir = ./backups/<YYYYmmdd_HHMMSS>
#   env_file   = ./.env

OUTPUT_DIR="${1:-./backups/$(date +%Y%m%d_%H%M%S)}"
ENV_FILE="${2:-./.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DB="${MYSQL_DB:-u349183440_crm_orbes}"

TRACTOR_DB_HOST="${TRACTOR_DB_HOST:-$MYSQL_HOST}"
TRACTOR_DB_PORT="${TRACTOR_DB_PORT:-$MYSQL_PORT}"
TRACTOR_DB_USER="${TRACTOR_DB_USER:-$MYSQL_USER}"
TRACTOR_DB_PASSWORD="${TRACTOR_DB_PASSWORD:-$MYSQL_PASSWORD}"
TRACTOR_DB_NAME="${TRACTOR_DB_NAME:-clinica_tractores_db}"

mkdir -p "$OUTPUT_DIR"

dump_db() {
  local host="$1"
  local port="$2"
  local user="$3"
  local pass="$4"
  local dbname="$5"
  local outfile="$6"

  if [[ -n "$pass" ]]; then
    MYSQL_PWD="$pass" mysqldump \
      --host="$host" \
      --port="$port" \
      --user="$user" \
      --single-transaction \
      --routines \
      --triggers \
      --events \
      --set-gtid-purged=OFF \
      "$dbname" | gzip > "$outfile"
  else
    mysqldump \
      --host="$host" \
      --port="$port" \
      --user="$user" \
      --single-transaction \
      --routines \
      --triggers \
      --events \
      --set-gtid-purged=OFF \
      "$dbname" | gzip > "$outfile"
  fi
}

echo "[1/2] Backing up DB: $MYSQL_DB"
dump_db "$MYSQL_HOST" "$MYSQL_PORT" "$MYSQL_USER" "$MYSQL_PASSWORD" "$MYSQL_DB" "$OUTPUT_DIR/mysql_main.sql.gz"

echo "[2/2] Backing up DB: $TRACTOR_DB_NAME"
dump_db "$TRACTOR_DB_HOST" "$TRACTOR_DB_PORT" "$TRACTOR_DB_USER" "$TRACTOR_DB_PASSWORD" "$TRACTOR_DB_NAME" "$OUTPUT_DIR/mysql_tractor.sql.gz"

cat > "$OUTPUT_DIR/backup_info.txt" <<EOF
created_at=$(date -Iseconds)
mysql_main_db=$MYSQL_DB
mysql_main_host=$MYSQL_HOST
mysql_main_port=$MYSQL_PORT
mysql_tractor_db=$TRACTOR_DB_NAME
mysql_tractor_host=$TRACTOR_DB_HOST
mysql_tractor_port=$TRACTOR_DB_PORT
EOF

sha256sum "$OUTPUT_DIR"/*.gz > "$OUTPUT_DIR/checksums.sha256"
echo "Backup completed in: $OUTPUT_DIR"

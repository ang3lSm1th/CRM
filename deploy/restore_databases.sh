#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./deploy/restore_databases.sh <backup_dir> [env_file]

BACKUP_DIR="${1:-}"
ENV_FILE="${2:-./.env}"

if [[ -z "$BACKUP_DIR" ]]; then
  echo "Usage: $0 <backup_dir> [env_file]"
  exit 1
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "Backup directory not found: $BACKUP_DIR"
  exit 1
fi

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

MAIN_FILE="$BACKUP_DIR/mysql_main.sql.gz"
TRACTOR_FILE="$BACKUP_DIR/mysql_tractor.sql.gz"

if [[ ! -f "$MAIN_FILE" ]]; then
  echo "Main backup file not found: $MAIN_FILE"
  exit 1
fi

if [[ ! -f "$TRACTOR_FILE" ]]; then
  echo "Tractor backup file not found: $TRACTOR_FILE"
  exit 1
fi

if [[ -f "$BACKUP_DIR/checksums.sha256" ]]; then
  (cd "$BACKUP_DIR" && sha256sum -c checksums.sha256)
fi

mysql_exec() {
  local host="$1"
  local port="$2"
  local user="$3"
  local pass="$4"
  shift 4

  if [[ -n "$pass" ]]; then
    MYSQL_PWD="$pass" mysql --host="$host" --port="$port" --user="$user" "$@"
  else
    mysql --host="$host" --port="$port" --user="$user" "$@"
  fi
}

echo "Creating databases if needed..."
mysql_exec "$MYSQL_HOST" "$MYSQL_PORT" "$MYSQL_USER" "$MYSQL_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS \`$MYSQL_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql_exec "$TRACTOR_DB_HOST" "$TRACTOR_DB_PORT" "$TRACTOR_DB_USER" "$TRACTOR_DB_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS \`$TRACTOR_DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "Restoring main DB: $MYSQL_DB"
if [[ -n "$MYSQL_PASSWORD" ]]; then
  gzip -dc "$MAIN_FILE" | MYSQL_PWD="$MYSQL_PASSWORD" mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" "$MYSQL_DB"
else
  gzip -dc "$MAIN_FILE" | mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" "$MYSQL_DB"
fi

echo "Restoring tractor DB: $TRACTOR_DB_NAME"
if [[ -n "$TRACTOR_DB_PASSWORD" ]]; then
  gzip -dc "$TRACTOR_FILE" | MYSQL_PWD="$TRACTOR_DB_PASSWORD" mysql --host="$TRACTOR_DB_HOST" --port="$TRACTOR_DB_PORT" --user="$TRACTOR_DB_USER" "$TRACTOR_DB_NAME"
else
  gzip -dc "$TRACTOR_FILE" | mysql --host="$TRACTOR_DB_HOST" --port="$TRACTOR_DB_PORT" --user="$TRACTOR_DB_USER" "$TRACTOR_DB_NAME"
fi

echo "Restore completed from: $BACKUP_DIR"

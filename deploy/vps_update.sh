#!/usr/bin/env bash
# Actualiza código, leads hasta hoy y reinicia servicios en la VPS.
# Uso (dentro de la VPS):
#   cd /var/www/crm_flask   # o la ruta de tu proyecto
#   bash deploy/vps_update.sh

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

echo "==> Proyecto: $PROJECT_DIR"

if [[ ! -f docker-compose.dockploy.yml ]] && [[ ! -f app.py ]]; then
  echo "No parece el directorio del CRM. Ajusta PROJECT_DIR."
  exit 1
fi

echo "==> Git pull..."
git fetch origin main
git pull origin main

TODAY=$(date +%Y-%m-%d)
echo "==> Leads hasta $TODAY..."

run_leads() {
  python3 scripts/generar_leads_mayo_diario.py --from "$1" --to "$TODAY"
}

if [[ -f docker-compose.dockploy.yml ]]; then
  echo "==> Modo Docker Compose"
  docker compose -f docker-compose.dockploy.yml build --pull
  docker compose -f docker-compose.dockploy.yml up -d

  # Última fecha en BD del contenedor
  LAST=$(docker compose -f docker-compose.dockploy.yml exec -T app python3 -c "
import os
from dotenv import load_dotenv
import MySQLdb
load_dotenv('/app/.env.dockploy')
load_dotenv('/app/.env')
c=MySQLdb.connect(
  host=os.getenv('MYSQL_HOST','mysql'),
  user=os.getenv('MYSQL_USER','root'),
  passwd=os.getenv('MYSQL_PASSWORD',''),
  db=os.getenv('MYSQL_DB','u349183440_crm_orbes'),
  port=int(os.getenv('MYSQL_PORT','3306')),
)
cur=c.cursor()
cur.execute('SELECT COALESCE(MAX(fecha), \"2026-05-01\") FROM leads')
print(cur.fetchone()[0])
c.close()
" 2>/dev/null || echo "2026-05-26")

  FROM=$(date -I -d "$LAST + 1 day" 2>/dev/null || python3 -c "from datetime import date, timedelta; print(date.fromisoformat('$LAST') + timedelta(days=1))")
  if [[ "$FROM" > "$TODAY" ]] || [[ "$FROM" == "$TODAY" && "$LAST" == "$TODAY" ]]; then
    echo "Leads ya al día (última fecha: $LAST)"
  else
    echo "Generando leads $FROM -> $TODAY"
    docker compose -f docker-compose.dockploy.yml exec -T app \
      python3 scripts/generar_leads_mayo_diario.py --from "$FROM" --to "$TODAY"
  fi

  docker compose -f docker-compose.dockploy.yml ps
  curl -sf http://127.0.0.1:8000/healthz && echo "" || echo "healthz no respondió"
else
  echo "==> Modo systemd / venv"
  if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi

  LAST=$(python3 -c "
import os
from dotenv import load_dotenv
import MySQLdb
load_dotenv()
c=MySQLdb.connect(
  host=os.getenv('MYSQL_HOST','127.0.0.1'),
  user=os.getenv('MYSQL_USER','root'),
  passwd=os.getenv('MYSQL_PASSWORD',''),
  db=os.getenv('MYSQL_DB','u349183440_crm_orbes'),
  port=int(os.getenv('MYSQL_PORT','3306')),
)
cur=c.cursor()
cur.execute('SELECT COALESCE(MAX(fecha), \"2026-05-01\") FROM leads')
print(cur.fetchone()[0])
c.close()
")
  FROM=$(python3 -c "from datetime import date, timedelta; print(date.fromisoformat('$LAST') + timedelta(days=1))")
  if [[ "$FROM" > "$TODAY" ]]; then
    echo "Leads ya al día (última fecha: $LAST)"
  else
    run_leads "$FROM"
  fi

  if systemctl is-active --quiet crm_flask 2>/dev/null; then
    sudo systemctl restart crm_flask
    sudo systemctl status crm_flask --no-pager | head -5
  fi
  curl -sf http://127.0.0.1:8000/healthz && echo "" || true
fi

echo "==> Listo."

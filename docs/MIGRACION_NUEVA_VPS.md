# Migracion completa a nueva VPS (codigo + frontend + base de datos)

Esta guia migra todo tu sistema desde una VPS origen a una VPS nueva:

- Codigo backend/frontend (proyecto Flask con templates/static).
- Variables de entorno.
- Base de datos principal (`u349183440_crm_orbes`).
- Base de datos secundaria (`clinica_tractores_db`, si aplica).

## 0) Requisitos recomendados para nueva VPS

- Ubuntu 22.04/24.04
- 1 vCPU / 2 GB RAM minimo (recomendado 2 vCPU / 4 GB)
- 25 GB SSD o mas

## 1) En la VPS origen: preparar backup

En la VPS actual, dentro del proyecto:

```bash
cd /var/www/crm_flask
chmod +x deploy/backup_databases.sh deploy/restore_databases.sh
./deploy/backup_databases.sh
```

Esto crea un backup en `./backups/<timestamp>/` con:

- `mysql_main.sql.gz`
- `mysql_tractor.sql.gz`
- `checksums.sha256`
- `backup_info.txt`

Obtiene la ruta generada y guardala:

```bash
ls -1dt /var/www/crm_flask/backups/* | head -n 1
```

## 2) En la VPS origen: empaquetar codigo

```bash
cd /var/www
tar -czf crm_flask_app.tar.gz \
  --exclude='crm_flask/.venv' \
  --exclude='crm_flask/env' \
  --exclude='crm_flask/__pycache__' \
  --exclude='crm_flask/*.pyc' \
  crm_flask
```

## 3) Transferir a nueva VPS

Desde tu maquina local (o desde VPS origen), copia:

```bash
scp /var/www/crm_flask_app.tar.gz root@IP_NUEVA_VPS:/var/www/
scp -r /var/www/crm_flask/backups/<TIMESTAMP> root@IP_NUEVA_VPS:/var/www/
```

## 4) En la nueva VPS: instalar paquetes base

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-dev build-essential pkg-config libmysqlclient-dev mysql-server nginx
```

## 5) En la nueva VPS: restaurar codigo

```bash
cd /var/www
tar -xzf crm_flask_app.tar.gz
cd /var/www/crm_flask
```

## 6) Configurar entorno (.env)

```bash
cp .env.example .env
nano .env
```

Minimo recomendado (ajusta passwords):

```env
FLASK_ENV=production
USE_HTTPS=0
TRUST_PROXY=1

PORT=8000
WEB_CONCURRENCY=1
GUNICORN_WORKER_CLASS=eventlet
GUNICORN_TIMEOUT=120

SOCKETIO_ASYNC_MODE=eventlet
SOCKETIO_CORS_ALLOWED_ORIGINS=http://IP_NUEVA_VPS

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=TU_PASSWORD
MYSQL_DB=u349183440_crm_orbes

TRACTOR_DB_HOST=127.0.0.1
TRACTOR_DB_PORT=3306
TRACTOR_DB_USER=root
TRACTOR_DB_PASSWORD=TU_PASSWORD
TRACTOR_DB_NAME=clinica_tractores_db
```

## 7) Restaurar base de datos en nueva VPS

Suponiendo que copiaste backup a `/var/www/<TIMESTAMP>`:

```bash
cd /var/www/crm_flask
chmod +x deploy/restore_databases.sh
./deploy/restore_databases.sh /var/www/<TIMESTAMP> /var/www/crm_flask/.env
```

Validar:

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p -e "SHOW DATABASES LIKE 'u349183440_crm_orbes';"
mysql -h 127.0.0.1 -P 3306 -u root -p -e "SHOW DATABASES LIKE 'clinica_tractores_db';"
```

## 8) Crear entorno Python e instalar dependencias

Si `python3` de la distro es muy nuevo y falla compilacion de paquetes, instala Python 3.11 con `uv`.

```bash
cd /var/www/crm_flask
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## 9) Probar arranque manual

```bash
cd /var/www/crm_flask
source .venv/bin/activate
python -m gunicorn -c gunicorn.conf.py wsgi:app
```

En otra terminal:

```bash
curl http://127.0.0.1:8000/healthz
```

## 10) Dejar servicio con systemd

```bash
cp /var/www/crm_flask/deploy/crm_flask.service.example /etc/systemd/system/crm_flask.service
```

Edita `/etc/systemd/system/crm_flask.service` y usa:

```ini
ExecStart=/var/www/crm_flask/.venv/bin/python -m gunicorn -c /var/www/crm_flask/gunicorn.conf.py wsgi:app
```

Luego:

```bash
systemctl daemon-reload
systemctl enable crm_flask
systemctl restart crm_flask
systemctl status crm_flask --no-pager
```

## 11) Nginx

```bash
cp /var/www/crm_flask/deploy/nginx.crm_flask.conf.example /etc/nginx/sites-available/crm_flask
nano /etc/nginx/sites-available/crm_flask
```

Si no tienes dominio aun:

- `server_name IP_NUEVA_VPS;` o `server_name _;`

Activar:

```bash
ln -sf /etc/nginx/sites-available/crm_flask /etc/nginx/sites-enabled/crm_flask
nginx -t
systemctl reload nginx
```

## 12) Checklist de migracion

- `curl http://127.0.0.1:8000/healthz` responde `{"status":"ok"}`
- `http://IP_NUEVA_VPS/auth/login` carga
- Login funciona con usuarios migrados
- Reportes/datos historicos visibles
- `journalctl -u crm_flask -n 100 --no-pager` sin errores criticos

## 13) Rollback rapido (si algo falla)

- Mantener VPS origen activa hasta validar nueva VPS.
- Cambiar DNS/uso final solo despues de checklist completo.
- Si falla nueva VPS, volver temporalmente a origen.

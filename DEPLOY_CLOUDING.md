# Despliegue en VPS clouding.io (Ubuntu)

Esta guia deja el CRM Flask corriendo con Gunicorn + systemd + Nginx.

## 1) Preparar servidor

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-dev build-essential pkg-config libmysqlclient-dev nginx certbot python3-certbot-nginx
```

## 2) Subir proyecto

```bash
sudo mkdir -p /var/www/crm_flask
sudo chown -R $USER:$USER /var/www/crm_flask
# Copia aqui tu proyecto (git clone o rsync)
```

## 3) Entorno virtual e instalacion

```bash
cd /var/www/crm_flask
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Valores minimos recomendados en `.env` para tu caso (MySQL local en `127.0.0.1:3307`):

- `FLASK_ENV=production`
- `USE_HTTPS=1`
- `TRUST_PROXY=1`
- `SOCKETIO_ASYNC_MODE=eventlet`
- `SOCKETIO_CORS_ALLOWED_ORIGINS=https://tu-dominio.com`
- `PORT=8000`
- `GUNICORN_WORKER_CLASS=eventlet`
- `WEB_CONCURRENCY=1`
- `MYSQL_HOST=127.0.0.1`
- `MYSQL_PORT=3307`
- `MYSQL_USER=root`
- `MYSQL_PASSWORD=<tu_password_root>`
- `MYSQL_DB=u349183440_crm_orbes`
- `TRACTOR_DB_HOST=127.0.0.1`
- `TRACTOR_DB_PORT=3307`
- `TRACTOR_DB_USER=root`
- `TRACTOR_DB_PASSWORD=<tu_password_root>`
- `TRACTOR_DB_NAME=clinica_tractores_db`
- `SECRET_KEY` seguro

## 5) Probar arranque manual

```bash
cd /var/www/crm_flask
source .venv/bin/activate
gunicorn -c gunicorn.conf.py wsgi:app
```

Verifica:

```bash
curl http://127.0.0.1:8000/healthz
```

Debe responder `{"status":"ok"}`.

Valida DB local:

```bash
mysql -h 127.0.0.1 -P 3307 -u root -p -e "SHOW DATABASES LIKE 'u349183440_crm_orbes';"
```

## 6) Crear servicio systemd

```bash
sudo cp deploy/crm_flask.service.example /etc/systemd/system/crm_flask.service
sudo nano /etc/systemd/system/crm_flask.service
```

Ajusta en el servicio:

- `User`/`Group`
- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

Luego:

```bash
sudo systemctl daemon-reload
sudo systemctl enable crm_flask
sudo systemctl start crm_flask
sudo systemctl status crm_flask
```

Logs:

```bash
sudo journalctl -u crm_flask -f
```

## 7) Configurar Nginx

```bash
sudo cp deploy/nginx.crm_flask.conf.example /etc/nginx/sites-available/crm_flask
sudo nano /etc/nginx/sites-available/crm_flask
```

Cambia `server_name tu-dominio.com`.

Activar sitio:

```bash
sudo ln -s /etc/nginx/sites-available/crm_flask /etc/nginx/sites-enabled/crm_flask
sudo nginx -t
sudo systemctl reload nginx
```

## 8) Certificado SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d tu-dominio.com
```

## 9) Checklist rapido

- `https://tu-dominio.com/healthz` responde 200.
- Login y rutas protegidas funcionan.
- Socket.IO funciona en `wss` (chat/agentes).
- Cookies seguras activas con HTTPS.

## 10) Comandos utiles de operacion

```bash
sudo systemctl restart crm_flask
sudo systemctl reload nginx
sudo journalctl -u crm_flask -n 100 --no-pager
```

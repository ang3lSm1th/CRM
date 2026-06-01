# Despliegue en Hostinger con Dockploy (App + MySQL)

Esta guia deja tu CRM Flask funcionando en Dockploy con dos servicios:

- `app` (Flask + Gunicorn + Socket.IO)
- `mysql` (MySQL 8 con volumen persistente)

## 1) Archivos incluidos para Dockploy

- `Dockerfile`
- `.dockerignore`
- `docker-compose.dockploy.yml`
- `.env.dockploy.example`
- `deploy/backup_databases.sh`
- `deploy/restore_databases.sh`

## 2) Preparar variables de entorno

```bash
cp .env.dockploy.example .env.dockploy
nano .env.dockploy
```

Valores obligatorios a editar:

- `SECRET_KEY`
- `MYSQL_PASSWORD`
- `TRACTOR_DB_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `SOCKETIO_CORS_ALLOWED_ORIGINS`

## 3) Subir proyecto a tu servidor Hostinger

Puedes usar Git o subir el proyecto por SCP/ZIP. El proyecto debe quedar completo en el host donde corre Dockploy.

### Opcion recomendada: GitHub + Deploy desde repositorio

En tu maquina local (raiz del proyecto):

```bash
git init
git add .
git commit -m "chore: preparar CRM Flask para Dockploy"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

Notas:

- `.gitignore` ya excluye `env/`, `.env`, `backups/` y caches.
- No subas `.env.dockploy`; solo sube `.env.dockploy.example`.

En Dockploy:

1. Conecta GitHub (Provider).
2. Selecciona tu repositorio y rama `main`.
3. Tipo: `Docker Compose`.
4. Compose file: `docker-compose.dockploy.yml`.
5. Variables: pega las de `.env.dockploy` en el panel de envs de Dockploy.
6. Deploy.

## 4) Crear proyecto en Dockploy

En Dockploy:

1. Crea un nuevo proyecto.
2. Tipo: `Docker Compose`.
3. Selecciona el archivo: `docker-compose.dockploy.yml`.
4. Asegura que use el archivo de entorno `.env.dockploy`.
5. Deploy.

## 5) Migrar datos reales desde VPS anterior

### 5.1 Generar backup en VPS origen

```bash
cd /var/www/crm_flask
chmod +x deploy/backup_databases.sh
./deploy/backup_databases.sh
ls -1dt backups/* | head -n 1
```

### 5.2 Copiar backup a nueva VPS (Hostinger)

```bash
scp -r /var/www/crm_flask/backups/<TIMESTAMP> root@IP_NUEVA_VPS:/var/www/crm_flask/backups/
```

### 5.3 Restaurar dentro del contenedor `app`

En la nueva VPS (Hostinger):

```bash
cd /var/www/crm_flask
chmod +x deploy/restore_databases.sh
docker compose -f docker-compose.dockploy.yml exec app ./deploy/restore_databases.sh /app/backups/<TIMESTAMP> /app/.env.dockploy
```

## 6) Verificar funcionamiento

```bash
docker compose -f docker-compose.dockploy.yml ps
docker compose -f docker-compose.dockploy.yml logs -f app
curl http://127.0.0.1:8000/healthz
```

Debe responder:

```json
{"status":"ok"}
```

## 7) Exponer por dominio (recomendado)

En Dockploy/Proxy:

- Configura dominio apuntando a tu VPS.
- Enruta al servicio `app` puerto `8000`.
- Activa SSL (Let's Encrypt) desde Dockploy.

Luego en `.env.dockploy` usa:

- `USE_HTTPS=1`
- `SOCKETIO_CORS_ALLOWED_ORIGINS=https://tu-dominio.com`

Redeploy del proyecto tras cambios.

## 8) Notas importantes

- El volumen `mysql_data` conserva datos entre reinicios/redeploy.
- Los scripts de `docker-entrypoint-initdb.d` (`Database.sql`, `bd_tracores.sql`) se ejecutan solo en primera inicializacion del volumen.
- Si ya tienes datos migrados, no borres el volumen `mysql_data`.

## 9) Ajuste si no tienes dominio aun

En `.env.dockploy` usa temporalmente:

- `USE_HTTPS=0`
- `SOCKETIO_CORS_ALLOWED_ORIGINS=http://IP_DE_TU_VPS`

Cuando tengas dominio + SSL, cambia a:

- `USE_HTTPS=1`
- `SOCKETIO_CORS_ALLOWED_ORIGINS=https://tu-dominio.com`

# Sistema Actual - CRM Flask

Fecha de corte: 2026-05-13

## 1. Resumen general
Este proyecto es un CRM web en Flask para gestion comercial, seguimiento de leads, reportes, marketing y chat interno.

El sistema esta organizado por Blueprints y modulos por dominio. Actualmente tiene:
- Core CRM transaccional (leads, usuarios, procesos, bienes/servicios).
- Modulo de marketing (campanas, ferias, inventario, roadmap, OKR).
- Chat interno entre usuarios.
- Chat multiagente interno con orquestador y monitoreo.

## 2. Stack tecnologico
- Backend: Flask 3.0.3
- Realtime: Flask-SocketIO
- Base de datos principal: MySQL (Flask-MySQLdb / mysqlclient)
- Seguridad: sesiones Flask + Flask-Bcrypt + decoradores de rol
- Templates: Jinja2
- Analitica/reporteria: matplotlib, openpyxl, numpy
- IA/LLM: openai, litellm, crewai (segun configuracion)
- ML: scikit-learn, joblib

## 3. Entry point y configuracion
## app.py
- Construye la app con `create_app()`.
- Inicializa `mysql`, `bcrypt` y `socketio` (desde `extensions.py`).
- Registra Blueprints de autenticacion, CRM, marketing, chat y agentes.
- Define `before_request` para login obligatorio global.
- Limita el alcance del rol marketing a endpoints permitidos.
- Agrega headers de seguridad HTTP.
- Ejecuta localmente con SocketIO en `127.0.0.1:8001`.

## config.py
- Carga variables de entorno con `python-dotenv`.
- Configura conexion MySQL CRM.
- Configura conexion secundaria a base Tractor.
- Incluye flags de seguridad (`USE_HTTPS`, `ALLOW_PUBLIC_REGISTRATION`) y parametros de agentes (`AGENT_MODEL`, `AGENT_MEMORY_SIZE`).

## extensions.py
- Instancias compartidas:
  - `mysql`
  - `bcrypt`
  - `socketio`
  - `login_manager`

## 4. Modulos funcionales
## Autenticacion y usuarios
- `routes/auth_login.py`
- `routes/auth_register.py`
- `routes/auth_usuarios.py`

## CRM comercial
- `routes/dashboard.py`
- `routes/lead.py`
- `routes/bienes_servicios.py`
- `routes/reporte_rapido.py`
- `routes/reportes.py`

## Marketing
- Blueprint facade: `routes/marketing.py`
- Modulos especializados:
  - `routes/marketing_shared.py`
  - `routes/marketing_campana.py`
  - `routes/marketing_feria.py`
  - `routes/marketing_inventario.py`
  - `routes/marketing_roadmap.py`
  - `routes/marketing_clients.py`
  - `routes/marketing_okr_panel.py`
  - `routes/marketing_whatsapp.py`

## Chat interno
- `routes/chat.py`
- Endpoints base bajo prefijo `/chat` para mensajes, envio, lectura y usuarios.

## Chat multiagente y monitoreo
- `routes/agent_chat.py`
  - UI: `GET /agent`
  - Sesion: `GET /agent/session`, `POST /agent/session/new`, `POST /agent/session/select`
  - Interaccion: `POST /agent/interact`
  - Historial/feedback/stats: `/agent/history`, `/agent/feedback`, `/agent/stats`
- `routes/agent_monitor.py`
  - UI: `GET /agent/monitor`
  - APIs de observabilidad: comunicacion, registry, traces, estadisticas

## 5. Capa de agentes (backend)
El orquestador principal esta en `agents/broker/orchestrator.py` y enruta por intencion.

Agentes declarados:
- `database` (consultas SQL/metricas CRM)
- `marketing` (campanas, inventario, ferias)
- `prediccion` (probabilidad de compra)
- `reportes` (tendencias, embudo, top productos)
- `retencion_abandono` (retencion/churn)
- `llm` (fallback de lenguaje natural)

Persistencia y metrica de agentes:
- Modelos en `models/agent_models/` (memoria, stats, trazas)

## 6. Modelos de dominio
En `models/` se concentran entidades del CRM:
- `lead.py`, `seguimiento.py`, `proceso.py`
- `user.py`
- `canal.py`, `canal_contacto.py`
- `bien_servicio.py`
- `moneda.py`, `motivonoventa.py`

Patron de acceso dominante: consultas SQL directas con cursores MySQL por modulo.

## 7. Base de datos y migraciones
Esquemas base presentes:
- `Database.sql`
- `bd_tracores.sql`

Migraciones en `db/migrations/`:
- `2026_04_06_add_detalle_to_marketing_feria_gastos.sql`
- `2026_04_06_create_marketing_inventario_mercaderia.sql`
- `2026_04_07_create_marketing_social_metrics.sql`
- `2026_04_09_create_lead_cambios.sql`
- `2026_04_15_create_notificaciones_venta_and_lead_tractor_guardados.sql`
- `2026_05_11_create_agent_tables.sql`
- `2026_05_11_create_agent_ml_tables.sql`
- `2026_05_11_drop_multiagent_artifacts.sql`

Nota: coexisten scripts de creacion y limpieza de artefactos de agentes por iteraciones previas; revisar orden de ejecucion en despliegues nuevos.

## 8. Seguridad y control de acceso
Mecanismos activos:
- Login obligatorio por middleware global en `app.py`.
- Decoradores `login_required` y `role_required` en `utils/security.py`.
- Restriccion especial para rol marketing.
- Headers de seguridad: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
- Cookies de sesion endurecidas (`HttpOnly`, `SameSite=Lax`, `Secure` segun `USE_HTTPS`).

## 9. Frontend y plantillas
Estructura principal de vistas:
- `templates/base.html`, `templates/base_login.html`
- `templates/auth/`
- `templates/leads/`
- `templates/marketing/`
- `templates/reportes/`
- `templates/chat/`
- `templates/agents/`

Assets estaticos en:
- `static/css/`
- `static/js/`
- `static/img/`

## 10. Estado actual (resumen operativo)
El sistema esta operativo como CRM + marketing + chat interno, y mantiene una capa de agentes integrada para consultas asistidas, monitoreo y analitica extendida.

En terminos de prioridad funcional, el core transaccional de leads/ventas y marketing sigue siendo el eje principal, con capacidades IA como modulo complementario.
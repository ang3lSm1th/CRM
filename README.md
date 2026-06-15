# CRM Flask — CRM Orbes

CRM comercial con workflow multiagente distribuido (Flask + Celery + Redis + microservicio de agentes IA).

## Inicio rápido

```bash
docker compose -f docker-compose.dockploy.yml up -d
```

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/ARQUITECTURA_DISTRIBUIDA.md](docs/ARQUITECTURA_DISTRIBUIDA.md) | Arquitectura distribuida |
| [docs/diagrams/](docs/diagrams/) | **Diagramas PNG** (arquitectura, flujo, carpetas) |
| [docs/SISTEMA_ACTUAL.md](docs/SISTEMA_ACTUAL.md) | Módulos del CRM |
| [docs/DEPLOY_DOCKPLOY_HOSTINGER.md](docs/DEPLOY_DOCKPLOY_HOSTINGER.md) | Despliegue en VPS |

## Estructura

```
core/          → config, extensions, celery
entrypoints/   → web (:8000) y agent-services (:8001)
routes/        → auth · crm · marketing · agents
agents/        → broker, core, lead_workflow
db/schemas/    → esquemas SQL base
infra/         → docker-compose, gunicorn, Procfile
```

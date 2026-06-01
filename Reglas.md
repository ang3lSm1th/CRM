# Reglas para CRM Flask - Integración Multiagente de Análisis de Leads y Automatización Comercial

Responde corto.
Usa arquitectura limpia.
No modifiques archivos innecesarios.

## 1. Contexto del Proyecto
- CRM web existente en **Flask 3.0.3** con MySQL, Blueprints, autenticación por roles y chat multiagente previo (broker/orquestador).
- El objetivo es **ampliar** la capa de agentes IA para implementar un flujo completo de leads: scoring, asignación, contacto/secuimiento, recuperación, cierre/facturación y dashboards gerenciales (según diagrama TO-BE).
- No se debe romper la funcionalidad actual del CRM (leads, seguimientos, marketing, reportes). La integración será **modular y respetando la estructura existente**.

## 2. Stack Tecnológico Existente (a mantener)
- Backend: Flask, Flask-SocketIO, MySQL (Flask-MySQLdb).
- Seguridad: sesiones Flask, bcrypt, decoradores `role_required`.
- Templates: Jinja2.
- IA/LLM: ya se usa `openai`, `litellm`, `crewai` y `scikit-learn`.
- Agentes actuales: `agents/broker/orchestrator.py` con agentes: database, marketing, prediccion, reportes, retencion_abandono, llm.
- Estructura de agentes: se debe **extender** no reemplazar. Los nuevos agentes convivirán con los existentes.

## 3. Nuevos Agentes a Implementar (según diagrama)
Crear nuevos módulos en `agents/` (o una subcarpeta `agents/lead_workflow/`) para:

| Agente | Archivo sugerido | Responsabilidad |
|--------|------------------|------------------|
| **Recepción + Scoring Inicial** | `agents/lead_scoring.py` | Recibe lead nuevo, valida, calcula score (0-100), genera recomendación (Alta/Media/Baja). Guarda en `lead` (tabla existente) y en `lead_agent_state` (tabla nueva). |
| **Asesor Comercial (Contacto y seguimiento)** | `agents/commercial_assistant.py` | Realiza 1er y 2do contacto (email/WhatsApp/SMS según canal preferido). Registra interacciones. Decide si escalar a recuperación o a cierre. |
| **Recuperación (Agente 4)** | `agents/recovery_agent.py` | Toma leads sin respuesta tras 2 intentos, aplica estrategias alternativas, hasta 2 intentos más. Si responde → vuelve a Asesor; si no → `venta_muerta`. |
| **Cierre y Facturación** | `agents/closing_agent.py` | Genera cotización/propuesta, manejo de objeciones, emisión de factura/boleta, registro de venta/no venta en CRM. |
| **Gerencia (KPIs, predictivo, feedback)** | `agents/management_agent.py` | Calcula CAC, tasa adquisición, retención, abandono. Análisis predictivo (riesgo de churn). Genera dashboards y retroalimenta al sistema de scoring. |

## 4. Flujo de Orquestación (recomendado: LangGraph o extensión del broker actual)
- **Opción A (más limpia)**: Usar **LangGraph** dentro de una nueva ruta/backend `agents/lead_workflow/orchestrator.py`. No interferir con el broker existente (`agents/broker/orchestrator.py`), que seguirá funcionando para consultas generales.
- **Opción B (simplificada)**: Extender el orquestador actual añadiendo un nuevo `workflow_id` para el proceso de leads, usando el mismo patrón de mensajería.
- **Decisión**: Dado que el sistema actual ya tiene `crewai`, puedes usar `CrewAI` para flujos secuenciales simples, pero LangGraph es mejor para condicionales múltiples (sí/no, reintentos). Se recomienda **LangGraph** para este caso.

## 5. Integración con Flask Existente (rutas y servicios)
- **Nuevo Blueprint**: `routes/lead_workflow.py` con endpoints:
  - `POST /lead_workflow/process` → recibe lead_id (o datos de lead nuevo) e inicia el workflow asíncrono.
  - `GET /lead_workflow/status/<lead_id>` → devuelve estado actual (nodo, intentos, score, etc.).
  - `POST /lead_workflow/manual` → para acciones manuales (reintentar, forzar paso, cambiar score).
- **Tareas asíncronas**: Usar **Celery** + Redis (si no está, se puede agregar o usar `threading` con cuidado; pero Celery es más robusto). El workflow completo no debe bloquear la petición HTTP.
- **Webhooks**: Para respuestas de lead (ej. cuando contesta un email), se puede usar un endpoint que reciba el evento y actualice el estado (similar a `lead_workflow/webhook`).


## 6. Modelos de Datos (nuevas tablas o columnas)
No modificar tablas existentes a menos que sea estrictamente necesario. Crear nuevas tablas:

```sql
-- Estado del lead en el workflow multiagente
CREATE TABLE lead_agent_state (
    id INT PRIMARY KEY AUTO_INCREMENT,
    lead_id INT NOT NULL,               -- FK a lead.id
    current_node VARCHAR(50),           -- 'scoring', 'commercial', 'recovery', 'closing', 'dead'
    score INT DEFAULT 0,
    attempts INT DEFAULT 0,              -- intentos de contacto acumulados
    last_action DATETIME,
    next_action_date DATETIME,
    data JSON,                           -- metadata adicional
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES lead(id) ON DELETE CASCADE
);

-- Historial de interacciones agente-lead
CREATE TABLE agent_interactions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    lead_id INT NOT NULL,
    agent_name VARCHAR(50),
    interaction_type VARCHAR(50),        -- 'email', 'whatsapp', 'sms', 'call'
    direction ENUM('outbound', 'inbound'),
    content TEXT,
    response_received BOOLEAN DEFAULT FALSE,
    response_content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES lead(id)
);
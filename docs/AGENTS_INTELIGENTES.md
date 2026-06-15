# 🤖 Sistema de Agentes Inteligentes - CRM Orbes

## 📋 Índice
1. [Visión General](#visión-general)
2. [Arquitectura de Agentes](#arquitectura-de-agentes)
3. [PrediccionCompraAgente (Predicción de Compra)](#prediccioncompraagente)
4. [Herramientas (Tools) Utilizadas](#herramientas-tools-utilizadas)
5. [Objetivos y Métricas](#objetivos-y-métricas)
6. [Flujo de Datos](#flujo-de-datos)

---

## 🎯 Visión General

El sistema de agentes inteligentes de Orbes CRM tiene como **OBJETIVO PRINCIPAL**: 
> **Aumentar la tasa de cierre de ventas proporcionando al asesor inteligencia contextual en tiempo real sobre cada lead**, incluyendo probabilidad de compra, historial del cliente, estado del pipeline, y acciones recomendadas personalizadas.

### Meta de Negocio
- 📈 Incrementar conversión de leads a ventas
- ⏱️ Reducir tiempo de ciclo de ventas
- 🎯 Priorizar esfuerzos en leads de mayor potencial
- 💡 Dar coaching automático a asesores con recomendaciones contextuales

---

## 🏗️ Arquitectura de Agentes

### Ubicación en el Proyecto
```
agents/
├── core/
│   ├── prediccion_agente.py          ← Predice probabilidad de compra
│   ├── db_agent.py                   ← Consultas a base de datos
│   ├── llm_agent.py                  ← Procesamiento de lenguaje natural
│   ├── marketing_agent.py            ← Análisis de campañas
│   ├── reportes_agente.py            ← Generación de reportes
│   └── retencion_agente.py           ← Predicción de churn/retención
├── broker/
│   └── orchestrator.py               ← Coordinación entre agentes
└── mas/                              ← Módulos de soporte
```

### Patrón de Diseño
- **Tipo**: Agentes Especializados (Task-Based Agents)
- **Comunicación**: REST API + Sesiones de chat persistentes
- **Persistencia**: Base de datos (agent_chat_sessions, agent_chat_messages)
- **Modo de Operación**: Sincrónico (respuesta inmediata) + Asincrónico (cachés con TTL)

---

## 🔮 PrediccionCompraAgente

### 📍 Ubicación
`agents/core/prediccion_agente.py`

### 🎯 Objetivo
Predecir la **probabilidad de que un lead realice una compra en los próximos 30 días**, basada en:
- Historial de compras del cliente
- Nivel de engagement (cantidad y recencia de contactos)
- Etapa actual en el pipeline de ventas
- Capacidad de compra (montos registrados)

### 🔧 Cómo Funciona

#### 1️⃣ **Inicialización**
```python
agent = PrediccionCompraAgente()
```
- Carga modelo ML entrenado: `models/ml_models/compra_model.pkl`
- Tipo: **RandomForestClassifier** (scikit-learn)
- Versión: Definida en `.env` como `COMPRA_MODEL_VERSION=rf_v1`

#### 2️⃣ **Métodos Principales**

| Método | Entrada | Salida | Propósito |
|--------|---------|--------|-----------|
| `predict_percentages_for_leads(leads)` | Lista de objetos Lead | Dict con predicciones | Predicción batch para vistas de lista |
| `_fetch_lead_engagement_metrics(lead_ids)` | Lista de IDs | Dict con métricas | Recopila datos del cliente |
| `_calculate_prediction_score(metrics)` | Dict de métricas | Número 15-100 | Calcula % probabilidad |
| `_generate_recommendation_message(metrics, %)` | Métricas + % | Lista de strings | Genera acciones para asesor |
| `handle(question)` | Pregunta natural | JSON respuesta | Interfaz chatbot |

### 📊 Algoritmo de Predicción (5 Factores Ponderados)

```
SCORE = Factor1 + Factor2 + Factor3 + Factor4 + Factor5
      = Compras(30%) + Engagement(25%) + Recencia(20%) + Proceso(15%) + Monto(10%)

Rango final: 15% (mínimo) a 100% (máximo)
```

#### **Factor 1: Historial de Compras (30 puntos)**
Cuenta cuántas veces el cliente ha completado un proceso "Cerrado" (excluye "Cerrado no vendido")
```
0 compras → 0 pts
1 compra  → 10 pts
2 compras → 20 pts
3+ compras → 30 pts
```
**Lógica**: Cliente recurrente = mayor probabilidad de nueva compra

#### **Factor 2: Engagement/Seguimientos (25 puntos)**
Cantidad total de interacciones (seguimientos) del cliente en el CRM
```
0 seguimientos    → 0 pts
1-2 seguimientos → 8 pts
3-5 seguimientos → 15 pts
6+ seguimientos  → 25 pts
```
**Lógica**: Más contacto = mayor interés y familiaridad

#### **Factor 3: Recencia (20 puntos)**
Cuántos días han pasado desde el último contacto con el cliente
```
< 7 días      → 20 pts (caliente)
7-30 días     → 15 pts (activo)
31-60 días    → 10 pts (moderado)
61-90 días    → 5 pts  (frío)
90+ días      → 0 pts  (muy frío)
```
**Lógica**: Contacto reciente = momentum de venta

#### **Factor 4: Etapa del Pipeline (15 puntos)**
Proceso actual del lead en el pipeline de ventas
```
Cerrado                   → 15 pts (ya compró!)
Cotizado                  → 12 pts (propuesta enviada)
Programado                → 10 pts (cita concertada)
Seguimiento               → 8 pts  (en conversación)
No iniciado               → 2 pts  (frío)
Cerrado no vendido        → 0 pts  (fallido)
```
**Lógica**: Lead en etapa avanzada = más cerca del cierre

#### **Factor 5: Capacidad de Compra/Monto (10 puntos)**
¿Hay registrados montos en los seguimientos del cliente?
```
Sin monto registrado → 0 pts
Con monto > 0       → 10 pts
```
**Lógica**: Cliente que ha indicado presupuesto es más serio

### 🎨 Bandas de Color por Probabilidad

| % | Color | Categoría | Acción |
|---|-------|-----------|--------|
| 80%+ | 🟢 Verde (#28a745) | **Muy Alto** | Cerrar esta semana |
| 65-79% | 🔵 Azul (#007bff) | **Alto** | Presionar suavemente |
| 45-64% | 🔷 Celeste (#17a2b8) | **Medio-Alto** | Nutrir continuamente |
| 25-44% | 🟡 Amarillo (#ffc107) | **Medio-Bajo** | Seguimiento constante |
| <25% | 🔴 Rojo (#dc3545) | **Bajo** | Automatizar/Buscar nuevos |

### 💬 Recomendaciones Contextuales

El agente genera **7-15 mensajes personalizados** basados en:

#### Ejemplo 1: Cliente VIP (3+ compras, reciente, alto engagement)
```
🎯 PRIORIDAD ALTA - Enfocarse en cierre esta semana
🔄 Cliente VIP recurrente - Ofrecer paquete de renovación/upgrade
🔥 Contacto muy reciente - Mantener el momentum, no dejar enfriar
🚀 Alta interacción - Cliente muy interesado, cerrar esta semana
💰 Capacidad compra: $15,000 promedio - Ajustar propuesta
```

#### Ejemplo 2: Cliente en cotización (sin compras previas, 2-3 segs)
```
📌 PRIORIDAD MEDIA - Seguimiento constante, presionar suavemente
📋 Cotización lista - Hacer seguimiento en 2-3 días para aclarar dudas
📞 En gestión - Aclarar objeciones y mantener presión positiva
🔥 Contacto muy reciente - Mantener el momentum, no dejar enfriar
💡 Sin monto registrado - Pedir presupuesto o rango de inversión
```

#### Ejemplo 3: Lead abandonado (0 compras, 60+ días sin contacto)
```
⏳ POTENCIAL BAJO - Automatizar follow-up, buscar nuevos contactos
❄️ Lead algo frío - Reactivar con llamada o email de valor
👤 Primer contacto pendiente - Llamar hoy mismo
```

### 🔌 Integración en la Vista

**Ubicación**: `templates/leads/list.html` línea 196+
**Activación**: `routes/lead.py` línea 913 (list views) y 1018 (todos)

```python
# En routes/lead.py
prediccion_agente = PrediccionCompraAgente()
lead_predictions = prediccion_agente.predict_percentages_for_leads(leads)
# Pasar al template
render_template(..., lead_predictions=lead_predictions)
```

**Visualización en Template**:
- Badge con % de probabilidad
- Color según rango (5 colores)
- Popover al pasar mouse mostrando:
  - Métricas (compras, seguimientos, días, monto)
  - Lista de 7-15 acciones recomendadas

---

## 🛠️ Herramientas (Tools) Utilizadas

### 1. **Base de Datos (MySQL)**
```
Tabla: leads
Tabla: seguimientos
Tabla: proceso
Tabla: predicciones_compra (caché)
```

**Métodos**:
- `_table_exists(table_name)` → Verifica existencia de tabla
- `_column_exists(table_name, column)` → Verifica columnas dinámicamente
- `_fetch_lead_engagement_metrics()` → Consulta batch de métricas

### 2. **Modelo de Machine Learning**
```
Archivo: models/ml_models/compra_model.pkl
Tipo: RandomForestClassifier
Características: 5 features
  - dias_desde_alta
  - tiene_cliente
  - total_seguimientos
  - dias_desde_ultimo_seguimiento
  - monto_promedio_seguimiento
Método: predict_proba() → Probabilidad de compra
```

### 3. **Caching**
```
Tabla: predicciones_compra
Campos:
  - lead_id
  - probabilidad_compra (0-1)
  - modelo_version
  - created_at
```

### 4. **Text Normalization**
```
Módulo: utils/text_normalizer.py
Función: normalize_user_text(text)
Propósito: Procesar preguntas naturales del chatbot
```

### 5. **Sesiones Flask**
```
Contexto: Flask application context
Propósito: Acceso a mysql.connection
```

---

## 🎯 Objetivos y Métricas

### Objetivo Primario
✅ **Aumentar tasa de cierre de ventas** mediante inteligencia contextual

### Métricas de Éxito
1. **Tasa de Conversión**: % de leads con score ≥70% que se convierten en venta
2. **Velocidad de Ciclo**: Reducción de días entre lead y cierre
3. **Adopción de Asesores**: % de asesores que usan recomendaciones en sus acciones
4. **Precisión del Modelo**: % de predicciones correctas vs. resultados reales

### KPIs a Monitorear
- 📊 Distribución de leads por banda de riesgo (% en verde/rojo)
- 🔴 Leads "en rojo" que se recuperan con recomendaciones
- 📈 Tasa de win en leads ≥75% vs. <25%
- ⏱️ Tiempo promedio de conversión por banda de riesgo

---

## 🔄 Flujo de Datos Completo

### A. Flujo en Vistas de Lista (Más Común)

```
1. Usuario abre /leads (list_leads en routes/lead.py)
                ↓
2. Consulta DB: SELECT leads...
                ↓
3. Crea lista de objetos Lead
                ↓
4. Llama: lead_predictions = prediccion_agente.predict_percentages_for_leads(leads)
                ↓
5. Agente: extrae lead_ids → [2, 4, 5, 7, ...]
                ↓
6. SQL Batch: _fetch_lead_engagement_metrics([2,4,5,7,...])
   → Obtiene para CADA lead:
     - compras_historicas (de todos los leads del cliente)
     - total_seguimientos (del cliente)
     - dias_ultimo_seg (recencia)
     - monto_promedio (capacidad)
     - proceso_actual (etapa del lead)
                ↓
7. Para cada lead:
   a) _calculate_prediction_score(metrics) → 15-100%
   b) _generate_recommendation_message(metrics, %) → ["msg1", "msg2", ...]
                ↓
8. Retorna dict:
   {
     2: {
       "porcentaje": 75.0,
       "compras_historicas": 2,
       "total_seguimientos": 5,
       "dias_ultimo_seg": 3,
       "proceso_actual": "seguimiento",
       "recomendaciones": ["🎯 PRIORIDAD ALTA...", "🔄 Cliente VIP...", ...]
     },
     4: {...},
     ...
   }
                ↓
9. Template recibe: {{ lead_predictions }}
                ↓
10. Para cada lead en tabla:
    - Renderiza badge con color según %
    - Popover con metrices + recomendaciones
                ↓
11. Usuario interactúa (hover/click):
    - VE el % en grande y colorido
    - VE las 7-15 acciones recomendadas
                ↓
12. Asesor TOMA ACCIÓN:
    - "Veo que Danny Paul tiene 75% y VIP"
    - "Debo ofrecer paquete de upgrade"
    - "Presiono cierre hoy"
```

### B. Flujo en Chatbot (Menos Común)

```
1. Usuario pregunta: "Lead #123 probabilidad de compra"
                ↓
2. Chat agent llama: agente.handle(question)
                ↓
3. Extrae: lead_id = 123
                ↓
4. Carga features individuales con _fetch_lead_features(123)
                ↓
5. Inferencia ML: model.predict_proba(features) → prob 0-1
                ↓
6. Convierte a %: pct = prob * 100
                ↓
7. Cachea en DB: INSERT INTO predicciones_compra
                ↓
8. Retorna JSON:
   {
     "ok": true,
     "agent": "prediccion_compra",
     "answer": "Lead #123: probabilidad estimada 72.5%...",
     "data": { "lead_id": 123, "probabilidad": 0.725, ... }
   }
```

---

## 🐛 Problemas Conocidos y Soluciones

### Problema 1: Clientes con compras mostraban 15% igual que sin compras
**Causa**: SQL contaba "leads cerrados" no "compras"
**Solución**: 
- Cambio de `COUNT(DISTINCT h.id)` a `SUM(CASE...) = 1`
- Ahora cuenta seguimientos cerrados (compras reales)
- Exluye "cerrado no vendido"

### Problema 2: Mensajes no aparecían
**Causa**: Datos generados pero no renderizados en template
**Solución**: 
- Template actualizado para mostrar popover
- Bootstrap Popover inicializado con JS

### Problema 3: Recencia incorrecta en clientes con múltiples leads
**Causa**: Tomaba MAX(fecha) del lead histórico, no del cliente
**Solución**: 
- Ahora usa MAX(s.fecha_guardado) de TODOS los seguimientos del cliente
- Más preciso para determinar si cliente está activo

---

## 📝 Tabla de Referencia Rápida

### Procesos Válidos en Pipeline
```
No iniciado
Seguimiento
Cotizado
Programado
Cerrado
Cerrado no vendido
```

### Campos en Predicción Dict
```
{
  "porcentaje": float (15-100),
  "compras_historicas": int,
  "total_seguimientos": int,
  "dias_ultimo_seg": int,
  "monto_promedio": float,
  "proceso_actual": str,
  "metodo": "multiplex_engagement",
  "recomendaciones": [str, str, ...] (7-15 items)
}
```

---

## 🚀 Próximos Pasos / Mejoras Planeadas

1. **Reentrenamiento del Modelo**: Actualizar RF con últimos datos de ventas
2. **A/B Testing**: Comparar impacto de recomendaciones en tasa de cierre
3. **Feedback Loop**: Registrar si asesor siguió recomendación → impacto en venta
4. **Más Agentes**: Implementar para retención, upsell, churn
5. **Integración API**: Exponer predicciones via API REST para integraciones externas

---

**Documento Generado**: 2026-05-16  
**Versión**: 1.0  
**Autor**: GitHub Copilot

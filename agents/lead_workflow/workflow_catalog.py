"""Catálogo del grafo multiagente: nodos, agentes, herramientas y sub-agentes de scoring."""

AGENT_TO_NODE = {
    "lead_scoring": "scoring",
    "commercial_assistant": "commercial",
    "recovery_agent": "recovery",
    "closing_agent": "completed",
    "management_agent": "management",
}

NODE_INDEX = {
    "scoring": 0,
    "assignment": 1,
    "commercial": 2,
    "recovery": 3,
    "closing": 4,
    "completed": 5,
    "dead": 6,
}

SCORING_SUB_AGENTS = [
    {
        "agent": "costo_adquisicion_agent",
        "label": "Costo de adquisición",
        "tools": [
            "SQL: marketing_campaigns.inversion",
            "SQL: ventas_concretadas",
            "SQL: leads + canal_id",
            "Calc: CALC = DGA / NLC",
        ],
    },
    {
        "agent": "tasa_adquisicion_agent",
        "label": "Tasa de adquisición",
        "tools": [
            "SQL: leads por canal",
            "SQL: seguimientos (embudo)",
            "SQL: ventas_concretadas por canal",
            "Calc: TDA = (NLC / NLO) × 100",
        ],
    },
    {
        "agent": "tasa_retencion_agent",
        "label": "Tasa de retención",
        "tools": [
            "SQL: compras históricas lead",
            "SQL: días último seguimiento",
            "Calc: TDR score por lead",
        ],
    },
    {
        "agent": "tasa_abandono_agent",
        "label": "Tasa de abandono",
        "tools": [
            "Calc: TDA = 100 − TDR",
            "SQL: inactividad del lead",
            "Calc: riesgo_abandono + acciones",
        ],
    },
]

PIPELINE = [
    {
        "node": "scoring",
        "agent": "lead_scoring",
        "label": "Scoring inicial",
        "description": "Orquestador invoca 4 agentes de análisis y calcula score global.",
        "tools": ["LeadScoringAgent.analyze()", "lead_agent_state.upsert"],
        "sub_agents": SCORING_SUB_AGENTS,
    },
    {
        "node": "assignment",
        "agent": "commercial_assistant",
        "label": "Asignación asesor",
        "description": "Asigna lead al asesor con menor carga según score.",
        "tools": [
            "SQL: usuarios + roles (asesor/gerente)",
            "SQL: COUNT leads activos por asesor",
            "UPDATE: leads.asignado_a",
        ],
        "sub_agents": [],
    },
    {
        "node": "commercial",
        "agent": "commercial_assistant",
        "label": "Contacto comercial",
        "description": "1er y 2do contacto (email/WhatsApp/llamada).",
        "tools": [
            "ChannelPicker: email | whatsapp | call",
            "Template: mensaje comercial por intento",
            "INSERT: agent_interactions",
            "Schedule: next_action_date",
        ],
        "sub_agents": [],
    },
    {
        "node": "recovery",
        "agent": "recovery_agent",
        "label": "Recuperación",
        "description": "Hasta 2 intentos alternativos si no hay respuesta.",
        "tools": [
            "Strategy: email reactivación",
            "Strategy: whatsapp caso éxito",
            "INSERT: agent_interactions",
            "Transition: venta_muerta si agota intentos",
        ],
        "sub_agents": [],
    },
    {
        "node": "closing",
        "agent": "closing_agent",
        "label": "Cierre",
        "description": "Propuesta y negociación de objeciones.",
        "tools": [
            "Generate: propuesta comercial",
            "Score-aware: condiciones según prioridad",
        ],
        "sub_agents": [],
    },
    {
        "node": "completed",
        "agent": "closing_agent",
        "label": "Venta registrada",
        "description": "Registra venta o no venta en CRM.",
        "tools": [
            "INSERT: ventas_concretadas",
            "UPDATE: lead_agent_state → completed",
        ],
        "sub_agents": [],
    },
    {
        "node": "dead",
        "agent": "recovery_agent",
        "label": "Venta muerta",
        "description": "Lead archivado tras agotar recuperación.",
        "tools": ["UPDATE: workflow_status=dead", "Log: motivo abandono"],
        "sub_agents": [],
    },
]

NODE_CATALOG = {item["node"]: item for item in PIPELINE}


def get_node_catalog(node):
    return NODE_CATALOG.get(node)


def get_workflow_catalog():
    return {
        "orchestrator": "LeadWorkflowOrchestrator",
        "pattern": "StateGraph (scoring → assignment → commercial ⇄ recovery → closing | dead | completed)",
        "pipeline": PIPELINE,
        "scoring_weights": {
            "costo_adquisicion": 0.30,
            "tasa_adquisicion": 0.30,
            "tasa_retencion": 0.20,
            "tasa_abandono": 0.20,
        },
    }


def enrich_scoring_step(scoring_result):
    """Mapea salidas de scoring a sub-agentes con score y detalle."""
    outputs = scoring_result.get("agent_outputs") or {}
    mapping = [
        ("costo_adquisicion_agent", "costo_adquisicion", "roi_score", "costo_adquisicion"),
        ("tasa_adquisicion_agent", "tasa_adquisicion", "acquisition_score", "tasa_adquisicion"),
        ("tasa_retencion_agent", "tasa_retencion", "retention_score", "tasa_retencion"),
        ("tasa_abandono_agent", "tasa_abandono", "abandonment_score", "tasa_abandono"),
    ]
    enriched = []
    sub_by_agent = {s["agent"]: s for s in SCORING_SUB_AGENTS}
    for agent_key, out_key, score_field, detail_field in mapping:
        block = outputs.get(out_key) or {}
        meta = sub_by_agent.get(agent_key, {})
        enriched.append(
            {
                "agent": agent_key,
                "label": meta.get("label", agent_key),
                "tools": meta.get("tools", []),
                "score": block.get(score_field),
                "detail": block.get(detail_field),
                "output": block,
            }
        )
    return enriched

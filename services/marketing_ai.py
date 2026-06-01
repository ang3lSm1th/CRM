import json
import os
import uuid

try:
    from crewai import Agent, Crew, Process, Task
except Exception:
    Agent = None
    Crew = None
    Process = None
    Task = None


def _emit(*_args, **_kwargs):
    return ""


def _get_llm() -> str:
    return "groq/llama-3.1-8b-instant"


def _parse_json_result(raw_result):
    text = (raw_result or "").strip()
    if not text:
        return {}

    try:
        return json.loads(text)
    except Exception:
        pass

    if "```" in text:
        chunks = [c.strip() for c in text.split("```") if c.strip()]
        for chunk in chunks:
            candidate = chunk
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            try:
                return json.loads(candidate)
            except Exception:
                continue

    return {}


def _is_crewai_enabled():
    raw = (os.getenv("MARKETING_CREWAI_ENABLED") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _format_number(value, suffix=""):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def _fallback_analysis(module):
    value = module.get("value")
    title = module.get("title") or "OKR"
    context = module.get("context") or []
    direction = module.get("direction") or "neutral"

    if value is None:
        summary = f"{title}: faltan datos para emitir una lectura confiable."
        recommendation = (
            "Completa la configuración pendiente y vuelve a revisar el indicador."
        )
    elif direction == "up":
        summary = f"{title}: el indicador avanza en la dirección correcta con {_format_number(value, '%')}."
        recommendation = "Mantén el canal actual y revisa qué fuente de demanda está empujando el crecimiento."
    elif direction == "down":
        summary = (
            f"{title}: el indicador está bajo presión con {_format_number(value, '%')}."
        )
        recommendation = "Revisa segmentación, inversión y calidad del seguimiento comercial para corregir la caída."
    else:
        summary = f"{title}: el indicador actual es {_format_number(value, '%')}."
        recommendation = "Usa el detalle del módulo para validar si el resultado está alineado con la meta del negocio."

    evidence = "; ".join(context[:3]) if context else "Sin contexto adicional."
    return {
        "engine": "local",
        "agent": f"Agente {title}",
        "summary": summary,
        "recommendation": recommendation,
        "evidence": evidence,
    }


def _run_local_analysis(module, brand, reason):
    title = module.get("title") or "OKR"
    session_id = f"okr-local-{uuid.uuid4().hex[:8]}"
    orchestrator_name = "Orquestador-Marketing"
    analyst_name = f"AnalistaLocal[{title}]"

    # 1. Orquestador asigna tarea (Contract Net)
    _emit(
        sender=orchestrator_name,
        receiver=analyst_name,
        method="assign_local_analysis",
        params={
            "module_id": module.get("id"),
            "brand": brand,
            "reason": reason,
            "engine": "local",
        },
        msg_type="request",
        session_id=session_id,
    )

    # 2. Agente local acepta la tarea
    _emit(
        sender=analyst_name,
        receiver=orchestrator_name,
        method="task_accepted",
        params={"module_id": module.get("id"), "llm": "local-rules-engine"},
        msg_type="response",
        session_id=session_id,
    )

    result = _fallback_analysis(module)

    # 3. Agente local publica hallazgo (handoff HTN)
    _emit(
        sender=analyst_name,
        receiver=analyst_name,
        method="publish_local_insight",
        params={"module_id": module.get("id"), "engine": "local"},
        result={"summary_preview": result["summary"][:80]},
        msg_type="notification",
        session_id=session_id,
    )

    # 4. Orquestador recibe resultado
    _emit(
        sender=analyst_name,
        receiver=orchestrator_name,
        method="local_analysis_completed",
        params={"module_id": module.get("id"), "engine": "local"},
        result={
            "summary_preview": result["summary"][:80],
            "recommendation_preview": result["recommendation"][:80],
        },
        msg_type="response",
        session_id=session_id,
    )
    return result


def _run_crewai(module, brand):
    if not (Agent and Crew and Task and Process):
        return _run_local_analysis(module, brand, "crewai_unavailable")
    if not _is_crewai_enabled() or not os.getenv("GROQ_API_KEY"):
        return _run_local_analysis(module, brand, "crewai_disabled_or_missing_key")

    session_id = f"okr-{uuid.uuid4().hex[:8]}"
    title = module.get("title") or "OKR"
    orchestrator_name = "Orquestador-Marketing"
    analyst_name = f"Analista[{title}]"
    reviewer_name = f"Revisor[{title}]"

    prompt_payload = {
        "brand": brand,
        "module": {
            "title": title,
            "formula": module.get("formula"),
            "value": module.get("value"),
            "value_label": module.get("value_label"),
            "context": module.get("context") or [],
            "target": module.get("target"),
        },
    }

    # 1. Orquestador asigna tarea (Contract Net Protocol)
    _emit(
        sender=orchestrator_name,
        receiver=analyst_name,
        method="assign_task",
        params={"module_id": module.get("id"), "brand": brand, "engine": "crewai"},
        msg_type="request",
        session_id=session_id,
    )

    try:
        llm = _get_llm()

        analyst = Agent(
            role=f"Analista de marketing para {title}",
            goal="Detectar hallazgos accionables y explicar si el indicador está sano o requiere corrección.",
            backstory="Especialista en performance marketing, funnel comercial y lectura ejecutiva de KPIs.",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )

        reviewer = Agent(
            role="Revisor de consistencia",
            goal="Validar que el análisis sea concreto, útil y basado solo en los datos entregados.",
            backstory="Lider de analítica que resume hallazgos para equipos comerciales y de marketing.",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )

        analysis_task = Task(
            description=(
                "Analiza este módulo OKR de marketing y responde en JSON con las claves "
                "summary, recommendation y evidence. Mantén cada campo en una sola frase clara. "
                f"Datos: {json.dumps(prompt_payload, ensure_ascii=False)}"
            ),
            expected_output="JSON con summary, recommendation y evidence.",
            agent=analyst,
        )
        review_task = Task(
            description=(
                "Revisa el JSON anterior. Si está bien, devuelve el mismo JSON. "
                "Si no, corrígelo y devuelve un JSON final con summary, recommendation y evidence."
            ),
            expected_output="JSON final con summary, recommendation y evidence.",
            agent=reviewer,
            context=[analysis_task],
        )

        # 2. Analista acepta la tarea
        _emit(
            sender=analyst_name,
            receiver=orchestrator_name,
            method="task_accepted",
            params={"module_id": module.get("id"), "llm": llm},
            msg_type="response",
            session_id=session_id,
        )

        crew = Crew(
            agents=[analyst, reviewer],
            tasks=[analysis_task, review_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        raw_output = str(result)
        data = _parse_json_result(raw_output)
        fb = _fallback_analysis(module)

        # 3. Analista hace handoff de contexto al Revisor (HTN)
        _emit(
            sender=analyst_name,
            receiver=reviewer_name,
            method="transfer_context",
            params={
                "module_id": module.get("id"),
                "context_keys": list(data.keys()) if data else [],
            },
            result={"raw_length": len(raw_output)},
            msg_type="notification",
            session_id=session_id,
        )

        final = {
            "engine": "crewai",
            "agent": f"CrewAI · {title}",
            "summary": str(data.get("summary") or "").strip() or fb["summary"],
            "recommendation": str(data.get("recommendation") or "").strip()
            or fb["recommendation"],
            "evidence": str(data.get("evidence") or "").strip() or fb["evidence"],
        }

        # 4. Revisor devuelve resultado validado al Orquestador
        _emit(
            sender=reviewer_name,
            receiver=orchestrator_name,
            method="analysis_completed",
            params={"module_id": module.get("id")},
            result={"engine": "crewai", "summary_preview": final["summary"][:80]},
            msg_type="response",
            session_id=session_id,
        )
        return final
    except Exception:
        return _run_local_analysis(module, brand, "crewai_execution_failed")


def generate_marketing_okr_analyses(brand, modules):
    analyses = {}
    engine = "local"
    for module in modules:
        item = _run_crewai(module, brand)
        if item.get("engine") == "crewai":
            engine = "crewai"
        analyses[module.get("id")] = item
    return {
        "engine": engine,
        "items": analyses,
    }

"""Cliente LLM para cotizaciones — solo Cursor Cloud Agents API (HTTP).

Evita el bridge local del SDK (falla en Windows con WinError 10038).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

API_BASE = "https://api.cursor.com"
SYSTEM_ORBES = (
    "Eres un agente comercial formal de Orbes Agrícola S.A.C. (Perú). "
    "Responde SOLO con JSON válido, sin markdown ni texto extra. "
    "NO edites archivos. NO uses herramientas. Solo responde el JSON."
)


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _api_request(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    api_key = _env("CURSOR_API_KEY")
    if not api_key:
        raise RuntimeError("CURSOR_API_KEY no configurada")

    url = f"{API_BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    if body is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        raise RuntimeError(f"Cursor API HTTP {exc.code}: {detail or exc.reason}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cursor API sin conexión: {exc.reason}") from None


def _archive_agent(agent_id: str) -> None:
    if not agent_id:
        return
    try:
        _api_request("POST", f"/v1/agents/{agent_id}/archive")
    except Exception as exc:
        logger.debug("No se pudo archivar agente %s: %s", agent_id, exc)


def _cursor_cloud_prompt(prompt: str) -> str:
    model = _env("CURSOR_MODEL", "composer-2.5")
    timeout = int(_env("CURSOR_AGENT_TIMEOUT", "180") or "180")
    poll_every = float(_env("CURSOR_POLL_SECONDS", "2") or "2")

    full_prompt = f"{SYSTEM_ORBES}\n\n{prompt}"
    created = _api_request(
        "POST",
        "/v1/agents",
        {
            "prompt": {"text": full_prompt},
            "model": {"id": model},
            "name": "CRM Orbes cotizacion",
        },
    )
    agent = created.get("agent") or {}
    run = created.get("run") or {}
    agent_id = agent.get("id") or ""
    run_id = run.get("id") or agent.get("latestRunId") or ""
    if not agent_id or not run_id:
        raise RuntimeError("Cursor API no devolvió agent/run id")

    deadline = time.monotonic() + timeout
    terminal = {"FINISHED", "ERROR", "FAILED", "CANCELLED", "EXPIRED"}
    last: dict[str, Any] = {}
    try:
        while time.monotonic() < deadline:
            last = _api_request("GET", f"/v1/agents/{agent_id}/runs/{run_id}")
            status = str(last.get("status") or "").upper()
            if status in terminal:
                if status != "FINISHED":
                    raise RuntimeError(f"Cursor run terminó en {status}")
                result = last.get("result")
                if isinstance(result, dict):
                    text = result.get("text") or result.get("result") or ""
                else:
                    text = result or ""
                text = str(text).strip()
                if not text:
                    raise RuntimeError("Cursor terminó sin texto de cotización")
                return text
            time.sleep(poll_every)
        raise RuntimeError(f"Cursor timeout ({timeout}s)")
    finally:
        _archive_agent(agent_id)


def generate_json(prompt: str) -> tuple[dict[str, Any], str]:
    """Solo Cursor Cloud API. Returns (parsed_dict, 'cursor')."""
    text = _cursor_cloud_prompt(prompt)
    data = _extract_json(text)
    if not data:
        logger.warning("Cursor respuesta no-JSON: %s", text[:300])
        raise RuntimeError("Cursor no devolvió una cotización válida")
    return data, "cursor"

"""Cliente HTTP del orquestador hacia el microservicio de agentes."""

import logging
import os

import requests

logger = logging.getLogger(__name__)


class AgentServiceClient:
    def __init__(self, base_url=None, secret=None, timeout=None):
        self.base_url = (base_url or os.getenv("AGENT_SERVICE_URL", "http://127.0.0.1:8001")).rstrip("/")
        self.secret = secret if secret is not None else os.getenv("INTERNAL_SERVICE_SECRET", "")
        self.timeout = int(timeout or os.getenv("AGENT_SERVICE_TIMEOUT", "120"))

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Internal-Secret"] = self.secret
        return headers

    def _post(self, path, payload):
        url = f"{self.base_url}/agents{path}"
        try:
            res = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            data = res.json() if res.content else {}
            if not res.ok:
                msg = data.get("error") or f"HTTP {res.status_code}"
                raise RuntimeError(f"Agent service error ({path}): {msg}")
            if not data.get("ok", True):
                raise RuntimeError(data.get("error") or f"Agent service falló en {path}")
            return data
        except requests.RequestException as exc:
            logger.exception("Error HTTP hacia agent-services %s", path)
            raise RuntimeError(f"No se pudo contactar agent-services en {url}: {exc}") from exc

    def scoring_analyze(self, lead_id):
        return self._post("/scoring/analyze", {"lead_id": lead_id})["result"]

    def commercial_assign(self, lead_id, score_data):
        return self._post(
            "/commercial/assign",
            {"lead_id": lead_id, "score_data": score_data},
        )["result"]

    def commercial_contact(self, lead_id, attempt, score_data):
        return self._post(
            "/commercial/contact",
            {"lead_id": lead_id, "attempt": attempt, "score_data": score_data},
        )["result"]

    def recovery_attempt(self, lead_id, recovery_attempt):
        return self._post(
            "/recovery/attempt",
            {"lead_id": lead_id, "recovery_attempt": recovery_attempt},
        )["result"]

    def recovery_mark_dead(self, lead_id):
        return self._post("/recovery/mark-dead", {"lead_id": lead_id})["result"]

    def closing_run(self, lead_id, score_data, *, sale_won=True, monto=0, motivo_no_venta=None):
        return self._post(
            "/closing/run",
            {
                "lead_id": lead_id,
                "score_data": score_data,
                "sale_won": sale_won,
                "monto": monto,
                "motivo_no_venta": motivo_no_venta,
            },
        )

    def health_check(self):
        url = f"{self.base_url}/healthz"
        res = requests.get(url, timeout=5)
        return res.ok

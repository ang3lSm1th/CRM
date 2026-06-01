import os
from openai import OpenAI

try:
    from litellm import completion as litellm_completion
except Exception:
    litellm_completion = None


class LLMAgent:
    """Agente para preguntas generales con OpenAI y fallback opcional a LiteLLM."""

    def __init__(self):
        self.model = os.getenv("AGENT_MODEL", "gpt-3.5-turbo")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    def _build_messages(self, question):
        return [
            {
                "role": "system",
                "content": (
                    "Eres un asesor para CRM comercial y marketing. "
                    "Responde en espanol claro, accionable y breve."
                ),
            },
            {"role": "user", "content": question},
        ]

    def _call_openai(self, question):
        client = OpenAI(api_key=self.openai_api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(question),
            temperature=0.3,
        )
        msg = response.choices[0].message.content if response.choices else ""
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", 0) if usage else 0
        return msg or "No pude generar una respuesta en este momento.", int(tokens or 0)

    def _call_litellm_groq(self, question):
        if not litellm_completion or not self.groq_api_key:
            return None, 0

        response = litellm_completion(
            model="groq/llama-3.1-8b-instant",
            api_key=self.groq_api_key,
            messages=self._build_messages(question),
            temperature=0.3,
        )
        msg = response.choices[0].message.content if response.choices else ""
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", 0) if usage else 0
        return msg or "No pude generar una respuesta en este momento.", int(tokens or 0)

    def handle(self, question):
        # Try OpenAI if key looks valid (non-empty, not a comment)
        openai_ok = bool(self.openai_api_key) and not self.openai_api_key.startswith(
            "#"
        )
        if openai_ok:
            try:
                answer, tokens = self._call_openai(question)
                return {
                    "ok": True,
                    "agent": "llm_agent",
                    "intent": "llm",
                    "answer": answer,
                    "tokens": tokens,
                    "provider": "openai",
                    "model": self.model,
                }
            except Exception:
                # OpenAI failed (invalid key, quota, etc.) — fall through to Groq
                pass

        # Fallback: Groq via LiteLLM
        try:
            fallback_answer, fallback_tokens = self._call_litellm_groq(question)
            if fallback_answer:
                return {
                    "ok": True,
                    "agent": "llm_agent",
                    "intent": "llm",
                    "answer": fallback_answer,
                    "tokens": fallback_tokens,
                    "provider": "groq_litellm",
                    "model": "groq/llama-3.1-8b-instant",
                }
        except Exception as exc:
            return {
                "ok": False,
                "agent": "llm_agent",
                "error": f"Fallo al consultar el LLM (Groq): {exc}",
            }

        return {
            "ok": False,
            "agent": "llm_agent",
            "error": "No hay credenciales válidas para OpenAI ni para Groq.",
        }

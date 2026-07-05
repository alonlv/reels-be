import httpx

from app.config import get_settings
from app.llm.prompts import (
    EXPLAIN_SYSTEM,
    SUMMARIZE_SYSTEM,
    coerce_explanation,
    explain_user,
    summarize_user,
)


class OllamaProvider:
    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            f"{s.ollama_base_url}/api/chat",
            json={
                "model": s.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": summarize_user(title, text)},
                ],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    def explain(self, title: str, text: str) -> dict:
        s = get_settings()
        resp = httpx.post(
            f"{s.ollama_base_url}/api/chat",
            json={
                "model": s.ollama_model,
                "stream": False,
                # Ask Ollama to constrain output to JSON so the short/long
                # split parses reliably even on small local models.
                "format": "json",
                "messages": [
                    {"role": "system", "content": EXPLAIN_SYSTEM},
                    {"role": "user", "content": explain_user(title, text)},
                ],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return coerce_explanation(resp.json()["message"]["content"])

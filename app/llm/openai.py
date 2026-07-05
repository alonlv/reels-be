import httpx

from app.config import get_settings
from app.llm.prompts import (
    EXPLAIN_SYSTEM,
    SUMMARIZE_SYSTEM,
    coerce_explanation,
    explain_user,
    summarize_user,
)


class OpenAIProvider:
    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"authorization": f"Bearer {s.openai_api_key or ''}"},
            json={
                "model": s.openai_model,
                "messages": [
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": summarize_user(title, text)},
                ],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def explain(self, title: str, text: str) -> dict:
        s = get_settings()
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"authorization": f"Bearer {s.openai_api_key or ''}"},
            json={
                "model": s.openai_model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": EXPLAIN_SYSTEM},
                    {"role": "user", "content": explain_user(title, text)},
                ],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return coerce_explanation(resp.json()["choices"][0]["message"]["content"])

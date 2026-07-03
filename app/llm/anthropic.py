import httpx

from app.config import get_settings
from app.llm.prompts import SUMMARIZE_SYSTEM, summarize_user


class AnthropicProvider:
    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": s.anthropic_api_key or "",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": s.anthropic_model,
                "max_tokens": 300,
                "system": SUMMARIZE_SYSTEM,
                "messages": [{"role": "user", "content": summarize_user(title, text)}],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()

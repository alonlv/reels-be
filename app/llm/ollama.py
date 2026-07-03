import httpx

from app.config import get_settings
from app.llm.prompts import SUMMARIZE_SYSTEM, summarize_user


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

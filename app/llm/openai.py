import httpx

from app.config import get_settings
from app.llm.prompts import SUMMARIZE_SYSTEM, summarize_user


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

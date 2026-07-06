import httpx

from app.config import get_settings
from app.llm.prompts import (
    EXPLAIN_SYSTEM,
    SUMMARIZE_SYSTEM,
    coerce_explanation,
    explain_user,
    summarize_user,
)


class AzureFunctionProvider:
    """Delegate generation to an HTTP-triggered Azure Function.

    The function is treated as a thin LLM gateway: we POST the system prompt and
    the user prompt, and it returns the model's text under ``content`` (a bare
    string body is also accepted). Whatever model the function wraps —
    Azure OpenAI, a hosted open-weights model, etc. — stays behind the function,
    so rotating models is a deployment concern, not a code change here.

    Auth uses the standard Azure Functions key, sent as ``x-functions-key`` when
    ``AZURE_FUNCTION_KEY`` is configured.
    """

    def _post(self, task: str, system: str, prompt: str) -> str:
        s = get_settings()
        headers = {"content-type": "application/json"}
        if s.azure_function_key:
            headers["x-functions-key"] = s.azure_function_key
        resp = httpx.post(
            s.azure_function_url or "",
            headers=headers,
            json={"task": task, "system": system, "prompt": prompt},
            timeout=120.0,
        )
        resp.raise_for_status()
        return _extract_text(resp)

    def summarize(self, title: str, text: str) -> str:
        return self._post(
            "summarize", SUMMARIZE_SYSTEM, summarize_user(title, text)
        ).strip()

    def explain(self, title: str, text: str) -> dict:
        return coerce_explanation(
            self._post("explain", EXPLAIN_SYSTEM, explain_user(title, text))
        )


def _extract_text(resp: httpx.Response) -> str:
    """Pull the generated text out of the function's response.

    Accepts a JSON object with a ``content`` (or ``text``/``output``) field, or a
    plain-text body, so the function is free to keep its response shape simple.
    """
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        data = resp.json()
        if isinstance(data, dict):
            for key in ("content", "text", "output", "result"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        if isinstance(data, str):
            return data
    return resp.text

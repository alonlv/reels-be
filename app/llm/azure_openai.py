import httpx

from app.config import get_settings
from app.llm.prompts import (
    EXPLAIN_SYSTEM,
    SUMMARIZE_SYSTEM,
    coerce_explanation,
    explain_user,
    summarize_user,
)


class AzureOpenAIProvider:
    """Azure OpenAI / Azure AI Foundry chat-completions provider.

    Talks to the same REST endpoint the ``openai.AzureOpenAI`` client uses:

        POST {endpoint}/openai/deployments/{deployment}/chat/completions
             ?api-version={version}
        header: api-key: {key}

    The model is selected by the Azure *deployment* name (in the URL), not the
    request body, so ``AZURE_OPENAI_DEPLOYMENT`` names the deployment you created
    in the portal. Kept on httpx to match the other providers (no extra SDK dep).
    """

    def _url(self) -> str:
        s = get_settings()
        endpoint = (s.azure_openai_endpoint or "").rstrip("/")
        return (
            f"{endpoint}/openai/deployments/{s.azure_openai_deployment}"
            f"/chat/completions?api-version={s.azure_openai_api_version}"
        )

    def summarize(self, title: str, text: str) -> str:
        s = get_settings()
        resp = httpx.post(
            self._url(),
            headers={"api-key": s.azure_openai_api_key or ""},
            json={
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
            self._url(),
            headers={"api-key": s.azure_openai_api_key or ""},
            json={
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

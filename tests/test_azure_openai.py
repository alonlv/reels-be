import pytest

import app.llm.azure_openai as az
from app.config import get_settings
from app.llm.azure_openai import AzureOpenAIProvider


class _Resp:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://ai-assistant-search-embedding-model.openai.azure.com/",
    )
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sub-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_summarize_hits_deployment_url_with_api_key(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _Resp("  a summary  ")

    monkeypatch.setattr(az.httpx, "post", fake_post)
    out = AzureOpenAIProvider().summarize("Title", "Body")

    assert out == "a summary"
    assert captured["url"] == (
        "https://ai-assistant-search-embedding-model.openai.azure.com/"
        "openai/deployments/gpt-4o-mini/chat/completions"
        "?api-version=2024-12-01-preview"
    )
    assert captured["headers"]["api-key"] == "sub-key"
    assert captured["json"]["messages"][0]["role"] == "system"


def test_explain_requests_json_and_coerces(monkeypatch):
    body = '{"short": "s", "long": "l", "technical": "t", "category": "product"}'
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Resp(body)

    monkeypatch.setattr(az.httpx, "post", fake_post)
    out = AzureOpenAIProvider().explain("T", "B")

    assert out == {"short": "s", "long": "l", "technical": "t", "category": "product"}
    assert captured["json"]["response_format"] == {"type": "json_object"}

import httpx
import pytest

import app.llm.azure_function as az
from app.config import get_settings
from app.llm.azure_function import AzureFunctionProvider


class _Resp:
    def __init__(self, json_body=None, text="", ctype="application/json"):
        self._json = json_body
        self.text = text
        self.headers = {"content-type": ctype}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setenv("AZURE_FUNCTION_URL", "https://fn.azurewebsites.net/api/llm")
    monkeypatch.setenv("AZURE_FUNCTION_KEY", "secret-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_summarize_posts_prompt_and_key(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _Resp(json_body={"content": "  a tidy summary  "})

    monkeypatch.setattr(az.httpx, "post", fake_post)
    out = AzureFunctionProvider().summarize("Title", "Body text")

    assert out == "a tidy summary"
    assert captured["url"] == "https://fn.azurewebsites.net/api/llm"
    assert captured["headers"]["x-functions-key"] == "secret-key"
    assert captured["json"]["task"] == "summarize"
    assert "Title" in captured["json"]["prompt"]


def test_explain_coerces_json_content(monkeypatch):
    body = {
        "content": '{"short": "s", "long": "l", "technical": "t", "category": "research"}'
    }
    monkeypatch.setattr(az.httpx, "post", lambda *a, **k: _Resp(json_body=body))
    out = AzureFunctionProvider().explain("T", "B")
    assert out == {"short": "s", "long": "l", "technical": "t", "category": "research"}


def test_accepts_plain_text_body(monkeypatch):
    monkeypatch.setattr(
        az.httpx,
        "post",
        lambda *a, **k: _Resp(text="just text", ctype="text/plain"),
    )
    assert AzureFunctionProvider().summarize("T", "B") == "just text"


def test_omits_key_header_when_unset(monkeypatch):
    monkeypatch.delenv("AZURE_FUNCTION_KEY", raising=False)
    get_settings.cache_clear()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _Resp(json_body={"content": "x"})

    monkeypatch.setattr(az.httpx, "post", fake_post)
    AzureFunctionProvider().summarize("T", "B")
    assert "x-functions-key" not in captured["headers"]

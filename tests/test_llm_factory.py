import pytest

from app.llm.factory import get_provider
from app.llm.ollama import OllamaProvider
from app.llm.azure_function import AzureFunctionProvider
from app.llm.azure_openai import AzureOpenAIProvider
from app.config import get_settings


def test_factory_defaults_to_ollama():
    get_settings.cache_clear()
    assert isinstance(get_provider(), OllamaProvider)


@pytest.mark.parametrize("value", ["azure_function", "azure-function", "azure", "AZURE"])
def test_factory_selects_azure_function(monkeypatch, value):
    monkeypatch.setenv("MODEL_PROVIDER", value)
    get_settings.cache_clear()
    assert isinstance(get_provider(), AzureFunctionProvider)
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "value", ["azure_openai", "azure-openai", "azure_foundry", "foundry", "AZURE_OPENAI"]
)
def test_factory_selects_azure_openai(monkeypatch, value):
    monkeypatch.setenv("MODEL_PROVIDER", value)
    get_settings.cache_clear()
    assert isinstance(get_provider(), AzureOpenAIProvider)
    get_settings.cache_clear()

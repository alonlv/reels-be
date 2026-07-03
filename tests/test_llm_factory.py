from app.llm.factory import get_provider
from app.llm.ollama import OllamaProvider
from app.config import get_settings


def test_factory_defaults_to_ollama():
    get_settings.cache_clear()
    assert isinstance(get_provider(), OllamaProvider)

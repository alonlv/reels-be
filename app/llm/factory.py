from app.config import get_settings
from app.llm.base import ModelProvider
from app.llm.anthropic import AnthropicProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider


def get_provider() -> ModelProvider:
    provider = get_settings().model_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()
    return OllamaProvider()

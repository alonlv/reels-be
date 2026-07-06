from app.config import get_settings
from app.llm.base import ModelProvider
from app.llm.anthropic import AnthropicProvider
from app.llm.azure_function import AzureFunctionProvider
from app.llm.azure_openai import AzureOpenAIProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider


def get_provider() -> ModelProvider:
    provider = get_settings().model_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider in ("azure_openai", "azure-openai", "azure_foundry", "foundry"):
        return AzureOpenAIProvider()
    if provider in ("azure_function", "azure-function", "azure"):
        return AzureFunctionProvider()
    return OllamaProvider()

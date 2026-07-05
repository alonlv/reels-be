from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./reels.db"
    model_provider: str = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "gemma2:2b"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "*"
    rate_limit_max: int = 5
    scan_cron: str = "0 * * * *"
    x_sync_interval_hours: int = 6
    x_bearer_token: str | None = None
    scan_enabled: bool = True
    # Generic admin login. Anyone who logs in with this password becomes the
    # admin and may edit/remove reels. Override in production.
    admin_password: str = "admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()

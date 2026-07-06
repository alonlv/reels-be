from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./reels.db"
    # Managed Postgres (e.g. Azure Database for PostgreSQL) typically requires
    # TLS. Set DB_SSLMODE=require in those deployments; leave unset for local
    # docker-compose Postgres and SQLite. pool_pre_ping recycles connections the
    # cloud provider silently drops so the first query after an idle period
    # doesn't fail.
    db_sslmode: str | None = None
    db_pool_pre_ping: bool = True

    model_provider: str = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "gemma2:2b"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Azure Function used as an LLM gateway (MODEL_PROVIDER=azure_function).
    azure_function_url: str | None = None
    azure_function_key: str | None = None

    cors_origins: str = "*"
    rate_limit_max: int = 5
    scan_cron: str = "0 * * * *"
    x_sync_interval_hours: int = 6
    x_bearer_token: str | None = None
    scan_enabled: bool = True

    # ---- Auth ----
    # Users are managed by SSO (Azure AD / Entra ID). password_auth_enabled is
    # the feature flag that re-enables the legacy username + admin-password flow
    # as a fallback (handy locally or if SSO is down). Both can be on at once.
    sso_enabled: bool = True
    password_auth_enabled: bool = True
    # OIDC/Entra config surfaced to the frontend so it can run the sign-in flow.
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    sso_scopes: str = "openid profile email"
    # OIDC userinfo endpoint used to resolve an access token to a user identity.
    sso_userinfo_url: str = "https://graph.microsoft.com/oidc/userinfo"
    # Comma-separated emails granted admin when they sign in via SSO. Everyone
    # else who signs in is an authenticated (non-admin) user.
    admin_emails: str = ""

    # Generic admin login for the password fallback. Anyone who logs in with this
    # password becomes the admin and may edit/remove reels. Override in production.
    admin_password: str = "admin"

    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

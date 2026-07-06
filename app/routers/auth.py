from fastapi import APIRouter, HTTPException

from app.auth import resolve_sso_identity, sso_authority
from app.config import get_settings
from app.schemas import AuthConfig, LoginResponse, SsoLoginRequest

router = APIRouter(prefix="/api/auth")


@router.get("/config", response_model=AuthConfig)
def auth_config() -> AuthConfig:
    """What sign-in methods the frontend should offer, and the SSO parameters."""
    s = get_settings()
    return AuthConfig(
        sso_enabled=s.sso_enabled,
        password_auth_enabled=s.password_auth_enabled,
        tenant_id=s.azure_tenant_id,
        client_id=s.azure_client_id,
        authority=sso_authority(),
        scopes=[scope for scope in s.sso_scopes.split() if scope],
    )


@router.post("/sso", response_model=LoginResponse)
def sso_login(payload: SsoLoginRequest) -> LoginResponse:
    """Exchange an Azure AD access token for a session.

    Users listed in ADMIN_EMAILS become admins (and receive the admin token so
    the existing edit/delete routes keep working); everyone else is an
    authenticated, non-admin user.
    """
    s = get_settings()
    if not s.sso_enabled:
        raise HTTPException(status_code=403, detail="SSO is disabled")
    email, name = resolve_sso_identity(payload.access_token)
    if email.lower() in s.admin_email_set():
        return LoginResponse(name=name, role="admin", token=s.admin_password)
    return LoginResponse(name=name, role="user", token=None)

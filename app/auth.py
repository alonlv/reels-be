"""SSO identity resolution for Azure AD / Entra ID.

The frontend runs the interactive OAuth2/OIDC flow (via MSAL) and hands us an
access token. We resolve that token to a user identity by calling the OIDC
userinfo endpoint rather than validating the JWT locally, which keeps this
dependency-free and works with any tenant configuration.
"""

import httpx
from fastapi import HTTPException

from app.config import get_settings


def sso_authority() -> str | None:
    """The Azure AD authority URL for the configured tenant, if any."""
    tenant = get_settings().azure_tenant_id
    return f"https://login.microsoftonline.com/{tenant}" if tenant else None


def _userinfo(access_token: str) -> dict:
    s = get_settings()
    resp = httpx.get(
        s.sso_userinfo_url,
        headers={"authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="invalid or expired SSO token")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=401, detail="unexpected SSO userinfo response")
    return data


def resolve_sso_identity(access_token: str) -> tuple[str, str]:
    """Resolve an access token to ``(email, display_name)``.

    Raises 401 if the token is missing/invalid or carries no email claim.
    Different Entra configurations surface the address under different claims,
    so we accept the common ones.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="missing SSO token")
    data = _userinfo(access_token)
    email = (
        data.get("email")
        or data.get("preferred_username")
        or data.get("upn")
        or ""
    ).strip()
    if not email:
        raise HTTPException(status_code=401, detail="SSO token has no email claim")
    name = (data.get("name") or email).strip()
    return email, name

from fastapi import Header, HTTPException

from app.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Reject the request unless it carries the admin token.

    Shared by the feed edit/delete routes and the source/scan management routes
    so "who may change the feed" is defined in exactly one place.
    """
    if not x_admin_token or x_admin_token != get_settings().admin_password:
        raise HTTPException(status_code=403, detail="admin only")

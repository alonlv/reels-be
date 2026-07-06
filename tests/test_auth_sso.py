import pytest

import app.auth as auth_mod
from app.config import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings():
    # Settings are lru_cached; clear around each test so env changes take effect
    # and don't leak into other tests.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mock_userinfo(monkeypatch, data):
    monkeypatch.setattr(auth_mod, "_userinfo", lambda token: data)


def test_auth_config_reports_methods(client, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-abc")
    monkeypatch.setenv("PASSWORD_AUTH_ENABLED", "false")
    get_settings.cache_clear()

    body = client.get("/api/auth/config").json()
    assert body["sso_enabled"] is True
    assert body["password_auth_enabled"] is False
    assert body["tenant_id"] == "tenant-123"
    assert body["client_id"] == "client-abc"
    assert body["authority"] == "https://login.microsoftonline.com/tenant-123"
    assert "openid" in body["scopes"]


def test_sso_admin_from_admin_emails(client, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@corp.com, other@corp.com")
    get_settings.cache_clear()
    _mock_userinfo(monkeypatch, {"email": "Boss@corp.com", "name": "The Boss"})

    body = client.post("/api/auth/sso", json={"access_token": "tok"}).json()
    assert body["role"] == "admin"
    assert body["name"] == "The Boss"
    assert body["token"] == "admin"  # reuses the admin token machinery


def test_sso_non_admin_is_plain_user(client, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@corp.com")
    get_settings.cache_clear()
    _mock_userinfo(monkeypatch, {"preferred_username": "dev@corp.com", "name": "Dev"})

    body = client.post("/api/auth/sso", json={"access_token": "tok"}).json()
    assert body["role"] == "user"
    assert body["token"] is None


def test_sso_disabled_returns_403(client, monkeypatch):
    monkeypatch.setenv("SSO_ENABLED", "false")
    get_settings.cache_clear()
    resp = client.post("/api/auth/sso", json={"access_token": "tok"})
    assert resp.status_code == 403


def test_sso_requires_email_claim(client, monkeypatch):
    _mock_userinfo(monkeypatch, {"name": "No Email"})
    resp = client.post("/api/auth/sso", json={"access_token": "tok"})
    assert resp.status_code == 401


def test_password_login_disabled_by_flag(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    resp = client.post("/api/login", json={"username": "x", "password": "admin"})
    assert resp.status_code == 403

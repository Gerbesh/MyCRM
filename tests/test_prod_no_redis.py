import os
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture()
def app_and_client(monkeypatch):
    # Гарантируем наличие корня проекта в sys.path
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Продакшн-окружение
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "codex-test-secret")
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("DB_NAME", "/tmp/test.db")
    monkeypatch.setenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/0")
    # Симулируем отсутствие Redis: форсим ошибки и убираем конфигурацию
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)
    monkeypatch.delenv("REDIS_DB", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)

    fake_redis = types.SimpleNamespace()

    def _raise(*args, **kwargs):
        raise Exception("simulated redis unavailable")

    fake_redis.from_url = _raise
    monkeypatch.setitem(sys.modules, "redis", fake_redis)

    from app import app  # импорт после monkeypatch

    app.testing = False
    app.config["TESTING"] = False
    client = app.test_client()
    return app, client


def test_https_redirect(app_and_client):
    app, client = app_and_client
    resp = client.get("/healthz", base_url="http://localhost", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers.get("Location", "").startswith("https://")


def test_security_headers(app_and_client):
    app, client = app_and_client
    resp = client.get("/healthz", base_url="https://localhost")
    # HSTS
    hsts = resp.headers.get("Strict-Transport-Security", "")
    assert "max-age=" in hsts
    # Базовые защитные заголовки
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "cdn.jsdelivr.net" in csp
    assert "cdn.redoc.ly" in csp
    assert "worker-src" in csp
    assert "blob:" in csp


def test_session_cookie_flags(app_and_client):
    app, client = app_and_client
    resp = client.get("/refresh_csrf", base_url="https://localhost")
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "Secure" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Strict" in set_cookie


def test_config_flags(app_and_client):
    app, client = app_and_client
    assert (
        app.config.get("ENV", "").lower() in ("production", "prod")
        or os.environ.get("FLASK_ENV") == "production"
    )
    assert app.config.get("REDIS_AVAILABLE") is False
    assert app.config.get("SESSION_TYPE") in ("filesystem", "sqlalchemy")

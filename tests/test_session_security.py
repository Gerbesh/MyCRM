"""Тесты механизмов защиты сессий."""

import hashlib
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from flask import session
from werkzeug.exceptions import Unauthorized

from session_security import SessionSecurity, require_secure_session


@pytest.fixture()
def frozen_now():
    """Фиксированное время для стабильных проверок."""
    return datetime(2024, 1, 10, 12, 0, 0)


def _expected_fingerprint(user_agent: str, accept: str, accept_language: str) -> str:
    """Утилита для вычисления ожидаемого отпечатка клиента."""
    raw = f"{user_agent}:{accept}:{accept_language}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def test_get_client_fingerprint_uses_stable_headers(app):
    """Отпечаток строится из User-Agent, Accept и Accept-Language."""
    headers = {
        "User-Agent": "TestBrowser/1.0",
        "Accept": "text/html",
        "Accept-Language": "ru,en",
    }

    with app.test_request_context("/", headers=headers):
        fingerprint = SessionSecurity.get_client_fingerprint()

    assert fingerprint == _expected_fingerprint("TestBrowser/1.0", "text/html", "ru,en")


def test_get_client_ip_prefers_forwarded_for(app):
    """X-Forwarded-For имеет наивысший приоритет при определении IP."""
    headers = {
        "X-Forwarded-For": "198.51.100.10, 203.0.113.5",
        "X-Real-IP": "203.0.113.100",
    }

    with app.test_request_context(
        "/", headers=headers, environ_base={"REMOTE_ADDR": "192.0.2.1"}
    ):
        assert SessionSecurity.get_client_ip() == "198.51.100.10"


def test_validate_session_updates_ip_and_fingerprint_on_change(app):
    """При мягких расхождениях IP/отпечатка значения обновляются без блокировки."""
    old_fingerprint = _expected_fingerprint("OldAgent", "text/html", "ru")

    headers = {
        "User-Agent": "NewAgent/5.0",
        "Accept": "application/json",
        "Accept-Language": "ru,en",
    }

    with app.test_request_context(
        "/dashboard",
        headers=headers,
        environ_base={"REMOTE_ADDR": "203.0.113.55"},
    ):
        session["session_id"] = "abc123"
        session["client_ip"] = "10.0.0.1"
        session["client_fingerprint"] = old_fingerprint
        session["created_at"] = datetime.utcnow().isoformat()
        session["last_activity"] = datetime.utcnow().isoformat()

        assert SessionSecurity.validate_session() is True
        assert session["client_ip"] == "203.0.113.55"
        assert session["client_fingerprint"] == _expected_fingerprint(
            "NewAgent/5.0", "application/json", "ru,en"
        )


def test_validate_session_detects_inactivity_timeout(app):
    """Застарелая активность приводит к завершению сессии."""
    with app.test_request_context(
        "/profile", environ_base={"REMOTE_ADDR": "192.0.2.15"}
    ):
        session["session_id"] = "inactive"
        session["client_ip"] = "192.0.2.15"
        session["client_fingerprint"] = _expected_fingerprint(
            "Agent", "text/html", "ru"
        )
        session["created_at"] = "2000-01-01T00:00:00"
        session["last_activity"] = "2000-01-01T00:00:00"

        assert SessionSecurity.validate_session() is False


def test_require_secure_session_aborts_when_validation_fails(app, monkeypatch):
    """Декоратор прерывает запрос и инвалидирует сессию при невалидных данных."""

    monkeypatch.setattr(
        SessionSecurity, "validate_session", staticmethod(lambda: False)
    )
    invalidate_mock = MagicMock()
    monkeypatch.setattr(
        SessionSecurity, "invalidate_session", staticmethod(invalidate_mock)
    )

    @require_secure_session
    def protected_view():
        return "ok"

    with app.test_request_context(
        "/sensitive", environ_base={"REMOTE_ADDR": "192.0.2.44"}
    ):
        with pytest.raises(Unauthorized):
            protected_view()

    invalidate_mock.assert_called_once()


def test_require_secure_session_updates_activity(app, monkeypatch, frozen_now):
    """Успешная проверка обновляет отметку активности и отдаёт результат обработчика."""
    monkeypatch.setattr(SessionSecurity, "validate_session", staticmethod(lambda: True))

    def fake_update():
        session["last_activity"] = frozen_now.isoformat()

    monkeypatch.setattr(
        SessionSecurity, "update_session_activity", staticmethod(fake_update)
    )

    @require_secure_session
    def protected_view():
        return "данные"

    with app.test_request_context(
        "/profile", environ_base={"REMOTE_ADDR": "198.51.100.5"}
    ):
        result = protected_view()
        assert session["last_activity"] == frozen_now.isoformat()
        assert result == "данные"

import logging

import config
import security_utils
from app import _should_create_all, app


def test_safe_log_masks_when_disabled(caplog):
    """Проверка маскировки токенов при LOG_SENSITIVE=false"""
    original = config.LOG_SENSITIVE
    config.LOG_SENSITIVE = False
    with caplog.at_level(logging.INFO):
        security_utils.safe_log(
            logging.getLogger("test"),
            logging.INFO,
            "token=abc123 session_id=xyz",
        )
    config.LOG_SENSITIVE = original
    assert "token=***" in caplog.text
    assert "session_id=***" in caplog.text


def test_safe_log_allows_when_enabled(caplog):
    """Проверка отсутствия маскировки при LOG_SENSITIVE=true"""
    original = config.LOG_SENSITIVE
    config.LOG_SENSITIVE = True
    with caplog.at_level(logging.INFO):
        security_utils.safe_log(
            logging.getLogger("test"),
            logging.INFO,
            "token=abc123",
        )
    config.LOG_SENSITIVE = original
    assert "token=abc123" in caplog.text


def test_should_create_all(monkeypatch):
    """db.create_all() не выполняется при FORCE_ALEMBIC_ONLY=true в проде"""
    monkeypatch.setenv("FLASK_ENV", "production")
    app.config["FORCE_ALEMBIC_ONLY"] = True
    assert _should_create_all() is False
    app.config["FORCE_ALEMBIC_ONLY"] = False
    assert _should_create_all() is True
    monkeypatch.setenv("FLASK_ENV", "development")
    app.config["FORCE_ALEMBIC_ONLY"] = True
    assert _should_create_all() is True


def test_hide_traceback(app):
    """При SHOW_DETAILED_ERRORS=false трейсбек скрыт"""
    from error_handler import handle_generic_error

    app.config["SHOW_DETAILED_ERRORS"] = False
    app.debug = False

    with app.test_request_context("/boom", headers={"Accept": "application/json"}):
        resp = handle_generic_error(RuntimeError("crash"))
    data = resp.get_json()
    assert data.get("detail") is None

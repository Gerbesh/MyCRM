import logging
from io import BytesIO
from types import SimpleNamespace

import pytest

import config
import security_utils as su


@pytest.fixture(autouse=True)
def restore_log_sensitive():
    original = config.LOG_SENSITIVE
    yield
    config.LOG_SENSITIVE = original


def make_file(data: bytes, name: str):
    stream = BytesIO(data)
    file = SimpleNamespace(stream=stream)
    file.read = stream.read
    file.seek = stream.seek
    file.tell = stream.tell
    file.filename = name
    return file


def test_validate_filename_rejects_paths():
    valid, error = su.validate_filename("../секрет.txt")
    assert not valid
    assert "Недопустимые" in error


def test_validate_filename_rejects_dangerous_char():
    valid, error = su.validate_filename("отчет<2024>.txt")
    assert not valid
    assert "Недопустимый символ" in error


def test_safe_filename_with_validation_returns_secure_name(monkeypatch):
    monkeypatch.setattr(su, "secure_filename", lambda value: value.replace(" ", "_"))
    safe_name, valid, error = su.safe_filename_with_validation("Отчет 2024.pdf")
    assert valid
    assert safe_name == "Отчет_2024.pdf"
    assert error == ""


def test_sanitize_input_detects_scripts():
    cleaned, valid, error = su.sanitize_input(
        "<script>alert('x')</script>", allow_html=True
    )
    assert not valid
    assert error == "Обнаружен подозрительный контент"
    assert cleaned is None


def test_validate_file_complete_checks_size(monkeypatch):
    monkeypatch.setattr(su, "MAX_FILE_SIZE", 10, raising=False)
    file = make_file(b"12345678901", "файл.txt")
    valid, error = su.validate_file_complete(file)
    assert not valid
    assert "превышает" in error


def test_validate_file_size_detects_empty_file():
    file = make_file(b"", "пусто.txt")
    valid, error = su.validate_file_size(file)
    assert not valid
    assert error == "Файл пустой"


def test_validate_file_extension_blocks_dangerous():
    valid, error = su.validate_file_extension("вирус.exe")
    assert not valid
    assert "Опасное" in error


def test_sanitize_log_data_masks_sensitive(monkeypatch):
    config.LOG_SENSITIVE = False
    payload = {
        "password": "secret",
        "token": "abcdef",
        "email": "user@example.com",
        "text": "Привет",
    }

    sanitized = su.sanitize_log_data(payload)

    assert "***FILTERED***" in sanitized
    assert "***EMAIL***@example.com" in sanitized
    assert "Привет" in sanitized


def test_sanitize_log_data_respects_sensitive_flag():
    config.LOG_SENSITIVE = True
    payload = {"password": "secret"}

    sanitized = su.sanitize_log_data(payload)

    assert sanitized == str(payload)


def test_safe_log_filters_arguments(monkeypatch, caplog):
    config.LOG_SENSITIVE = False
    logger = logging.getLogger("safe_log_test")

    with caplog.at_level(logging.INFO, logger="safe_log_test"):
        su.safe_log(logger, logging.INFO, {"password": "12345"})

    assert "***FILTERED***" in caplog.text


def test_safe_log_passes_through_when_sensitive(monkeypatch, caplog):
    config.LOG_SENSITIVE = True
    logger = logging.getLogger("safe_log_sensitive")

    with caplog.at_level(logging.INFO, logger="safe_log_sensitive"):
        su.safe_log(logger, logging.INFO, {"password": "12345"})

    assert "{'password': '12345'}" in caplog.text


def test_verify_recaptcha_v3_skips_without_secret(app):
    with app.app_context():
        app.config["RECAPTCHA_SECRET_KEY"] = ""
        app.testing = True
        ok, reason = su.verify_recaptcha_v3("token")

    assert ok
    assert reason == "skipped"


def test_verify_recaptcha_v3_requires_token(app):
    with app.app_context():
        app.config["RECAPTCHA_SECRET_KEY"] = "секрет"
        app.testing = True
        ok, reason = su.verify_recaptcha_v3(None)

    assert not ok
    assert reason == "missing_token"

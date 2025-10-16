import pytest

from error_handler import ErrorHandler, _safe_redirect, handle_generic_error


@pytest.fixture(autouse=True)
def _reset_debug(app):
    """Отключаем детальный вывод по умолчанию, чтобы тесты контролировали состояние."""
    original_debug = app.debug
    original_setting = app.config.get("SHOW_DETAILED_ERRORS")
    app.debug = False
    app.config["SHOW_DETAILED_ERRORS"] = False
    yield
    app.debug = original_debug
    if original_setting is None:
        app.config.pop("SHOW_DETAILED_ERRORS", None)
    else:
        app.config["SHOW_DETAILED_ERRORS"] = original_setting


def test_problem_response_rfc7807_payload(app):
    with app.test_request_context("/problem", headers={"Accept": "application/json"}):
        response = ErrorHandler.problem_response(
            422,
            "Ошибка обработки",
            detail="Некорректные данные",
            extra={"error_id": "abc123"},
        )

    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/problem+json"
    data = response.get_json()
    assert data == {
        "type": "about:blank",
        "title": "Ошибка обработки",
        "status": 422,
        "instance": "/problem",
        "detail": "Некорректные данные",
        "error_id": "abc123",
    }


def test_problem_response_omits_optional_detail(app):
    with app.test_request_context("/problem-no-detail"):
        response = ErrorHandler.problem_response(404, "Не найдено")

    data = response.get_json()
    assert data["status"] == 404
    assert data["instance"] == "/problem-no-detail"
    assert "detail" not in data


def test_safe_redirect_from_main_index_goes_to_login(app):
    with app.test_request_context(
        "/",
        headers={"Referer": "http://localhost/dashboard"},
    ):
        response = _safe_redirect()

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_safe_redirect_on_cyclic_referrer_goes_to_login(app):
    with app.test_request_context(
        "/dashboard",
        headers={"Referer": "http://localhost/dashboard"},
    ):
        response = _safe_redirect()

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_handle_generic_error_returns_problem_detail_json(app):
    with app.test_request_context(
        "/api/fail",
        headers={"Accept": "application/json"},
    ):
        response = handle_generic_error(RuntimeError("boom"))

    assert response.status_code == 500
    assert response.headers["Content-Type"] == "application/problem+json"
    payload = response.get_json()
    assert payload["title"] == "Произошла ошибка"
    assert "detail" not in payload
    assert payload["status"] == 500
    assert payload["instance"] == "/api/fail"


def test_handle_generic_error_returns_html_page_without_details(app):
    with app.test_request_context("/ui/fail"):
        rendered, status = handle_generic_error(RuntimeError("секрет"))

    assert status == 500
    assert "Произошла ошибка" in rendered
    assert "секрет" not in rendered

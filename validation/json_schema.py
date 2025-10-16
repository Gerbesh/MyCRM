"""
нициализация и выполнение валидации JSON по JSON Schema (draft 2020-12).

Поддерживает автоматическую проверку для эндпоинтов, описанных
в validation.schemas.ENDPOINT_SCHEMAS. При несоответствии возвращается
HTTP 400 с деталями ошибок.
"""

from __future__ import annotations

from typing import Any, Dict, List

from flask import jsonify, request
from flask_login import current_user
from jsonschema import Draft202012Validator, ValidationError

from .schemas import ENDPOINT_SCHEMAS, SCHEMAS


class JSONSchemasValidator:
    """Компилирует и валидирует данные по именованным схемам."""

    def __init__(self, schemas: Dict[str, Dict[str, Any]]):
        self._compiled: Dict[str, Draft202012Validator] = {
            name: Draft202012Validator(schema) for name, schema in schemas.items()
        }

    def validate(self, schema_key: str, data: Any) -> List[ValidationError]:
        validator = self._compiled.get(schema_key)
        if not validator:
            return []
        return list(validator.iter_errors(data))


_validator = JSONSchemasValidator(SCHEMAS)


def _format_errors(errors: List[ValidationError]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for e in errors:
        path = "/".join(map(str, e.path)) or "$"
        schema_path = "/".join(map(str, e.schema_path))
        formatted.append(
            {
                "path": path,
                "message": e.message,
                "validator": e.validator,
                "schema_path": schema_path,
            }
        )
    return formatted


def init_json_validation(app) -> None:
    """Подключить хук before_request для валидации JSON по схемам.

    Условия срабатывания:
    - Совпадает пара (request.endpoint, request.method) с ENDPOINT_SCHEMAS
    - В запросе присутствует JSON (request.get_json(silent=True) не None)
    - Пользователь аутентифицирован (чтобы не перехватывать редирект login_required)
    """

    @app.before_request
    def _validate_json_before_view():  # noqa: ANN001
        endpoint = request.endpoint or ""
        method = request.method.upper()

        schema_key = ENDPOINT_SCHEMAS.get((endpoint, method))
        if not schema_key:
            return None

        # Не вмешиваемся до прохождения аутентификации
        try:
            if not current_user.is_authenticated:  # type: ignore[attr-defined]
                return None
        except Exception:
            return None

        data = request.get_json(silent=True)
        # Если JSON не передан (например, используется форма) — не валидируем
        if data is None:
            return None

        errors = _validator.validate(schema_key, data)
        if errors:
            details = _format_errors(errors)
            return (
                jsonify(
                    {
                        "error": "Ошибка валидации JSON",
                        "details": details,
                    }
                ),
                400,
            )
        return None

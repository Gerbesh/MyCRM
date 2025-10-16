"""
JSON Schema (draft 2020-12) для ключевых JSON-запросов.

- Создание пользователя
- зменение объекта у заявки
- зменение статуса заявки

Схемы описаны в терминах официального черновика 2020-12 и
могут быть переиспользованы в автогенерации документации.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from utils.statuses import RequestStatus

SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"


def _user_roles() -> list[str]:
    # В проекте используются роли 'admin', 'user' и 'demo' (см. проверки в коде)
    return ["admin", "user", "demo"]


def build_schemas() -> Dict[str, Dict[str, Any]]:
    """Собрать словарь схем по ключам."""
    return {
        "user_create": {
            "$schema": SCHEMA_URI,
            "type": "object",
            "additionalProperties": False,
            "required": ["username", "password", "role"],
            "properties": {
                "username": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 50,
                    "pattern": r"^[a-zA-Z0-9_.-]+$",
                    "description": "Уникальное имя пользователя (латиница, цифры, _.-)",
                },
                "password": {
                    "type": "string",
                    "minLength": 8,
                    "maxLength": 255,
                    "description": "Пароль пользователя",
                },
                "role": {
                    "type": "string",
                    "enum": _user_roles(),
                    "description": "Роль пользователя",
                },
                "csrf_token": {
                    "type": "string",
                    "description": "CSRF-токен",
                },
            },
        },
        "request_change_object": {
            "$schema": SCHEMA_URI,
            "type": "object",
            "additionalProperties": False,
            "required": ["new_object_id"],
            "properties": {
                "new_object_id": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Новый ID объекта",
                },
                "csrf_token": {
                    "type": "string",
                    "description": "CSRF-токен",
                },
            },
        },
        "request_change_status": {
            "$schema": SCHEMA_URI,
            "type": "object",
            "additionalProperties": False,
            "required": ["status"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": RequestStatus.all(),
                    "description": "Новый статус заявки",
                },
                "csrf_token": {
                    "type": "string",
                    "description": "CSRF-токен",
                },
            },
        },
    }


SCHEMAS: Dict[str, Dict[str, Any]] = build_schemas()


# Карта соответствия эндпоинта+метода -> ключ схемы
# Значение request.endpoint принимает вид "<blueprint>.<function>"
ENDPOINT_SCHEMAS: Dict[Tuple[str, str], str] = {
    ("user.add_user", "POST"): "user_create",
    ("request_process.change_request_object", "POST"): "request_change_object",
    ("request_process.change_status", "POST"): "request_change_status",
}

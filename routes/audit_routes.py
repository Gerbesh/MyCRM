import json
import logging
import time

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app import _scrub

# Блюпринт для приёма клиентских событий
audit_bp = Blueprint("audit", __name__)
audit_logger = logging.getLogger("audit")

# CSRF защита применяется автоматически при регистрации блюпринта


@audit_bp.route("/audit/event", methods=["POST", "GET", "HEAD"])
def audit_event():
    """Получение клиентского события и запись в аудит без строгих проверок."""
    if request.method != "POST":
        # Для GET/HEAD отвечаем мягко, чтобы не засорять журнал ошибок
        if request.method == "HEAD":
            return ("", 204)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Отправка событий доступна только через POST",
                }
            ),
            405,
        )

    # Проверка дополнительного токена, если он задан в конфигурации
    token_required = current_app.config.get("AUDIT_EVENT_TOKEN")
    if token_required and request.headers.get("X-Audit-Token") != token_required:
        return ("", 403)

    payload = request.get_json(silent=True)
    if payload is None:
        # Поддержка запросов, отправленных через sendBeacon или простым текстом
        try:
            raw = request.get_data(as_text=True) or ""
            payload = json.loads(raw) if raw.strip().startswith("{") else {}
        except Exception:
            payload = {}

    user = current_user.username if current_user.is_authenticated else "аноним"

    event = {
        "type": "client_event",
        "ts": time.time(),
        "request_id": request.headers.get("X-Request-Id"),
        "user": user,
        "ip": request.remote_addr,
        "event": {"name": payload.get("name"), "data": _scrub(payload.get("data", {}))},
        "ua": request.headers.get("User-Agent"),
    }
    try:
        audit_logger.info(json.dumps(event, ensure_ascii=False))
    except Exception as e:
        current_app.logger.warning(f"audit_event log failed: {e}")

    # Отвечаем пустым телом и кодом 204, чтобы не провоцировать обработчики ошибок
    return ("", 204)

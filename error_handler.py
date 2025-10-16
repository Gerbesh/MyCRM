"""
Unified error handling module for CRM application
Provides consistent error responses across all routes
"""

import traceback
from datetime import datetime

from flask import current_app, jsonify, redirect, render_template, request, url_for


def _safe_redirect():
    """Безопасный редирект без циклов на main.index"""
    target = request.referrer or url_for("main.index")
    if request.endpoint == "main.index" or target == request.url:
        return redirect(url_for("auth.login"))
    return redirect(target)


class ErrorHandler:
    """Centralized error handling class"""

    @staticmethod
    def is_ajax_request():
        """Check if request is AJAX"""
        return request.headers.get("X-Requested-With") == "XMLHttpRequest"

    @staticmethod
    def is_json_request():
        """Check if request expects JSON response"""
        return request.headers.get("Content-Type", "").startswith(
            "application/json"
        ) or request.headers.get("Accept", "").startswith("application/json")

    @staticmethod
    def log_error(error, context=None):
        """Log error with context information"""
        error_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "url": request.url if request else "N/A",
            "method": request.method if request else "N/A",
            "user_agent": (
                request.headers.get("User-Agent", "N/A") if request else "N/A"
            ),
            "ip_address": request.remote_addr if request else "N/A",
            "context": context or {},
        }

        # Log full traceback for debugging
        if current_app.debug:
            error_info["traceback"] = traceback.format_exc()

        current_app.logger.error(f"Application Error: {error_info}")
        return error_info

    @staticmethod
    def problem_response(
        status_code, title, detail=None, type_uri="about:blank", extra=None
    ):
        """Формирует ответ в формате RFC 7807 (application/problem+json)"""
        problem = {
            "type": type_uri,
            "title": title,
            "status": status_code,
            "instance": request.path,
        }
        if detail:
            problem["detail"] = detail
        if extra:
            problem.update(extra)

        response = jsonify(problem)
        response.status_code = status_code
        response.headers["Content-Type"] = "application/problem+json"
        return response


# Набор чувствительных ключей, которые не должны светиться в UI
SENSITIVE_KEYS = {"password", "passwd", "pwd", "token", "csrf_token", "new_password"}


def _scrub_dict(d):
    if not isinstance(d, dict):
        return d
    redacted = {}
    for k, v in d.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted


def _build_error_details(error):
    """Собирает подробности ошибки: тип, сообщение, трейсбек и информацию о запросе"""
    try:
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    except Exception:
        try:
            tb = traceback.format_exc()
        except Exception:
            tb = None

    try:
        params = request.values.to_dict(flat=True)
    except Exception:
        params = {}

    details = {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": tb,
        "request": {
            "method": getattr(request, "method", None),
            "path": getattr(request, "path", None),
            "query": _scrub_dict(params),
            "user_agent": request.headers.get("User-Agent") if request else None,
            "ip": request.remote_addr if request else None,
            "request_id": getattr(
                getattr(request, "environ", {}), "get", lambda *_: None
            )("REQUEST_ID"),
        },
    }
    # Параллельно пробуем взять request_id из g, если он используется
    try:
        from flask import g

        details["request"]["request_id"] = getattr(
            g, "request_id", details["request"]["request_id"]
        )
    except Exception:
        pass
    return details


class ValidationError(Exception):
    """Custom validation error"""

    def __init__(self, message, field=None, code=400):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(self.message)


class BusinessLogicError(Exception):
    """Custom business logic error"""

    def __init__(self, message, code=422):
        self.message = message
        self.code = code
        super().__init__(self.message)


class SecurityError(Exception):
    """Custom security error"""

    def __init__(self, message, code=403):
        self.message = message
        self.code = code
        super().__init__(self.message)


def handle_validation_error(error):
    """Handle validation errors consistently"""
    error_info = ErrorHandler.log_error(error, {"type": "validation"})
    extra = {"error_id": error_info.get("timestamp")}
    if hasattr(error, "field") and error.field:
        extra["field"] = error.field

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            error.code,
            "Ошибка валидации",
            detail=error.message,
            extra=extra,
        )
    else:
        from flask import flash

        flash(error.message, "danger")
        # Перенаправляем на главную вместо дашборда, чтобы избежать циклов
        return _safe_redirect()


def handle_business_logic_error(error):
    """Handle business logic errors consistently"""
    error_info = ErrorHandler.log_error(error, {"type": "business_logic"})
    extra = {"error_id": error_info.get("timestamp")}

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            error.code,
            "Ошибка бизнес-логики",
            detail=error.message,
            extra=extra,
        )
    else:
        from flask import flash

        flash(error.message, "warning")
        # Перенаправляем на главную вместо дашборда, чтобы избежать циклов
        return _safe_redirect()


def handle_security_error(error):
    """Handle security errors consistently"""
    error_info = ErrorHandler.log_error(error, {"type": "security", "severity": "high"})
    extra = {"error_id": error_info.get("timestamp")}

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            error.code,
            "Доступ запрещен",
            detail="Недостаточно прав для выполнения операции",
            extra=extra,
        )
    else:
        from flask import flash

        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))


def handle_http_error(error):
    """Handle HTTP errors (404, 500, etc.)"""
    error_info = ErrorHandler.log_error(error, {"type": "http"})

    # Map common HTTP errors to user-friendly messages
    error_messages = {
        400: "Некорректный запрос — переданы неверные данные",
        401: "Требуется аутентификация",
        403: "Доступ запрещен",
        404: "Страница не найдена",
        405: "Метод не поддерживается",
        413: "Слишком большой файл",
        429: "Слишком много запросов",
        500: "Внутренняя ошибка сервера",
        502: "Плохой шлюз",
        503: "Сервис временно недоступен",
    }

    status_code = getattr(error, "code", 500)
    message = error_messages.get(status_code, "An error occurred")

    # Подготавливаем сводку деталей (для JSON и, при необходимости, для HTML)
    details = _build_error_details(error)
    extra = {"error_id": error_info.get("timestamp")}
    show_details = (
        current_app.config.get("SHOW_DETAILED_ERRORS", False) or current_app.debug
    )

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            status_code,
            message,
            detail=str(error) if show_details else None,
            extra=extra,
        )
    else:
        # В HTML передаем максимально подробные данные, если настроено
        return (
            render_template(
                "error.html",
                error_code=status_code,
                error_message=message,
                error_id=error_info.get("timestamp"),
                error_trace=details.get("traceback") if show_details else None,
                request_info=details.get("request") if show_details else None,
            ),
            status_code,
        )


def handle_database_error(error):
    """Handle database-related errors"""
    error_info = ErrorHandler.log_error(error, {"type": "database"})

    # Don't expose database details to users
    user_message = "Database operation failed. Please try again."
    extra = {"error_id": error_info.get("timestamp")}

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            500,
            "Ошибка базы данных",
            detail=user_message,
            extra=extra,
        )
    else:
        from flask import flash

        flash(user_message, "danger")
        # Перенаправляем на главную вместо дашборда, чтобы избежать циклов
        return _safe_redirect()


def handle_operational_error(error):
    """Обработка ошибок OperationalError"""
    error_info = ErrorHandler.log_error(
        error, {"type": "database", "kind": "operational"}
    )

    user_message = "База данных временно недоступна. Попробуйте позже."
    extra = {"error_id": error_info.get("timestamp")}

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            500,
            "Ошибка подключения к базе",
            detail=user_message,
            extra=extra,
        )
    else:
        from flask import flash

        flash(user_message, "danger")
        return _safe_redirect()


def handle_file_error(error):
    """Handle file upload/processing errors"""
    error_info = ErrorHandler.log_error(error, {"type": "file"})
    extra = {"error_id": error_info.get("timestamp")}

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            400,
            "Ошибка файла",
            detail=str(error),
            extra=extra,
        )
    else:
        from flask import flash

        flash(str(error), "danger")
        # Перенаправляем на главную вместо дашборда, чтобы избежать циклов
        return _safe_redirect()


def handle_generic_error(error):
    """Handle unexpected/generic errors"""
    error_info = ErrorHandler.log_error(error, {"type": "generic"})

    # Сообщение пользователю
    show_details = (
        current_app.config.get("SHOW_DETAILED_ERRORS", False) or current_app.debug
    )
    user_message = (
        f"Произошла ошибка: {str(error)}" if show_details else "Произошла ошибка"
    )

    details = _build_error_details(error)
    extra = {"error_id": error_info.get("timestamp")}

    if ErrorHandler.is_ajax_request() or ErrorHandler.is_json_request():
        return ErrorHandler.problem_response(
            500,
            user_message,
            detail=str(error) if show_details else None,
            extra=extra,
        )
    else:
        # Возвращаем подробную страницу ошибки вместо редиректа
        return (
            render_template(
                "error.html",
                error_code=500,
                error_message=user_message,
                error_id=error_info.get("timestamp"),
                error_trace=details.get("traceback") if show_details else None,
                request_info=details.get("request") if show_details else None,
            ),
            500,
        )


def register_error_handlers(app):
    """Register all error handlers with the Flask app"""

    # Custom application errors
    app.errorhandler(ValidationError)(handle_validation_error)
    app.errorhandler(BusinessLogicError)(handle_business_logic_error)
    app.errorhandler(SecurityError)(handle_security_error)

    # HTTP errors
    app.errorhandler(400)(handle_http_error)
    app.errorhandler(401)(handle_http_error)
    app.errorhandler(403)(handle_http_error)
    app.errorhandler(404)(handle_http_error)
    app.errorhandler(405)(handle_http_error)
    app.errorhandler(413)(handle_http_error)
    app.errorhandler(429)(handle_http_error)
    app.errorhandler(500)(handle_http_error)
    app.errorhandler(502)(handle_http_error)
    app.errorhandler(503)(handle_http_error)

    # Database errors
    from sqlalchemy.exc import (
        DataError,
        IntegrityError,
        OperationalError,
        SQLAlchemyError,
    )

    app.errorhandler(SQLAlchemyError)(handle_database_error)
    app.errorhandler(IntegrityError)(handle_database_error)
    app.errorhandler(DataError)(handle_database_error)
    app.errorhandler(OperationalError)(handle_operational_error)

    # Generic exception handler (catch-all)
    app.errorhandler(Exception)(handle_generic_error)


def safe_execute(func, *args, **kwargs):
    """
    Decorator/function to safely execute operations with consistent error handling
    """
    try:
        return func(*args, **kwargs)
    except ValidationError:
        raise  # Re-raise custom errors to be handled by specific handlers
    except BusinessLogicError:
        raise
    except SecurityError:
        raise
    except Exception as e:
        # Convert unexpected errors to generic errors
        current_app.logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
        raise Exception(f"Operation failed: {func.__name__}")


def validate_and_execute(validation_func, execution_func, *args, **kwargs):
    """
    Helper to validate inputs and execute function with proper error handling
    """
    try:
        # Run validation first
        if validation_func:
            validation_result = validation_func(*args, **kwargs)
            if not validation_result.get("valid", True):
                raise ValidationError(
                    validation_result.get("message", "Validation failed")
                )

        # Execute main function
        return execution_func(*args, **kwargs)

    except ValidationError:
        raise  # Re-raise validation errors
    except Exception as e:
        current_app.logger.error(f"Error in validate_and_execute: {str(e)}")
        raise BusinessLogicError(f"Operation failed: {str(e)}")


# Utility decorators for common error patterns
def handle_errors(error_type="generic"):
    """
    Decorator to add consistent error handling to route functions
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValidationError:
                raise
            except BusinessLogicError:
                raise
            except SecurityError:
                raise
            except Exception as e:
                if error_type == "database":
                    raise Exception(f"Database operation failed in {func.__name__}")
                elif error_type == "file":
                    raise Exception(f"File operation failed in {func.__name__}")
                else:
                    raise Exception(f"Operation failed in {func.__name__}: {str(e)}")

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator

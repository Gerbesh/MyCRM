import collections

from flask import Flask, current_app, flash, g, jsonify, redirect, request, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from flask_session import Session

# Совместимость: старые пакеты ожидают MutableMapping в collections
if not hasattr(collections, "MutableMapping"):
    from collections.abc import MutableMapping  # type: ignore

    collections.MutableMapping = MutableMapping  # type: ignore

import json
import logging
import logging.config
import os
import time
import uuid
from datetime import timedelta

from dotenv import load_dotenv

# Flask-Limiter (обязателен storage_uri в проде)
from extensions import limiter

if os.path.exists(".env.local"):
    load_dotenv(".env.local")
else:
    load_dotenv()

from config import get_config
from database import db

# CLI-регистрация
from scripts.cleanup import register_cleanup_commands

# Важно: bootstrap и прочие импорты выполняем после создания app/конфига
from security_utils import safe_log

# --- чувствительные ключи для скрытия в логах ---
SENSITIVE_KEYS = {"password", "passwd", "pwd", "token", "csrf_token", "new_password"}


def _scrub(d):
    if not isinstance(d, dict):
        return d
    redacted = {}
    for k, v in d.items():
        redacted[k] = "***" if k.lower() in SENSITIVE_KEYS else v
    return redacted


# Таймзона процесса
os.environ.setdefault("TZ", "Europe/Moscow")
try:
    import time as _t

    if hasattr(_t, "tzset"):
        _t.tzset()
except Exception:
    pass


def _should_create_all() -> bool:
    """Нужно ли выполнять db.create_all() в текущем окружении"""
    return not (
        os.getenv("FLASK_ENV") == "production" and app.config.get("FORCE_ALEMBIC_ONLY")
    )


# ------------------ Создание приложения ------------------
app = Flask(__name__)

# Конфигурация из собственного конфига (он сам читает окружение)
config_class = get_config()
app.config.from_object(config_class)
app.config.setdefault("SHOW_DETAILED_ERRORS", True)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 30

# DEV: при SKIP_DB=1 и не-production — принудительно используем локальную SQLite,
# чтобы не подключаться к внешнему SQL (мокаем БД на локалке)
if os.environ.get("FLASK_ENV", "development").lower() != "production":
    _skip = os.environ.get("SKIP_DB", "").strip().lower()
    if _skip in {"1", "true", "yes", "on", "y"}:
        instance_dir = os.path.join(os.getcwd(), "instance")
        os.makedirs(instance_dir, exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
            instance_dir, "app.db"
        )
        # Для sqlite пул коннектов не нужен
        app.config.pop("SQLALCHEMY_ENGINE_OPTIONS", None)

# База на случай отсутствия DSN (dev fallback)
if not app.config.get("SQLALCHEMY_DATABASE_URI"):
    instance_dir = os.path.join(os.getcwd(), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        instance_dir, "app.db"
    )

# Каталог загрузок
app.config.setdefault("UPLOAD_FOLDER", os.path.join(app.root_path, "static", "uploads"))

# Поздняя инициализация из config_class, если есть init_app
if hasattr(config_class, "init_app"):
    config_class.init_app(app)


# ------------------ Логирование (без рекурсии) ------------------
os.makedirs("logs", exist_ok=True)
log_level = getattr(config_class, "LOGGING_LEVEL", "INFO")

# Если Passenger уже импортировал модуль, не дублируем обработчики
# логирования.
if not getattr(app, "_logging_configured", False):
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # не гасим сторонние логгеры
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s: %(message)s "
                        "[in %(pathname)s:%(lineno)d]"
                    )
                },
                "audit_json": {"()": "logging.Formatter", "format": "%(message)s"},
            },
            "handlers": {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": "logs/app.log",
                    "maxBytes": 10 * 1024 * 1024,
                    "backupCount": 10,
                    "formatter": "default",
                    "level": log_level,
                },
                "console": {
                    "class": "logging.StreamHandler",
                    # Используем сырое stdout, чтобы избежать рекурсии.
                    "stream": "ext://sys.__stdout__",
                    "formatter": "default",
                    "level": log_level,
                },
                "audit_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": "logs/audit.log",
                    "maxBytes": 10 * 1024 * 1024,
                    "backupCount": 20,
                    "formatter": "audit_json",
                    "level": "INFO",
                },
            },
            "loggers": {
                "audit": {
                    "level": "INFO",
                    "handlers": ["audit_file"],
                    "propagate": False,
                }
            },
            "root": {"level": log_level, "handlers": ["file", "console"]},
        }
    )

    # Привязываем app.logger к root-хендлерам без лишней болтовни
    app.logger.handlers = logging.getLogger().handlers
    app.logger.setLevel(log_level)
    app.logger.propagate = False

    app._logging_configured = True  # маркер, чтобы не конфигурировать повторно

audit_logger = logging.getLogger("audit")
app.logger.info("CRM startup")

# ------------------ Расширения ------------------
db.init_app(app)
from models import User  # импорт моделей после init_app  # noqa: E402

# ===== СЕСС (Redis/SQLAlchemy/Filesystem) =====
# Если выбран Redis — настраиваем из REDIS_URL (.env), без дефолтов
if app.config.get("SESSION_TYPE") == "redis":
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        app.logger.error(
            "SESSION_TYPE=redis, но REDIS_URL не задан — переключаюсь на sqlalchemy"
        )
        app.config["SESSION_TYPE"] = "sqlalchemy"
        app.config["REDIS_AVAILABLE"] = False
    else:
        try:
            import redis

            r = redis.StrictRedis.from_url(redis_url, socket_timeout=2)
            r.ping()
            app.config["SESSION_REDIS"] = r
            app.config["REDIS_AVAILABLE"] = True
            app.logger.info(f"SESSION_REDIS OK: {redis_url}")
        except Exception as e:
            app.logger.error(
                f"SESSION_REDIS FAIL: {e} ({redis_url}) — переключаюсь на sqlalchemy"
            )
            app.config["SESSION_TYPE"] = "sqlalchemy"
            app.config["REDIS_AVAILABLE"] = False

# Если итоговый backend — SQLAlchemy, привязываем к db
if app.config.get("SESSION_TYPE") == "sqlalchemy" and not app.config.get(
    "SESSION_SQLALCHEMY"
):
    app.config["SESSION_SQLALCHEMY"] = db

# Предупреждаем, если в проде остались файловые сессии
if (
    app.config.get("ENV") == "production"
    and app.config.get("SESSION_TYPE") == "filesystem"
):
    app.logger.warning(
        'SESSION_TYPE=filesystem в продакшене может приводить к "дробным" сессиям'
    )

Session(app)

# CSRF
csrf = CSRFProtect(app)

# Адаптивные CSRF настройки на основе наличия Redis
if app.config.get("REDIS_AVAILABLE"):
    app.logger.info("Redis доступен: используем стандартные timeout для CSRF")
else:
    app.logger.info("Redis недоступен: увеличиваем timeout для CSRF до 24 часов")
    app.config["WTF_CSRF_TIME_LIMIT"] = 86400

app.logger.info(f"Окружение: {app.config.get('ENV', 'development')}")
app.logger.info(f"Debug режим: {app.debug}")
app.logger.info(f"Session type: {app.config.get('SESSION_TYPE', 'unknown')}")
app.logger.info(f"CSRF timeout: {app.config.get('WTF_CSRF_TIME_LIMIT', 3600)} сек")
app.logger.info(f"Redis доступен: {app.config.get('REDIS_AVAILABLE', False)}")

# ===== Flask-Limiter — backend ТОЛЬКО из окружения =====
storage_uri = os.environ.get("RATELIMIT_STORAGE_URL")
if app.config.get("ENV") == "production" and (
    not storage_uri or storage_uri.startswith("memory://")
):
    raise RuntimeError(
        "В продакшене требуется внешний storage для лимитера (RATELIMIT_STORAGE_URL)"
    )
if not storage_uri:
    app.logger.warning(
        (
            "RATELIMIT_STORAGE_URL не задан — лимитер будет работать в памяти "
            "(не рекомендуется в проде)."
        )
    )

# Настраиваем Limiter через конфиг приложения, чтобы избежать циклических импортов
app.config.setdefault(
    "RATELIMIT_DEFAULTS", [os.environ.get("RATE_LIMIT_DEFAULT", "100/hour")]
)
app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
app.config["RATELIMIT_STORAGE_URL"] = storage_uri or app.config.get(
    "RATELIMIT_STORAGE_URL", "memory://"
)

try:
    limiter.init_app(app)
except Exception as _limiter_err:
    app.logger.warning(
        f"Limiter init failed: {_limiter_err}. Falling back to in-memory backend."
    )
    app.config["RATELIMIT_STORAGE_URL"] = "memory://"
    limiter.init_app(app)

app.logger.info(
    f"Limiter backend: {app.config.get('RATELIMIT_STORAGE_URL') or 'in-memory'}"
)

# Логин-менеджер
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.remember_cookie_duration = timedelta(days=30)

# CLI-команды
register_cleanup_commands(app)

# ------------------ Контекст/хелперы ------------------
from utils.request_helpers import get_request_contractor  # noqa: E402
from utils.statuses import get_status_class, get_status_label  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "VERSION"), encoding="utf-8") as f:
    APP_VERSION = f.read().strip()
THEME_COLOR = "#2563eb"


def _human_size(bytes_val: int) -> str:
    try:
        units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
        size = float(bytes_val)
        idx = 0
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        # Показываем без лишних нулей
        return ("{:.0f} {}" if size.is_integer() else "{:.1f} {}").format(
            size, units[idx]
        )
    except Exception:
        return str(bytes_val)


@app.context_processor
def inject_helpers():
    from utils.statuses import RequestStatus

    demo_seed_target = int(current_app.config.get("DEMO_SEED_REQUESTS", 5000))
    demo_seed_disabled: bool | None = None
    demo_seed_current = None

    if current_user.is_authenticated and getattr(current_user, "role", None) == "admin":
        try:
            from models import Request  # локальный импорт, чтобы избежать циклов

            demo_seed_current = Request.query.count()
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(
                "Не удалось получить количество заявок для демо-генерации: %s",
                exc,
            )
            demo_seed_current = demo_seed_target
        demo_seed_disabled = int(demo_seed_current) >= demo_seed_target

    return {
        "get_request_contractor": get_request_contractor,
        "RequestStatus": RequestStatus,
        "status_label": get_status_label,
        "status_class": get_status_class,
        "status_labels": {s: get_status_label(s) for s in RequestStatus.all()},
        "status_classes": {s: get_status_class(s) for s in RequestStatus.all()},
        "APP_VERSION": APP_VERSION,
        "THEME_COLOR": THEME_COLOR,
        "demo_seed_disabled": demo_seed_disabled,
        "demo_seed_target": demo_seed_target,
        "demo_seed_current": demo_seed_current,
    }


# Healthcheck
@app.get("/healthz")
def healthz():
    return "OK", 200


# Обновление CSRF токена
@app.get("/refresh_csrf")
def refresh_csrf():
    token = generate_csrf()
    return jsonify({"csrf_token": token})


# ------------------ Логирование запросов/ответов ------------------
@app.before_request
def log_request_info():
    g.request_start = time.time()
    g.request_id = str(uuid.uuid4())
    user = current_user.username if current_user.is_authenticated else "аноним"

    params = request.values.to_dict(flat=True)
    json_body = {}
    if request.is_json:
        try:
            json_body = request.get_json(silent=True) or {}
        except Exception:
            json_body = {}

    safe_log(
        app.logger,
        logging.INFO,
        (
            f"Запрос {request.method} {request.path} от {request.remote_addr} ",
            f"пользователь={user} параметры={params}",
        ),
    )

    audit_event = {
        "type": "request",
        "ts": time.time(),
        "ts_iso": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "request_id": g.request_id,
        "user": user,
        "ip": request.remote_addr,
        "method": request.method,
        "path": request.path,
        "query": _scrub(params),
        "json": _scrub(json_body),
        "headers": {
            "User-Agent": request.headers.get("User-Agent"),
            "Referer": request.headers.get("Referer"),
        },
        "session_id": request.cookies.get(
            app.config.get("SESSION_COOKIE_NAME", "session")
        ),
    }
    audit_logger.info(json.dumps(audit_event, ensure_ascii=False))


@app.before_request
def enforce_demo_readonly():
    """Запрещает демо-пользователю изменять данные."""

    if not current_user.is_authenticated:
        return None

    if getattr(current_user, "role", "") != "demo":
        return None

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None

    allow_demo_writes = {"request_crud.create_request"}
    if request.endpoint in allow_demo_writes:
        return None

    message = "Демо-доступ только для чтения. Действие заблокировано."

    safe_log(
        app.logger,
        logging.WARNING,
        (
            "Попытка записи в демо-режиме: %s %s пользователем %s",
            request.method,
            request.path,
            current_user.username,
        ),
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        response = jsonify({"error": message, "demo_mode": True})
        response.status_code = 403
        return response

    flash(message, "warning")
    fallback = (
        url_for("main.dashboard")
        if request.endpoint != "main.dashboard"
        else url_for("main.index")
    )
    redirect_target = request.referrer or fallback
    if redirect_target == request.url:
        redirect_target = fallback
    return redirect(redirect_target)


@app.after_request
def add_cache_headers(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000"
    return response


@app.after_request
def log_response_info(response):
    duration = time.time() - g.get("request_start", time.time())
    user = current_user.username if current_user.is_authenticated else "аноним"
    safe_log(
        app.logger,
        logging.INFO,
        (
            f"Ответ {response.status_code} для {request.method} {request.path} ",
            f"пользователь={user} время={duration:.3f}с",
        ),
    )

    audit_event = {
        "type": "response",
        "ts": time.time(),
        "ts_iso": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "request_id": getattr(g, "request_id", None),
        "user": user,
        "status": response.status_code,
        "path": request.path,
        "method": request.method,
        "duration_ms": int(duration * 1000),
    }
    audit_logger.info(json.dumps(audit_event, ensure_ascii=False))
    return response


# CSRF Error Handler
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    app.logger.warning(f"CSRF Error from {request.remote_addr}: Invalid CSRF token")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return (
            jsonify(
                {
                    "error": "CSRF токен недействителен. Обновите страницу.",
                    "csrf_error": True,
                    "reload_required": True,
                }
            ),
            400,
        )
    if request.referrer and request.referrer != request.url:
        return redirect(request.referrer)
    flash("CSRF токен недействителен. Пожалуйста, обновите страницу.", "danger")
    return redirect(url_for("main.index"))


# Глобальный csrf_token темплейт-хелпер
@app.template_global()
def csrf_token():
    from flask_wtf.csrf import generate_csrf

    return generate_csrf()


# Загрузка пользователя
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        app.logger.error(f"Error loading user {user_id}: {str(e)}")
        return None


# Обработчик неавторизованных
@login_manager.unauthorized_handler
def unauthorized():
    app.logger.warning("Unauthorized access attempt")
    return redirect(url_for("auth.login"))


# ------------------ нициализация БД/директорий ------------------
with app.app_context():
    try:
        instance_path = os.path.join(os.getcwd(), "instance")
        os.makedirs(instance_path, exist_ok=True)
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

        # Управляемый bootstrap: только по флагу окружения
        if os.environ.get("MIGRATE_ON_START") == "1":
            from db_bootstrap import bootstrap_db

            bootstrap_db(app)
        elif _should_create_all():
            db.create_all()

        # ---- Инициализация учётных данных деплоя (через переменные окружения) ----
        try:
            # Если DEPLOY_KEY_HASH не задан, но указан DEPLOY_CHECK_KEY,
            # получаем хеш в памяти для эндпоинта проверки деплоя.
            if not app.config.get("DEPLOY_KEY_HASH"):
                from werkzeug.security import generate_password_hash  # lazy import

                _plain_key = os.getenv("DEPLOY_CHECK_KEY")
                if _plain_key:
                    app.config["DEPLOY_KEY_HASH"] = generate_password_hash(_plain_key)

            # Гарантируем наличие пользователя деплоя, если логин/пароль заданы
            # через окружение
            _deploy_login = os.getenv("DEPLOY_CHECK_LOGIN")
            _deploy_password = os.getenv("DEPLOY_CHECK_PASSWORD")
            if _deploy_login and _deploy_password:
                from werkzeug.security import generate_password_hash

                from models import User

                exists = User.query.filter_by(username=_deploy_login).first()
                if not exists:
                    u = User(
                        username=_deploy_login,
                        password=generate_password_hash(_deploy_password),
                    )
                    db.session.add(u)
                    db.session.commit()
        except Exception as e:
            app.logger.warning(f"Deploy bootstrap skipped: {e}")

        db.reflect()
    except Exception as e:
        app.logger.error(f"Ошибка инициализации приложения: {str(e)}")
        raise


# ------------------ Регистрация блюпринтов ------------------
blueprints = [
    ("blueprints.auth", "auth_bp", "/auth"),
    ("routes.main_routes", "main_bp", ""),
    ("routes.object_routes", "object_bp", "/objects"),
    ("routes.contractor_routes", "contractor_bp", "/contractors"),
    ("routes.user_routes", "user_bp", "/users"),
    ("routes.search_routes", "search_bp", "/search"),
    ("routes.api.v1", "api_v1_bp", "/api/v1"),
    ("routes.file_routes", "file_bp", "/files"),
    ("routes.request_crud_routes", "request_crud_bp", "/requests/crud"),
    ("routes.request_process_routes", "request_process_bp", "/requests/process"),
    ("routes.request_comment_routes", "request_comment_bp", "/requests/comment"),
    ("routes.docs_routes", "docs_bp", ""),
    ("routes.audit_routes", "audit_bp", "/api/v1"),
    ("routes.admin_routes", "admin_bp", "/"),
    ("routes.admin_logs", "admin_logs_bp", ""),
    ("blueprints.op", "op_bp", ""),
    ("routes.op_api", "op_api_bp", ""),
]

for module, bp_name, prefix in blueprints:
    try:
        mod = __import__(module, fromlist=[bp_name])
        bp = getattr(mod, bp_name)
        # deploy_check alias удалён
        app.register_blueprint(bp, url_prefix=prefix)
        safe_log(
            app.logger,
            logging.INFO,
            f"Зарегистрирован blueprint {bp_name} по префиксу {prefix or '/'}",
        )
    except Exception as e:
        safe_log(
            app.logger, logging.ERROR, f"Ошибка регистрации blueprint {bp_name}: {e}"
        )

# GraphQL функционал удалён

# Регистрация обработчиков ошибок
try:
    from error_handler import register_error_handlers

    register_error_handlers(app)
    app.logger.info("Error handlers registered successfully")
except Exception as e:
    app.logger.error(f"Error registering error handlers: {str(e)}")

# Безопасность сессий
try:
    from session_security import setup_session_security

    setup_session_security(app)
    app.logger.info("Session security configured successfully")
except Exception as e:
    app.logger.error(f"Error configuring session security: {str(e)}")

# Валидация JSON по JSON Schema (draft 2020-12)
try:
    from validation.json_schema import init_json_validation

    init_json_validation(app)
    app.logger.info("JSON Schema validation initialized")
except Exception as e:
    app.logger.error(f"Error initializing JSON Schema validation: {str(e)}")


# Глобальный перехватчик на крайний случай
@app.errorhandler(Exception)
def handle_unexpected_error(e):
    try:
        from error_handler import handle_generic_error as _handle_generic_error

        return _handle_generic_error(e)
    except Exception:
        app.logger.error("Fatal in handle_unexpected_error", exc_info=True)
        return "Internal Server Error", 500


if __name__ == "__main__":
    app.logger.info("Starting Flask development server...")
    app.run(
        host=app.config.get("APP_HOST", "127.0.0.1"),
        port=app.config.get("APP_PORT", 5000),
        debug=app.config.get("DEBUG", True),
    )

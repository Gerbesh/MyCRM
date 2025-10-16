# -*- coding: utf-8 -*-
"""Конфигурация Flask-приложения: .env, БД-пул, безопасный Redis без скрытых
дефолтов."""

from __future__ import annotations

import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import find_dotenv, load_dotenv
from flask import redirect, request

# --------------------------- Надёжная загрузка .env ---------------------------

_THIS_FILE = Path(__file__).resolve()
_DEFAULT_DOTENV_DIR = _THIS_FILE.parent
_ENV_EXPLICIT = os.environ.get("ENV_FILE")
_loaded = False

if _ENV_EXPLICIT:
    _loaded = load_dotenv(dotenv_path=_ENV_EXPLICIT)

if not _loaded:
    _loaded = load_dotenv(dotenv_path=_DEFAULT_DOTENV_DIR / ".env")

if not _loaded:
    load_dotenv(find_dotenv(usecwd=True))


# ----------------------------- Утилиты .env ----------------------------------


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


# --------------------------- Фичефлаги ---------------------------------------

# Подробные ошибки: включает вывод трейсбеков в ответах
SHOW_DETAILED_ERRORS = os.getenv("SHOW_DETAILED_ERRORS", "true").lower() == "true"
# Логирование чувствительных данных: при False токены и сессии маскируются
LOG_SENSITIVE = os.getenv("LOG_SENSITIVE", "true").lower() == "true"
# Жёсткий запрет db.create_all в проде (используется, если схемой управляют вручную)
FORCE_ALEMBIC_ONLY = os.getenv("FORCE_ALEMBIC_ONLY", "false").lower() == "true"
# Разрешить старый FTP-деплой (False → только SFTP/rsync)
ALLOW_FTP_DEPLOY = os.getenv("ALLOW_FTP_DEPLOY", "true").lower() == "true"
# Разрешить старый статический ключ для /deploy/check
ALLOW_LEGACY_DEPLOYKEY = os.getenv("ALLOW_LEGACY_DEPLOYKEY", "true").lower() == "true"
# Секрет и TTL для HMAC-подписей /deploy/check
DEPLOY_HMAC_SECRET = os.getenv("DEPLOY_HMAC_SECRET", "")
DEPLOY_HMAC_TTL = int(os.getenv("DEPLOY_HMAC_TTL", "300"))
ALLOW_SYSTEMCTL_RESTART = _bool(env("ALLOW_SYSTEMCTL_RESTART"), False)
SYSTEMD_SERVICE_NAME = env("SYSTEMD_SERVICE_NAME", "")
APP_RESTART_COMMAND = env("APP_RESTART_COMMAND", "")
DEPLOY_RESTART_COMMAND = env("DEPLOY_RESTART_COMMAND", "")


# ------------------------------ Redis helper ---------------------------------


def _connect_redis(
    app, url: str, session_dir: str | None = None, raise_on_fail: bool = False
) -> bool:
    """Подключиться к Redis по URL (если он задан). наче вернёт False."""
    if not url:
        # URL не задан → не трогаем Redis вообще
        app.config["REDIS_AVAILABLE"] = False
        return False
    try:
        import redis  # локальный импорт, чтобы не тащить зависимость заранее

        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        app.config["SESSION_TYPE"] = env("SESSION_TYPE", "redis")
        app.config["SESSION_REDIS"] = client
        app.config["REDIS_AVAILABLE"] = True
        app.logger.info(f"Redis connected: {url}")
        return True
    except Exception as e:  # noqa: BLE001
        app.logger.warning(f"Redis unavailable: {e} ({url})")
        app.config["REDIS_AVAILABLE"] = False
        # Фолбэк на SQLAlchemy сессии (или указанный SESSION_TYPE)
        app.config["SESSION_TYPE"] = env("SESSION_TYPE", "sqlalchemy")
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)
        if raise_on_fail:
            raise
        return False


# ------------------------------ Базовая конфигурация --------------------------


class Config:
    """Общая конфигурация для всех окружений."""

    # Секрет
    _default_secret_key = secrets.token_hex(32)
    SECRET_KEY = env("SECRET_KEY", _default_secret_key)

    # Фичефлаги (могут переопределяться через переменные окружения)
    SHOW_DETAILED_ERRORS = SHOW_DETAILED_ERRORS
    LOG_SENSITIVE = LOG_SENSITIVE
    FORCE_ALEMBIC_ONLY = FORCE_ALEMBIC_ONLY
    ALLOW_FTP_DEPLOY = ALLOW_FTP_DEPLOY
    ALLOW_LEGACY_DEPLOYKEY = ALLOW_LEGACY_DEPLOYKEY
    DEPLOY_HMAC_SECRET = DEPLOY_HMAC_SECRET
    DEPLOY_HMAC_TTL = DEPLOY_HMAC_TTL
    ALLOW_SYSTEMCTL_RESTART = ALLOW_SYSTEMCTL_RESTART
    SYSTEMD_SERVICE_NAME = SYSTEMD_SERVICE_NAME
    APP_RESTART_COMMAND = APP_RESTART_COMMAND
    DEPLOY_RESTART_COMMAND = DEPLOY_RESTART_COMMAND

    # Flask / SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = _bool(env("SQLALCHEMY_ECHO"), False)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    PROPAGATE_EXCEPTIONS = True

    # Пул БД (включим ниже, когда будет собран URI и это не sqlite)
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}

    # Сессии (базовые)
    SESSION_TYPE = env(
        "SESSION_TYPE", "filesystem"
    )  # 'redis' / 'filesystem' / 'sqlalchemy'
    SESSION_COOKIE_NAME = env("SESSION_COOKIE_NAME", "session")
    SESSION_COOKIE_HTTPONLY = _bool(env("SESSION_COOKIE_HTTPONLY"), True)
    SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_USE_SIGNER = _bool(env("SESSION_USE_SIGNER"), True)
    SESSION_COOKIE_SECURE = _bool(
        env("SESSION_COOKIE_SECURE"), False
    )  # станет True при https
    SESSION_COOKIE_MAX_AGE = timedelta(days=1)
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)

    # Логи
    LOGGING_LEVEL = env("LOG_LEVEL", "INFO")

    # Сетевые
    APP_HOST = env("APP_HOST", "127.0.0.1")
    APP_PORT = int(env("APP_PORT", 5000))

    # CSRF
    WTF_CSRF_ENABLED = _bool(env("WTF_CSRF_ENABLED"), True)
    WTF_CSRF_FIELD_NAME = "csrf_token"
    WTF_CSRF_TIME_LIMIT = int(env("CSRF_TIMEOUT", "86400"))
    WTF_CSRF_SSL_STRICT = True  # в проде True, в деве перепишем

    # Клиентские события
    AUDIT_EVENT_TOKEN = env("AUDIT_EVENT_TOKEN")

    # Безопасность/HTTPS
    SECURITY_HEADERS = False
    FORCE_HTTPS = False
    PREFERRED_URL_SCHEME = env("PREFERRED_URL_SCHEME", "http")

    # HSTS
    HSTS_ENABLED = _bool(env("HSTS_ENABLED"), False)
    HSTS_MAX_AGE = int(env("HSTS_MAX_AGE", "31536000"))
    HSTS_INCLUDE_SUBDOMAINS = _bool(env("HSTS_INCLUDE_SUBDOMAINS"), False)
    HSTS_PRELOAD = _bool(env("HSTS_PRELOAD"), False)

    # reCAPTCHA v3
    RECAPTCHA_SITE_KEY = env("RECAPTCHA_SITE_KEY")
    RECAPTCHA_SECRET_KEY = env("RECAPTCHA_SECRET_KEY")
    RECAPTCHA_MIN_SCORE = float(env("RECAPTCHA_MIN_SCORE", "0.5"))

    # Deploy hash check
    DEPLOY_KEY_HASH = env("DEPLOY_KEY_HASH")
    DEPLOY_ROOT = env("DEPLOY_ROOT")

    # Flask-Limiter
    RATELIMIT_STORAGE_URL = env("RATELIMIT_STORAGE_URL")  # брать ТОЛЬКО из .env
    RATELIMIT_HEADERS_ENABLED = _bool(env("RATELIMIT_HEADERS_ENABLED"), True)
    RATE_LIMIT_DEFAULT = env("RATE_LIMIT_DEFAULT", "100/hour")
    LOGIN_RATE_LIMIT = env("LOGIN_RATE_LIMIT", "10/minute")

    # Прочее
    MIGRATE_ON_START = env("MIGRATE_ON_START", "0")

    # --------------------------- БД URI сборка -------------------------------

    @staticmethod
    def _build_database_uri(default_sqlite: bool = False) -> str | None:
        """Сборка SQLALCHEMY_DATABASE_URI из .env."""
        db_type = env("DB_TYPE")
        if not db_type:
            if default_sqlite:
                base = env(
                    "SQLITE_DIR", str((_THIS_FILE.parent / "instance").resolve())
                )
                path = Path(base) / "app.db"
                path.parent.mkdir(parents=True, exist_ok=True)
                return f"sqlite:///{path}"
            return None

        t = db_type.lower().strip()

        if t == "mysql":
            user = quote_plus(env("DB_USER", ""))
            password = quote_plus(env("DB_PASSWORD", ""))
            host = env("DB_HOST", "")
            port = env("DB_PORT", "3306")
            name = env("DB_NAME", "")
            if not all([user, password, host, name]):
                raise RuntimeError(
                    (
                        "Не заданы параметры подключения к MySQL "
                        "(DB_USER/DB_PASSWORD/DB_HOST/DB_NAME)"
                    )
                )
            return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"

        if t in ("postgres", "postgresql"):
            user = quote_plus(env("DB_USER", ""))
            password = quote_plus(env("DB_PASSWORD", ""))
            host = env("DB_HOST", "")
            port = env("DB_PORT", "5432")
            name = env("DB_NAME", "")
            if not all([user, password, host, name]):
                raise RuntimeError(
                    (
                        "Не заданы параметры подключения к Postgres "
                        "(DB_USER/DB_PASSWORD/DB_HOST/DB_NAME)"
                    )
                )
            return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

        if t == "sqlite":
            name = env("DB_NAME")
            if not name:
                base = env(
                    "SQLITE_DIR", str((_THIS_FILE.parent / "instance").resolve())
                )
                name = str(Path(base) / "app.db")
            Path(name).parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{name}"

        raise RuntimeError(f"Неизвестный тип БД: {db_type}")

    # ---------------------------- нициализация app ---------------------------

    @staticmethod
    def init_app(app) -> None:
        level = getattr(
            logging, str(app.config.get("LOGGING_LEVEL", "INFO")).upper(), logging.INFO
        )
        logging.getLogger().setLevel(level)

        # HTTPS → включаем secure-cookie
        scheme = app.config.get("PREFERRED_URL_SCHEME", "http")
        if scheme == "https":
            app.config["SESSION_COOKIE_SECURE"] = True
        else:
            app.config.setdefault("SESSION_COOKIE_SECURE", False)


# --------------------------- Развёртывания окружений -------------------------


class DevelopmentConfig(Config):
    DEBUG = True
    LOGGING_LEVEL = env("LOG_LEVEL", "DEBUG")
    WTF_CSRF_SSL_STRICT = False  # разрешаем HTTP в деве
    SESSION_TYPE = env("SESSION_TYPE", "filesystem")
    SESSION_FILE_DIR = str((_THIS_FILE.parent / "flask_session").resolve())
    SESSION_PERMANENT = False

    @staticmethod
    def init_app(app) -> None:
        Config.init_app(app)
        # В деве — Redis по желанию: если явно указан REDIS_URL или задан лимитер
        need_redis = (env("SESSION_TYPE") == "redis") or bool(
            env("RATELIMIT_STORAGE_URL")
        )
        if need_redis:
            _connect_redis(
                app, env("REDIS_URL"), session_dir=app.config.get("SESSION_FILE_DIR")
            )


class ProductionConfig(Config):
    DEBUG = False
    LOGGING_LEVEL = env("LOG_LEVEL", "INFO")
    SESSION_TYPE = env("SESSION_TYPE", "redis")

    # Строже куки и CSRF
    WTF_CSRF_SSL_STRICT = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    SESSION_COOKIE_MAX_AGE = timedelta(hours=8)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Безопасность
    SECURITY_HEADERS = True
    FORCE_HTTPS = True
    PREFERRED_URL_SCHEME = "https"

    HSTS_ENABLED = True
    HSTS_MAX_AGE = int(env("HSTS_MAX_AGE", "31536000"))
    HSTS_INCLUDE_SUBDOMAINS = _bool(env("HSTS_INCLUDE_SUBDOMAINS"), True)
    HSTS_PRELOAD = _bool(env("HSTS_PRELOAD"), True)

    @staticmethod
    def init_app(app) -> None:
        Config.init_app(app)

        # SECRET_KEY должен быть задан в проде
        if app.config.get(
            "SECRET_KEY"
        ) == Config._default_secret_key and not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production")

        # --- Redis ---
        # Никаких дефолтов. Берём только из .env (REDIS_URL).
        # Подключаем, если:
        #   • SESSION_TYPE=redis, Л
        #   • задан RATELIMIT_STORAGE_URL (лимитер на Redis)
        need_redis = (env("SESSION_TYPE", "redis") == "redis") or bool(
            env("RATELIMIT_STORAGE_URL")
        )
        if need_redis:
            _connect_redis(
                app,
                env("REDIS_URL"),
                session_dir=str((_THIS_FILE.parent / "flask_session").resolve()),
            )
        else:
            app.config["REDIS_AVAILABLE"] = False
            app.logger.info("Redis not required at startup")

        # Если Redis недоступен — откатываемся на SQLAlchemy
        if not app.config.get("REDIS_AVAILABLE"):
            app.config["SESSION_TYPE"] = env("SESSION_TYPE", "sqlalchemy")
            if app.config["SESSION_TYPE"] == "filesystem":
                app.logger.warning(
                    (
                        "SESSION_TYPE=filesystem в продакшене может привести к потере "
                        "сессий"
                    )
                )

        # Включаем HTTPS-редирект и заголовки безопасности
        https_redirect_middleware(app)
        setup_security_headers(app)
        app.logger.info("HTTPS redirect and security headers enabled (production)")


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    LOGGING_LEVEL = env("LOG_LEVEL", "DEBUG")
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = str((_THIS_FILE.parent / "test_sessions").resolve())

    @staticmethod
    def init_app(app) -> None:
        Config.init_app(app)
        # Тесты могут захотеть Redis — только если явно указан URL
        if env("REDIS_URL"):
            _connect_redis(
                app, env("REDIS_URL"), session_dir=app.config.get("SESSION_FILE_DIR")
            )


# --------------------------- Выбор конфигурации -------------------------------

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """Вернуть КЛАСС конфигурации по FLASK_ENV и собрать БД/пул."""
    env_name = os.environ.get("FLASK_ENV", "development").lower()
    cfg_class = config.get(env_name, DevelopmentConfig)

    # Сборка URI БД
    if cfg_class is not TestingConfig:
        uri = Config._build_database_uri(default_sqlite=(env_name != "production"))
        if env_name == "production" and not uri:
            raise RuntimeError("Не заданы параметры подключения к БД")
        if uri:
            cfg_class.SQLALCHEMY_DATABASE_URI = uri
            # Пул только для не-sqlite
            if not uri.startswith("sqlite"):
                cfg_class.SQLALCHEMY_ENGINE_OPTIONS = {
                    "pool_size": int(env("DB_POOL_SIZE", "5")),
                    "max_overflow": int(env("DB_MAX_OVERFLOW", "10")),
                    "pool_recycle": int(env("DB_POOL_RECYCLE", "280")),
                }

    return cfg_class


# ------------------------- Middleware / Security headers ---------------------


def https_redirect_middleware(app):
    """Принудительный редирект HTTP → HTTPS в production."""

    @app.before_request
    def _before_request():
        if not app.config.get("FORCE_HTTPS", False):
            return None
        if request.is_secure or app.debug or app.testing:
            return None
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)


def setup_security_headers(app):
    """Установка security headers (production)."""
    if not app.config.get("SECURITY_HEADERS", False):
        return

    @app.after_request
    def _after_request(response):
        # HSTS
        if app.config.get("HSTS_ENABLED", False):
            hsts_max_age = app.config.get("HSTS_MAX_AGE", 31536000)
            hsts_include_subdomains = app.config.get("HSTS_INCLUDE_SUBDOMAINS", False)
            hsts_preload = app.config.get("HSTS_PRELOAD", False)
            hsts_value = f"max-age={hsts_max_age}"
            if hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Базовые заголовки
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP — строгий набор для reCAPTCHA, ReDoc и CDN (GSAP, particles.js и т.п.)
        if app.config.get("FORCE_HTTPS", False):
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
                "https://cdnjs.cloudflare.com https://www.google.com "
                "https://www.gstatic.com; "
                "style-src  'self' 'unsafe-inline' https://cdn.jsdelivr.net "
                "https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
                "font-src   'self' data: https://fonts.gstatic.com "
                "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "img-src    'self' data: https://cdn.redoc.ly; "
                "connect-src 'self' https:; "
                "worker-src 'self' blob:; "
                "frame-src  https://www.google.com https://www.gstatic.com; "
                "frame-ancestors 'none'; "
                "form-action 'self'; "
                "base-uri 'self'; "
                "upgrade-insecure-requests;"
            )
            response.headers["Content-Security-Policy"] = csp
        return response

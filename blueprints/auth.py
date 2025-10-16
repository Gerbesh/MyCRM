"""
Blueprint для аутентификации пользователей
"""

import logging
import secrets
import time
from urllib.parse import (
    urlparse as url_parse,
)

# Замена устаревшему werkzeug.urls.url_parse
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter.util import get_remote_address
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import limiter
from models import User, db
from security_utils import safe_log, validate_user_input, verify_recaptcha_v3
from session_security import SessionSecurity, init_session_on_login

auth_bp = Blueprint("auth", __name__)

failed_login_attempts = {}
CAPTCHA_THRESHOLD = 3
ATTEMPT_WINDOW = 900  # 15 минут


def login_limit_key():
    """Ключ ограничения: имя пользователя или IP."""
    return request.form.get("username") or get_remote_address()


# Разрешаем превышение глобального лимита на /auth/login, если reCAPTCHA v3 пройдена
@limiter.request_filter
def _recaptcha_bypass_rate_limit():
    try:
        if request.endpoint == "auth.login" and request.method == "POST":
            token = request.form.get("g-recaptcha-response")
            if token:
                ok, _ = verify_recaptcha_v3(
                    token, action="login", remote_ip=get_remote_address()
                )
                return bool(ok)
        return False
    except Exception:
        return False


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", key_func=login_limit_key)
def login():
    try:
        if current_user.is_authenticated:
            safe_log(
                logging.getLogger(__name__),
                logging.DEBUG,
                (
                    f"User {current_user.username} already authenticated, "
                    "redirecting to dashboard"
                ),
            )
            return redirect(url_for("main.dashboard"))

        identifier = login_limit_key()
        now = time.time()
        record = failed_login_attempts.get(identifier)
        if record and now - record["time"] > ATTEMPT_WINDOW:
            failed_login_attempts.pop(identifier, None)
            record = None
        show_captcha = bool(record and record["count"] >= CAPTCHA_THRESHOLD)

        if request.method == "POST":
            # Валидация входных данных
            field_rules = {
                "username": {
                    "required": True,
                    "max_length": 50,
                    "pattern": r"^[a-zA-Z0-9_.-]+$",
                },
                "password": {"required": True, "max_length": 255},
            }

            form_data = {
                "username": request.form.get("username", ""),
                "password": request.form.get("password", ""),
            }

            cleaned_data, valid, errors = validate_user_input(form_data, field_rules)

            if not valid:
                for error in errors:
                    flash(error, "danger")
                safe_log(
                    logging.getLogger(__name__),
                    logging.WARNING,
                    f"Login validation failed: {errors}",
                )
                return render_template("login.html", show_captcha=show_captcha)

            username = cleaned_data["username"]
            password = cleaned_data["password"]
            safe_log(
                logging.getLogger(__name__),
                logging.DEBUG,
                f"Login attempt: username={username}",
            )

            # Если требуется капча — проверяем reCAPTCHA v3
            if show_captcha:
                token = request.form.get("g-recaptcha-response")
                ok, reason = verify_recaptcha_v3(
                    token, action="login", remote_ip=get_remote_address()
                )
                if not ok:
                    flash("Подтвердите, что вы не робот", "warning")
                    safe_log(
                        logging.getLogger(__name__),
                        logging.WARNING,
                        f"reCAPTCHA failed: {reason}",
                    )
                    return render_template(
                        "login.html",
                        show_captcha=True,
                        recaptcha_site_key=current_app.config.get("RECAPTCHA_SITE_KEY"),
                    )

            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password, password):
                flash("Неверное имя пользователя или пароль", "danger")
                safe_log(
                    logging.getLogger(__name__),
                    logging.WARNING,
                    f"Login failed for user {username}",
                )
                count = (record["count"] if record else 0) + 1
                failed_login_attempts[identifier] = {"count": count, "time": now}
                if count >= CAPTCHA_THRESHOLD:
                    flash("Подтвердите, что вы не робот", "warning")
                    return render_template(
                        "login.html",
                        show_captcha=True,
                        recaptcha_site_key=current_app.config.get("RECAPTCHA_SITE_KEY"),
                    )
                return render_template(
                    "login.html",
                    recaptcha_site_key=current_app.config.get("RECAPTCHA_SITE_KEY"),
                )

            failed_login_attempts.pop(identifier, None)
            login_user(user, remember=True)

            # При обычной авторизации очищаем флаг демо-режима
            session.pop("demo_mode", None)

            # Инициализируем безопасную сессию
            init_session_on_login()

            session_id = session.get("session_id")
            safe_log(
                logging.getLogger(__name__),
                logging.INFO,
                f"User {username} logged in successfully, session {session_id} issued",
            )

            # Переадресация на запрошенную страницу, если она внутри нашего сайта
            next_page = request.args.get("next")
            if next_page and url_parse(next_page).netloc == "":
                return redirect(next_page)
            return redirect(url_for("main.dashboard"))
        else:
            safe_log(logging.getLogger(__name__), logging.DEBUG, "Rendering login page")
            return render_template(
                "login.html",
                show_captcha=show_captcha,
                recaptcha_site_key=current_app.config.get("RECAPTCHA_SITE_KEY"),
            )

    except Exception as e:
        safe_log(
            logging.getLogger(__name__),
            logging.ERROR,
            f"Error in login route: {str(e)}",
        )
        flash("Произошла ошибка при входе", "danger")
        return (
            render_template(
                "login.html",
                recaptcha_site_key=current_app.config.get("RECAPTCHA_SITE_KEY"),
            ),
            500,
        )


def _ensure_demo_user() -> User:
    """Возвращает существующего или создаёт демо-пользователя."""

    demo_username = current_app.config.get("DEMO_LOGIN_USERNAME", "demo")
    demo_user = User.query.filter_by(username=demo_username).first()
    if demo_user is None:
        demo_user = User(
            username=demo_username,
            password=generate_password_hash(secrets.token_urlsafe(32)),
            role="demo",
        )
        db.session.add(demo_user)
        db.session.commit()
        safe_log(
            logging.getLogger(__name__),
            logging.INFO,
            f"Создан новый демо-пользователь {demo_username}",
        )
    elif demo_user.role != "demo":
        previous_role = demo_user.role
        demo_user.role = "demo"
        db.session.commit()
        safe_log(
            logging.getLogger(__name__),
            logging.WARNING,
            (
                f"Пользователь {demo_username} имел роль {previous_role}, "
                "переключено на demo для ограниченного доступа"
            ),
        )
    return demo_user


@auth_bp.route("/demo-login", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def demo_login():
    """Авторизация в режиме демо-пользователя."""

    try:
        if current_user.is_authenticated:
            flash("Вы уже вошли в систему", "info")
            return redirect(url_for("main.dashboard"))

        demo_user = _ensure_demo_user()
        login_user(demo_user, remember=False)
        session["demo_mode"] = True

        init_session_on_login()

        session_id = session.get("session_id")
        safe_log(
            logging.getLogger(__name__),
            logging.INFO,
            (
                "Активирован демо-режим: пользователь %s, сессия %s",
                demo_user.username,
                session_id,
            ),
        )

        flash("Демо-режим: доступен только просмотр данных", "warning")
        return redirect(url_for("main.dashboard"))
    except Exception as exc:  # noqa: BLE001
        safe_log(
            logging.getLogger(__name__),
            logging.ERROR,
            f"Ошибка демо-авторизации: {exc}",
        )
        flash("Не удалось выполнить демо-вход", "danger")
        return redirect(url_for("auth.login")), 500


@auth_bp.route("/logout")
@login_required
def logout():
    try:
        username = current_user.username

        session_id = session.get("session_id", "unknown")
        SessionSecurity.invalidate_session()

        logout_user()
        safe_log(
            logging.getLogger(__name__),
            logging.INFO,
            f"User {username} logged out, session {session_id} expired",
        )
        return redirect(url_for("main.index"))
    except Exception as e:
        safe_log(
            logging.getLogger(__name__),
            logging.ERROR,
            f"Error in logout route: {str(e)}",
        )
        return "Произошла ошибка", 500

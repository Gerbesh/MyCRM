"""
Session security enhancements for CRM application
Provides IP validation, session hijacking protection, and secure session management
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import abort, current_app, request, session
from flask_login import current_user, logout_user

from security_utils import safe_log


class SessionSecurity:
    """Session security management class"""

    @staticmethod
    def get_client_fingerprint():
        """Generate a client fingerprint based on User-Agent and Accept headers"""
        user_agent = request.headers.get("User-Agent", "")
        accept = request.headers.get("Accept", "")
        accept_language = request.headers.get("Accept-Language", "")

        # Create fingerprint from stable headers
        fingerprint_data = f"{user_agent}:{accept}:{accept_language}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    @staticmethod
    def get_client_ip():
        """Get real client IP, handling proxies"""
        # Check for forwarded IPs
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.remote_addr

    @staticmethod
    def is_ip_subnet_match(ip1, ip2, subnet_mask=24):
        """Check if two IPs are in the same subnet (for IP validation)"""
        try:
            import ipaddress

            network1 = ipaddress.ip_network(f"{ip1}/{subnet_mask}", strict=False)
            network2 = ipaddress.ip_network(f"{ip2}/{subnet_mask}", strict=False)
            return network1 == network2
        except Exception:
            # Fallback to exact match if ipaddress module issues
            return ip1 == ip2

    @staticmethod
    def init_secure_session():
        """Initialize session with security parameters"""
        if "session_id" not in session:
            session["session_id"] = secrets.token_hex(16)

        session["created_at"] = datetime.utcnow().isoformat()
        session["last_activity"] = datetime.utcnow().isoformat()
        session["client_ip"] = SessionSecurity.get_client_ip()
        session["client_fingerprint"] = SessionSecurity.get_client_fingerprint()
        session["security_version"] = 1  # For future security upgrades

        safe_log(
            current_app.logger,
            logging.DEBUG,
            f"Secure session initialized: {session['session_id']}",
        )

    @staticmethod
    def validate_session():
        """Validate session security parameters"""
        # Если session_id отсутствует, значит сессия ещё не была инициализирована
        # Это нормально для новых логинов
        if not session.get("session_id"):
            current_app.logger.debug(
                "Session missing session_id - will be initialized on login"
            )
            return True  # Разрешаем доступ, сессия будет инициализирована при логине

        # Мягкая проверка IP: допускаем дрейф в пределах /20 и лишь логируем расхождение
        stored_ip = session.get("client_ip")
        current_ip = SessionSecurity.get_client_ip()

        if stored_ip and current_ip:
            if not SessionSecurity.is_ip_subnet_match(
                stored_ip, current_ip, subnet_mask=20
            ):
                current_app.logger.warning(
                    (
                        f"IP mismatch (soft): stored={stored_ip}, "
                        f"current={current_ip} -> updating"
                    )
                )
                # Обновляем след IP вместо немедленного обрыва
                session["client_ip"] = current_ip

        # Check client fingerprint (менее строгая проверка)
        stored_fingerprint = session.get("client_fingerprint")
        current_fingerprint = SessionSecurity.get_client_fingerprint()

        if stored_fingerprint and current_fingerprint:
            if stored_fingerprint != current_fingerprint:
                current_app.logger.warning(
                    "Client fingerprint mismatch - updating fingerprint"
                )
                # Обновляем fingerprint вместо блокировки сессии
                session["client_fingerprint"] = current_fingerprint
                # return False  # Закомментировано - не блокируем сессию

        # Check session age
        created_at_str = session.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                max_age = timedelta(days=7)  # Maximum session lifetime

                if datetime.utcnow() - created_at > max_age:
                    safe_log(
                        current_app.logger,
                        logging.WARNING,
                        "Session expired due to age",
                    )
                    return False
            except Exception:
                current_app.logger.warning("Invalid session creation timestamp")
                return False

        # Check inactivity timeout
        last_activity_str = session.get("last_activity")
        if last_activity_str:
            try:
                last_activity = datetime.fromisoformat(last_activity_str)
                timeout = timedelta(hours=24)  # 24 hour inactivity timeout

                if datetime.utcnow() - last_activity > timeout:
                    safe_log(
                        current_app.logger,
                        logging.WARNING,
                        "Session expired due to inactivity",
                    )
                    return False
            except Exception:
                current_app.logger.warning("Invalid session activity timestamp")
                return False

        return True

    @staticmethod
    def update_session_activity():
        """Update session last activity timestamp"""
        session["last_activity"] = datetime.utcnow().isoformat()

    @staticmethod
    def invalidate_session():
        """Securely invalidate current session"""
        session_id = session.get("session_id", "unknown")
        safe_log(
            current_app.logger, logging.INFO, f"Invalidating session: {session_id}"
        )

        # Clear all session data
        session.clear()

        # Force logout if user is logged in
        if current_user.is_authenticated:
            logout_user()

    @staticmethod
    def regenerate_session_id():
        """Regenerate session ID for security"""
        old_session_id = session.get("session_id", "none")
        new_session_id = secrets.token_hex(16)

        session["session_id"] = new_session_id
        session["last_regeneration"] = datetime.utcnow().isoformat()

        safe_log(
            current_app.logger,
            logging.INFO,
            f"Session ID regenerated: {old_session_id} -> {new_session_id}",
        )

    @staticmethod
    def check_concurrent_sessions(user_id):
        """Check for suspicious concurrent session activity"""
        # This would require a session store to track active sessions
        # For now, we'll implement basic checking in the session itself

        if "login_count" not in session:
            session["login_count"] = 1
        else:
            session["login_count"] += 1

            # If too many logins in short time, flag as suspicious
            if session["login_count"] > 5:
                safe_log(
                    current_app.logger,
                    logging.WARNING,
                    f"Suspicious login activity for user {user_id}",
                )
                return False

        return True


def require_secure_session(f):
    """Decorator to enforce secure session validation"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validate session security
        if not SessionSecurity.validate_session():
            safe_log(
                current_app.logger,
                logging.WARNING,
                f"Session validation failed for {request.endpoint}",
            )
            SessionSecurity.invalidate_session()
            abort(401)  # Unauthorized

        # Update activity timestamp
        SessionSecurity.update_session_activity()

        return f(*args, **kwargs)

    return decorated_function


def init_session_on_login():
    """Initialize secure session parameters on login"""
    SessionSecurity.init_secure_session()
    SessionSecurity.regenerate_session_id()


def validate_session_on_request():
    """Проверка сессии только для чувствительных запросов"""
    # Не трогаем статику и публичные страницы
    if (
        request.endpoint
        and (
            request.endpoint.startswith("static")
            or request.endpoint == "auth.login"
            or request.endpoint == "main.index"
        )
    ) or request.path == "/favicon.ico":
        return

    # Пользователь не залогинен — ничего не делаем
    if not current_user.is_authenticated:
        return

    # Маркируем критичные и фоновые эндпоинты
    SENSITIVE_ENDPOINTS = {
        "main.change_password",
        "auth.reauth",
        "finance.process",
        "admin.mutate",
    }
    BACKGROUND_ENDPOINTS = {
        "admin.logs_data",
        "widgets.update",
    }

    # Фоновые запросы и безопасные GET пропускаем без строгой проверки
    if request.endpoint in BACKGROUND_ENDPOINTS or request.method == "GET":
        return

    # Если запрос не относится к критичным — тоже пропускаем
    if request.endpoint not in SENSITIVE_ENDPOINTS:
        return

    # Для чувствительных действий требуем валидную сессию
    if not SessionSecurity.validate_session():
        current_app.logger.warning("Session validation failed on sensitive endpoint")
        SessionSecurity.invalidate_session()
        return abort(401)

    SessionSecurity.update_session_activity()


def setup_session_security(app):
    """Setup session security for the application"""

    # Configure secure session settings
    app.config.setdefault("SESSION_COOKIE_SECURE", not app.debug)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(days=1))

    # Register session validation for each request
    @app.before_request
    def validate_session():
        validate_session_on_request()

    # Session cleanup on logout
    @app.teardown_request
    def cleanup_session(exception):
        if exception:
            current_app.logger.error(f"Request ended with exception: {str(exception)}")

    app.logger.info("Session security configured")


class SessionStore:
    """Simple session store for tracking active sessions"""

    def __init__(self):
        self.sessions = {}  # In production, use Redis or database

    def store_session(self, session_id, user_id, ip_address, user_agent):
        """Store session information"""
        self.sessions[session_id] = {
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }

    def update_activity(self, session_id):
        """Update session last activity"""
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = datetime.utcnow()

    def remove_session(self, session_id):
        """Remove session from store"""
        self.sessions.pop(session_id, None)

    def get_user_sessions(self, user_id):
        """Get all active sessions for a user"""
        return [
            {"session_id": sid, **data}
            for sid, data in self.sessions.items()
            if data["user_id"] == user_id
        ]

    def cleanup_expired_sessions(self, max_age_hours=24):
        """Remove expired sessions"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        expired_sessions = [
            sid for sid, data in self.sessions.items() if data["last_activity"] < cutoff
        ]

        for sid in expired_sessions:
            self.remove_session(sid)

        return len(expired_sessions)


# Global session store instance
session_store = SessionStore()

"""
Модуль безопасности для валидации файлов и входных данных
"""

import hashlib
import json
import logging
import os
import re
import urllib.parse
import urllib.request

from flask import current_app
from werkzeug.utils import secure_filename

import config

# Константы проекта
from utils.constants import MAX_FILE_SIZE

# Попытка импортировать python-magic; в окружениях без libmagic пропускаем
try:
    import magic  # type: ignore
except Exception:  # noqa: BLE001
    magic = None

# Разрешенные типы файлов и их MIME-типы
ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "webp",  # зображения
    "pdf",  # Документы
    "txt",
    "doc",
    "docx",
    "xls",
    "xlsx",  # Офисные документы
}

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Опасные расширения файлов
DANGEROUS_EXTENSIONS = {
    "exe",
    "scr",
    "bat",
    "cmd",
    "com",
    "pif",
    "scf",
    "vbs",
    "js",
    "jar",
    "app",
    "deb",
    "pkg",
    "rpm",
    "dmg",
    "iso",
    "bin",
    "run",
    "msi",
    "php",
    "asp",
    "aspx",
    "jsp",
    "py",
    "pl",
    "sh",
    "bash",
    "ps1",
}

# Паттерн для маскировки чувствительных параметров в логах
SENSITIVE_RE = re.compile(
    r"(session(_?id)?|token|authorization)=([^&\s]+)", re.IGNORECASE
)


def validate_file_size(file):
    """
    Проверяет размер файла

    Args:
        file: FileStorage объект

    Returns:
        tuple: (bool, str) - (валидность, сообщение об ошибке)
    """
    if not file:
        return False, "Файл не предоставлен"

    # Получаем размер файла
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Возвращаем указатель в начало

    if size > MAX_FILE_SIZE:
        size_mb = size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return (
            False,
            f"Размер файла ({size_mb:.1f}MB) превышает максимальный ({max_mb}MB)",
        )

    if size == 0:
        return False, "Файл пустой"

    return True, ""


def validate_file_extension(filename):
    """
    Проверяет расширение файла

    Args:
        filename: str - имя файла

    Returns:
        tuple: (bool, str) - (валидность, сообщение об ошибке)
    """
    if not filename:
        return False, "мя файла не указано"

    # Получаем расширение
    ext = os.path.splitext(filename)[1].lower().lstrip(".")

    # Проверяем на опасные расширения
    if ext in DANGEROUS_EXTENSIONS:
        return False, f"Опасное расширение файла: .{ext}"

    # Проверяем на разрешенные расширения
    if ext not in ALLOWED_EXTENSIONS:
        return (
            False,
            (
                f"Неразрешенное расширение файла: .{ext}. Разрешены: "
                f"{', '.join(ALLOWED_EXTENSIONS)}"
            ),
        )

    return True, ""


def validate_mime_type(file):
    """
    Проверяет MIME-тип файла через python-magic

    Args:
        file: FileStorage объект

    Returns:
        tuple: (bool, str) - (валидность, сообщение об ошибке)
    """
    if magic is None:
        return True, ""  # Библиотека magic недоступна, пропускаем проверку

    try:
        file.seek(0)
        file_data = file.read(1024)  # Читаем первые 1KB
        file.seek(0)

        try:
            mime_type = magic.from_buffer(file_data, mime=True)
        except Exception:  # noqa: BLE001
            return True, ""

        if mime_type not in ALLOWED_MIME_TYPES:
            return False, f"Неразрешенный MIME-тип: {mime_type}"
        return True, ""
    except Exception as e:  # noqa: BLE001
        current_app.logger.error(f"Ошибка проверки MIME-типа: {str(e)}")
        return False, "Ошибка проверки типа файла"


def validate_filename(filename):
    """
    Проверяет имя файла на безопасность

    Args:
        filename: str - имя файла

    Returns:
        tuple: (bool, str) - (валидность, сообщение об ошибке)
    """
    if not filename:
        return False, "мя файла не указано"

    # Проверяем длину
    if len(filename) > 255:
        return False, "мя файла слишком длинное (максимум 255 символов)"

    # Проверяем на опасные символы
    dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\x00"]
    for char in dangerous_chars:
        if char in filename:
            return False, f"Недопустимый символ в имени файла: {char}"

    # Проверяем на относительные пути
    if ".." in filename or filename.startswith("/") or "\\" in filename:
        return False, "Недопустимые символы пути в имени файла"

    return True, ""


def safe_filename_with_validation(filename):
    """
    Создает безопасное имя файла с проверками

    Args:
        filename: str - исходное имя файла

    Returns:
        tuple: (str, bool, str) - (безопасное имя, валидность, ошибка)
    """
    # Сначала проверяем исходное имя
    valid, error = validate_filename(filename)
    if not valid:
        return None, False, error

    # Создаем безопасное имя
    safe_name = secure_filename(filename)
    if not safe_name:
        return None, False, "Не удалось создать безопасное имя файла"

    return safe_name, True, ""


def validate_file_complete(file):
    """
    Полная валидация файла

    Args:
        file: FileStorage объект

    Returns:
        tuple: (bool, str) - (валидность, сообщение об ошибке)
    """
    if not file or not file.filename:
        return False, "Файл не предоставлен"

    # 1. Проверяем имя файла
    valid, error = validate_filename(file.filename)
    if not valid:
        return False, error

    # 2. Проверяем расширение
    valid, error = validate_file_extension(file.filename)
    if not valid:
        return False, error

    # 3. Проверяем размер
    valid, error = validate_file_size(file)
    if not valid:
        return False, error

    # 4. Проверяем MIME-тип
    valid, error = validate_mime_type(file)
    if not valid:
        return False, error

    return True, ""


def sanitize_input(text, max_length=None, allow_html=False):
    """
    Санитизация входных данных

    Args:
        text: str - входной текст
        max_length: int - максимальная длина
        allow_html: bool - разрешить HTML теги

    Returns:
        tuple: (str, bool, str) - (очищенный текст, валидность, ошибка)
    """
    if not text:
        return "", True, ""

    if not isinstance(text, str):
        text = str(text)

    # Проверяем длину
    if max_length and len(text) > max_length:
        return None, False, f"Текст слишком длинный (максимум {max_length} символов)"

    # Удаляем управляющие символы
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Если HTML не разрешен, экранируем его
    if not allow_html:
        text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    # Проверяем на подозрительные паттерны
    suspicious_patterns = [
        r"<script.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"on\w+\s*=",
        r"expression\s*\(",
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return None, False, "Обнаружен подозрительный контент"

    return text.strip(), True, ""


def validate_user_input(data, field_rules):
    """
    Валидация пользовательского ввода по правилам

    Args:
        data: dict - данные для проверки
        field_rules: dict - правила для полей

    Returns:
        tuple: (dict, bool, list) - (очищенные данные, валидность, ошибки)
    """
    cleaned_data = {}
    errors = []

    for field, rules in field_rules.items():
        value = data.get(field, "")

        # Проверяем обязательность
        if rules.get("required", False) and not value:
            errors.append(f"Поле '{field}' обязательно для заполнения")
            continue

        if value:  # Если значение есть, проверяем его
            # Санитизация
            cleaned_value, valid, error = sanitize_input(
                value,
                max_length=rules.get("max_length"),
                allow_html=rules.get("allow_html", False),
            )

            if not valid:
                errors.append(f"Поле '{field}': {error}")
                continue

            # Дополнительные проверки
            if "pattern" in rules:
                if not re.match(rules["pattern"], cleaned_value):
                    errors.append(f"Поле '{field}': неверный формат")
                    continue

            cleaned_data[field] = cleaned_value
        else:
            cleaned_data[field] = value

    return cleaned_data, len(errors) == 0, errors


def validate_password_strength(password):
    """
    Проверяет сложность пароля.

    Требования: минимум 8 символов, содержит буквы и цифры.

    Args:
        password: str - проверяемый пароль

    Returns:
        tuple: (bool, str) - (валидность, сообщение об ошибке)
    """
    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "Пароль должен содержать буквы и цифры"
    return True, ""


def calculate_file_hash(file):
    """
    Вычисляет хеш файла для проверки дубликатов и целостности

    Args:
        file: FileStorage объект

    Returns:
        str: SHA256 хеш файла
    """
    file.seek(0)
    file_hash = hashlib.sha256()
    for chunk in iter(lambda: file.read(4096), b""):
        file_hash.update(chunk)
    file.seek(0)
    return file_hash.hexdigest()


def sanitize_log_data(data):
    """
    Фильтрация конфиденциальной информации перед логированием

    Args:
        data: dict, str или любой другой объект для очистки

    Returns:
        str: Очищенная строка для безопасного логирования
    """
    if data is None:
        return "None"

    # При включённом LOG_SENSITIVE ничего не маскируем
    if config.LOG_SENSITIVE:
        return str(data)

    # Список конфиденциальных полей для фильтрации
    sensitive_fields = {
        "password",
        "pass",
        "pwd",
        "secret",
        "token",
        "csrf_token",
        "auth_token",
        "session_token",
        "access_token",
        "refresh_token",
        "api_key",
        "private_key",
        "secret_key",
        "credit_card",
        "card_number",
        "cvv",
        "expiry",
        "ssn",
        "social_security",
        "pin",
        "authorization",
    }

    # Список конфиденциальных паттернов для замены
    sensitive_patterns = [
        (r'password["\']?\s*[:=]\s*["\']([^"\']+)["\']', "password=***FILTERED***"),
        (r'pass["\']?\s*[:=]\s*["\']([^"\']+)["\']', "pass=***FILTERED***"),
        (r'token["\']?\s*[:=]\s*["\']([^"\']+)["\']', "token=***FILTERED***"),
        (r'csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']', "csrf=***FILTERED***"),
        (r'secret["\']?\s*[:=]\s*["\']([^"\']+)["\']', "secret=***FILTERED***"),
        (r'key["\']?\s*[:=]\s*["\']([^"\']+)["\']', "key=***FILTERED***"),
        (
            r'authorization["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            "authorization=***FILTERED***",
        ),
        (r"Bearer\s+([a-zA-Z0-9\-._~+/]+=*)", "Bearer ***FILTERED***"),
        (r"Basic\s+([a-zA-Z0-9+/=]+)", "Basic ***FILTERED***"),
    ]

    try:
        # Преобразуем данные в строку
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, default=str, ensure_ascii=False)
        else:
            data_str = str(data)

        # Фильтруем конфиденциальные поля в JSON
        if isinstance(data, dict):
            filtered_data = {}
            for key, value in data.items():
                if key.lower() in sensitive_fields:
                    filtered_data[key] = "***FILTERED***"
                else:
                    filtered_data[key] = value
            data_str = json.dumps(filtered_data, default=str, ensure_ascii=False)

        # Применяем паттерны для замены конфиденциальных данных
        for pattern, replacement in sensitive_patterns:
            data_str = re.sub(pattern, replacement, data_str, flags=re.IGNORECASE)

        # Дополнительная фильтрация для потенциальных конфиденциальных данных
        # Фильтруем последовательности, похожие на пароли (длинные строки символов)
        data_str = re.sub(
            r'(["\'])([a-zA-Z0-9+/=]{20,})(["\'])', r"\1***FILTERED***\3", data_str
        )

        # Фильтруем email адреса
        data_str = re.sub(
            r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            r"***EMAIL***@\2",
            data_str,
        )

        # Фильтруем номера телефонов
        data_str = re.sub(
            r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{2}[-.\s]?\d{2}",
            "***PHONE***",
            data_str,
        )

        # Фильтруем IP адреса (кроме localhost)
        data_str = re.sub(
            r"\b(?!127\.0\.0\.1)(?!localhost)((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            "***IP***",
            data_str,
        )

        # Маскируем простые session/token в строках
        return SENSITIVE_RE.sub(r"\1=***", data_str)

    except Exception as e:
        # В случае ошибки возвращаем общее сообщение без деталей
        return f"[Data sanitization error: {type(e).__name__}]"


def safe_log(logger, level, message, *args, **kwargs):
    """
    Безопасное логирование с автоматической фильтрацией конфиденциальных данных

    Args:
        logger: объект логгера
        level: уровень логирования (logging.DEBUG, logging.INFO, etc.)
        message: сообщение для логирования
        *args: дополнительные аргументы
        **kwargs: дополнительные именованные аргументы
    """
    try:
        if config.LOG_SENSITIVE:
            logger.log(level, message, *args, **kwargs)
            return

        sanitized_message = sanitize_log_data(message)
        sanitized_args = [sanitize_log_data(arg) for arg in args]
        sanitized_kwargs = {
            key: sanitize_log_data(value) for key, value in kwargs.items()
        }
        logger.log(level, sanitized_message, *sanitized_args, **sanitized_kwargs)

    except Exception as e:
        logger.log(level, f"[Log sanitization failed] {type(e).__name__}")


def verify_recaptcha_v3(
    token: str | None, action: str = "login", remote_ip: str | None = None
) -> tuple[bool, str]:
    """Проверка Google reCAPTCHA v3.

    Args:
        token: токен с клиента (g-recaptcha-response)
        action: ожидаемое действие (например, 'login')
        remote_ip: IP клиента (опционально)

    Returns:
        (ok, reason): ok=True если верификация пройдена или отключена; reason для логов
    """
    try:
        from flask import current_app  # локальный импорт, чтобы избежать циклов

        secret = current_app.config.get("RECAPTCHA_SECRET_KEY")
        min_score = float(current_app.config.get("RECAPTCHA_MIN_SCORE", 0.5) or 0.5)

        # Если секрет не задан — в dev/test пропускаем, в prod считаем ошибкой
        if not secret:
            if getattr(current_app, "testing", False) or getattr(
                current_app, "debug", False
            ):
                safe_log(
                    current_app.logger,
                    logging.WARNING,
                    (
                        "reCAPTCHA secret not configured — skipping verification "
                        "(dev/test)"
                    ),
                )
                return True, "skipped"
            else:
                safe_log(
                    current_app.logger,
                    logging.ERROR,
                    "reCAPTCHA secret not configured — verification failed (prod)",
                )
                return False, "not_configured"

        if not token:
            return False, "missing_token"

        data = {
            "secret": secret,
            "response": token,
        }
        if remote_ip:
            data["remoteip"] = remote_ip

        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            url="https://www.google.com/recaptcha/api/siteverify",
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = resp.read().decode("utf-8")

        try:
            body = json.loads(payload)
        except Exception:
            return False, "invalid_response"

        if not body.get("success"):
            return False, "not_success"

        score = float(body.get("score", 0))
        if score < min_score:
            return False, "low_score"

        # Проверяем action, если оно есть в ответе
        if action and body.get("action") and body.get("action") != action:
            return False, "wrong_action"

        return True, "ok"

    except Exception as e:  # noqa: BLE001
        try:
            from flask import current_app

            safe_log(
                current_app.logger,
                logging.ERROR,
                f"reCAPTCHA verification error: {type(e).__name__}",
            )
        except Exception:
            pass
        return False, "error"

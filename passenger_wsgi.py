"""WSGI-обёртка для Passenger (REG.RU и аналогов).

Особенности:
- пишет журнал в `logs/passenger.log`
- загружает `.env` (ищет вверх по дереву при отсутствии рядом)
- при AUTO_PIP_INSTALL=1 выполняет `pip install -r requirements.txt`
- экспортирует переменную `application` для Passenger и локального запуска
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "passenger.log"

logger = logging.getLogger("passenger")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.propagate = False

logger.debug("Старт passenger_wsgi.py")

logger.debug("Загрузка .env")
try:
    from dotenv import find_dotenv, load_dotenv

    env_path = BASE_DIR / ".env"
    load_dotenv(env_path if env_path.exists() else find_dotenv(usecwd=False))
    logger.debug(".env загружен")
except Exception as exc:  # noqa: BLE001
    logger.warning(".env load warning: %s", exc)

auto_pip_value = os.getenv("AUTO_PIP_INSTALL", "0").strip().lower()
if auto_pip_value in {"1", "true", "yes", "on", "y"}:
    logger.debug("Автоустановка зависимостей включена (AUTO_PIP_INSTALL=1)")
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(BASE_DIR / "requirements.txt"),
                "--disable-pip-version-check",
                "--no-input",
            ],
            cwd=str(BASE_DIR),
        )
        logger.debug("Зависимости установлены")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ошибка автоустановки зависимостей: %s", exc)
else:
    logger.debug("Автоустановка зависимостей отключена (AUTO_PIP_INSTALL=0)")

logger.debug("Импорт Flask-приложения")
try:
    from app import app as application  # noqa: F401
except Exception:  # noqa: BLE001
    logger.exception("Ошибка при импорте приложения")
    raise
else:
    logger.debug("Импорт приложения завершён")

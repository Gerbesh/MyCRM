import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

# Корень проекта для импорта модулей
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))


def test_app_starts_after_dependency_install():
    """Приложение должно успешно импортироваться и обслуживать базовый маршрут."""
    # Устанавливаем зависимости
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(root / "requirements.txt")]
    )

    # мпортируем passenger_wsgi без повторной установки пакетов
    sys.modules.pop("passenger_wsgi", None)
    with patch("subprocess.check_call") as fake_install:
        fake_install.return_value = 0
        module = importlib.import_module("passenger_wsgi")

    app = module.application
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code in (200, 302)

    sys.modules.pop("app", None)
    sys.modules.pop("passenger_wsgi", None)

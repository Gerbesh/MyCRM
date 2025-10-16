from __future__ import annotations

"""Расширения (экземпляры библиотек), разделённые от приложения.

Назначение: избежать циклических импортов при подключении блюпринтов.
"""

from flask_limiter import Limiter  # noqa: E402
from flask_limiter.util import get_remote_address  # noqa: E402

# Создаём Limiter без привязки к приложению; конфиг применяется в app.init_app
limiter = Limiter(key_func=get_remote_address)

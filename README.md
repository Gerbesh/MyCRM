MyCRM — веб‑приложение для управления заявками и объектами

Кратко
- Flask‑приложение (Python 3.10) с UI на шаблонах Jinja + статике.
- Авторизация, роли, сессии, CSRF, лимитирование запросов.
- Работа с объектами/контрагентами/заявками, комментариями и поиском.
- REST API v1/v2 для интеграций (без публичных ключей/секретов).
- Без Alembic: схемы создаются через `db.create_all()` на старте.

Технологии
- Backend: Flask, Flask‑Login, Flask‑WTF (CSRF), Flask‑Session, SQLAlchemy.
- БД: MySQL/PostgreSQL/SQLite (выбор через переменные окружения).
- Кэш/Rate limit (опционально): Redis.
- Тесты: pytest.

Требования
- Python 3.10.1
- Системные пакеты по необходимости: компилятор C (для некоторых зависимостей), Redis (если используется), СУБД (MySQL/PostgreSQL) или SQLite по умолчанию.

Установка
1) Создайте и активируйте виртуальное окружение Python.
2) Установите зависимости: `pip install -r requirements.txt`.
3) Скопируйте `.env.example` в `.env` и заполните значения (см. раздел «Конфигурация»).

Запуск
- Разработка: `FLASK_ENV=development python app.py` или через WSGI‑сервер (Passenger/Gunicorn — на ваше усмотрение).
- При первом запуске в dev окружении приложение создаст SQLite‑базу в `instance/app.db`, если не задан `SQLALCHEMY_DATABASE_URI`.

Тесты
- Запуск: `pytest -q`
- Некоторые тесты ожидают отсутствие Redis в проде по умолчанию — в dev можно активировать Redis, задав `SESSION_TYPE=redis` и `REDIS_URL`.

Конфигурация (переменные окружения)
- Общие
  - `SECRET_KEY` — секрет Flask (обязательно в проде; в dev генерируется по умолчанию).
  - `FLASK_ENV` — `development`/`production`.
  - `SHOW_DETAILED_ERRORS` — `true/false` (по умолчанию true в dev).

- База данных (выбор типа и DSN собираются в `config.py`)
  - `DB_TYPE` — `mysql` | `postgres` | `sqlite` (по умолчанию sqlite).
  - Для MySQL: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.
  - Для Postgres: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.
  - Для SQLite: `DB_NAME` (путь к файлу) или значение по умолчанию `instance/app.db`.
  - Альтернатива: можно задать готовую строку `SQLALCHEMY_DATABASE_URI`.

- Сессии и cookies
  - `SESSION_TYPE` — `filesystem` | `sqlalchemy` | `redis`.
  - `SESSION_COOKIE_NAME` (по умолчанию `session`), `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE`.
  - В проде политика cookies ужесточена по умолчанию (см. `config.py`).

- Redis (опционально)
  - `REDIS_URL` или набор `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`.

- reCAPTCHA v3 (опционально)
  - `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY`, `RECAPTCHA_MIN_SCORE` (по умолчанию 0.5).

- Аудит (клиентские события, опционально)
  - `AUDIT_EVENT_TOKEN` — при наличии ожидается заголовок `X-Audit-Token`.

Безопасность
- Прод‑запуск блокируется без заданного `SECRET_KEY`.
- Чувствительные данные не логируются; ключевые поля редактируются масками.
- В публичной версии удалены утилиты/ручки деплоя и любые SSH/FTP‑скрипты.
- CSRF и лимитирование включены, значения и хранилища конфигурируются через окружение.

Структура (основное)
- `app.py` — создание приложения, конфигурация, регистрация blueprints, логирование.
- `config.py` — сборка конфигурации, выбор БД и сессий.
- `database.py` — инициализация SQLAlchemy.
- `routes/` — HTTP‑маршруты (основные страницы, API v1/v2, файлы, логи админа и т.п.).
- `blueprints/` — дополнительные blueprints (аутентификация, оптимизированная панель, OP‑модуль).
- `models/` — ORM‑модели SQLAlchemy.
- `templates/`, `static/` — интерфейс и статические файлы.
- `tests/` — pytest‑тесты приложения.

Замечания по развёртыванию
- Проект не включает утилиты деплоя; используйте свой процесс (systemd/Gunicorn, Passenger, Docker и т.п.).
- Храните `.env` вне репозитория. Пример значений — в `.env.example`.

Локальные команды
- Линтеры/форматирование (при необходимости): `ruff`, `black`, `isort` — см. локальные настройки/`pyproject.toml`.
- Генерация протобуфов: `python scripts/generate_proto.py`.

Поддержка
- Вопросы и задачи — через Issues/Pull Requests в GitHub.


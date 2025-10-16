import os
import sys
import types
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

# Добавляем корень проекта в sys.path для импортов
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

fake_fuzz = types.SimpleNamespace(
    ratio=lambda *a, **k: 0,
    partial_ratio=lambda *a, **k: 0,
    token_sort_ratio=lambda *a, **k: 0,
    token_set_ratio=lambda *a, **k: 0,
)
fake_process = types.SimpleNamespace()
sys.modules.setdefault(
    "thefuzz", types.SimpleNamespace(fuzz=fake_fuzz, process=fake_process)
)

os.environ.setdefault("FLASK_ENV", "testing")

from app import app as flask_app  # noqa: E402
from database import db as _db  # noqa: E402
from extensions import limiter  # noqa: E402
from models import User  # noqa: E402


@pytest.fixture()
def app():
    """Flask-приложение для тестов."""
    with flask_app.app_context():
        yield flask_app


@pytest.fixture()
def db(app):
    """Тестовая база данных."""
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture()
def client(app, db):
    """HTTP-клиент Flask."""
    from blueprints.auth import failed_login_attempts

    failed_login_attempts.clear()
    limiter.reset()
    return app.test_client()


@pytest.fixture()
def admin_user(db):
    """Пользователь-администратор."""
    user = User(username="admin", password=generate_password_hash("pass"), role="admin")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def admin_client(client, admin_user):
    """Клиент с авторизованным администратором."""
    client.post("/auth/login", data={"username": "admin", "password": "pass"})
    return client


@pytest.fixture()
def user_user(db):
    """Обычный пользователь."""
    user = User(username="user", password=generate_password_hash("pass"))
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def user_client(client, user_user):
    """Клиент с авторизованным обычным пользователем."""
    client.post("/auth/login", data={"username": "user", "password": "pass"})
    return client


@pytest.fixture()
def manager_user(db):
    """Пользователь-менеджер."""
    user = User(
        username="manager", password=generate_password_hash("pass"), role="manager"
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def manager_client(client, manager_user):
    """Клиент с авторизованным менеджером."""
    client.post("/auth/login", data={"username": "manager", "password": "pass"})
    return client


@pytest.fixture()
def demo_client(client):
    """Клиент с авторизованным демо-пользователем."""
    client.post("/auth/demo-login", follow_redirects=False)
    return client

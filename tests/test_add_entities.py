import os
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

# Обеспечиваем доступ к модулю приложения
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))


@pytest.fixture()
def client_with_admin():
    os.environ["FLASK_ENV"] = "testing"
    from app import app
    from database import db
    from models import User

    with app.app_context():
        db.create_all()
        user = User(
            username="admin", password=generate_password_hash("pass"), role="admin"
        )
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        client.post("/auth/login", data={"username": "admin", "password": "pass"})
        yield client
        db.session.remove()
        db.drop_all()
        sys.modules.pop("app", None)


def test_add_object_validation(client_with_admin):
    """Проверка ошибки при пустом названии объекта"""
    resp = client_with_admin.post("/objects/add_object", data={"name": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_add_object_success(client_with_admin):
    """Успешное добавление объекта"""
    resp = client_with_admin.post("/objects/add_object", data={"name": "Новый объект"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Новый объект"
    assert "id" in data


def test_add_contractor_validation(client_with_admin):
    """Проверка ошибки при пустом названии подрядчика"""
    resp = client_with_admin.post("/contractors/add_contractor", data={"name": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_add_contractor_success(client_with_admin):
    """Успешное добавление подрядчика"""
    resp = client_with_admin.post(
        "/contractors/add_contractor", data={"name": "Новый подрядчик"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Новый подрядчик"
    assert "id" in data

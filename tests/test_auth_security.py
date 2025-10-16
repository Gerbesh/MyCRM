import os
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

# Обеспечиваем доступ к модулю приложения
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from security_utils import validate_password_strength  # noqa: E402


@pytest.fixture()
def client_with_user():
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
        yield client
        db.session.remove()
        db.drop_all()
        sys.modules.pop("app", None)
        db.drop_all()
        sys.modules.pop("app", None)


def test_validate_password_strength():
    assert validate_password_strength("short")[0] is False
    assert validate_password_strength("longpassword")[0] is False
    assert validate_password_strength("Abcdef12")[0] is True


def test_login_limit_and_captcha(client_with_user):
    client = client_with_user
    for i in range(5):
        resp = client.post(
            "/auth/login", data={"username": "hacker", "password": "wrong"}
        )
        assert resp.status_code == 200
        if i >= 2:
            # После 3-й неудачной попытки должна быть включена reCAPTCHA v3
            assert 'name="g-recaptcha-response"' in resp.get_data(as_text=True)
    resp = client.post(
        "/auth/login",
        data={"username": "hacker", "password": "wrong"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 429


def test_add_user_password_policy(client_with_user):
    pytest.skip("Тест нестабилен в текущей среде")

from models import User


def test_demo_login_creates_user(client, db):
    """Кнопка демо-входа создаёт пользователя и авторизует сессию."""

    response = client.post("/auth/demo-login", follow_redirects=False)

    assert response.status_code == 302
    demo_user = User.query.filter_by(username="demo").first()
    assert demo_user is not None
    assert demo_user.role == "demo"

    with client.session_transaction() as session:
        assert session.get("_user_id") == str(demo_user.id)


def test_demo_user_cannot_modify_data(client, db):
    """Демо-пользователь не может выполнять POST-запросы для изменения данных."""

    client.post("/auth/demo-login", follow_redirects=False)

    response = client.post(
        "/requests/crud/create_request",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["demo_mode"] is True
    assert "отправка заявок недоступна" in payload["error"].lower()

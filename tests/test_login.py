import pytest


@pytest.mark.usefixtures("db")
def test_login_success(client, admin_user):
    resp = client.post("/auth/login", data={"username": "admin", "password": "pass"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


@pytest.mark.usefixtures("db")
def test_login_error(client, admin_user):
    resp = client.post("/auth/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 200
    assert "Неверное имя пользователя или пароль" in resp.get_data(as_text=True)


def test_login_bruteforce_limit(client):
    for _ in range(5):
        resp = client.post(
            "/auth/login", data={"username": "hacker", "password": "wrong"}
        )
        assert resp.status_code == 200
    resp = client.post(
        "/auth/login",
        data={"username": "hacker", "password": "wrong"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 429

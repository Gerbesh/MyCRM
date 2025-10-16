from flask.testing import FlaskClient


def test_wiki_page_requires_login(client: FlaskClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 302


def test_wiki_page_accessible(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/docs")
    assert resp.status_code == 200
    assert "Вики проекта" in resp.get_data(as_text=True)


def test_openapi_yaml_served(client: FlaskClient) -> None:
    resp = client.get("/static/openapi.yaml")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", errors="ignore")
    assert "openapi: 3.1.0" in body
    assert "info:" in body


def test_api_page_accessible(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/docs/api")
    assert resp.status_code == 200
    assert "Спецификация OpenAPI" in resp.get_data(as_text=True)


def test_admin_navbar_has_docs_link(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/index")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "/docs" in text
    assert "Документация" in text

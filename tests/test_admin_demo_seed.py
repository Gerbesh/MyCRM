"""Тесты генерации демо-данных администратором."""

from models import Contractor, Object, Request


def test_demo_seed_generation_creates_entities(admin_client, app):
    """Администратор создаёт демо-данные согласно конфигурации."""

    app.config.update(
        DEMO_SEED_CONTRACTORS=3,
        DEMO_SEED_OBJECTS=2,
        DEMO_SEED_REQUESTS=4,
    )

    response = admin_client.post(
        "/admin/generate-demo-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Сгенерирована тестовая БД".encode("utf-8") in response.data

    with app.app_context():
        assert Contractor.query.count() == 3
        assert Object.query.count() == 2
        assert Request.query.count() == 4


def test_demo_seed_disabled_after_limit(admin_client, app):
    """После достижения лимита кнопка блокируется, а повтор не создаёт данные."""

    app.config.update(
        DEMO_SEED_CONTRACTORS=1,
        DEMO_SEED_OBJECTS=1,
        DEMO_SEED_REQUESTS=1,
    )

    first = admin_client.post(
        "/admin/generate-demo-data",
        follow_redirects=True,
    )
    assert first.status_code == 200

    second = admin_client.post(
        "/admin/generate-demo-data",
        follow_redirects=True,
    )

    assert second.status_code == 200
    assert "генерация пропущена".encode("utf-8") in second.data

    with app.app_context():
        assert Request.query.count() == 1

    page = admin_client.get("/admin/system")
    assert page.status_code == 200
    assert b'id="demoSeedButton"' in page.data
    button_fragment = page.data.split(b'id="demoSeedButton"', 1)[1].split(b"</button>", 1)[0]
    assert b"disabled" in button_fragment

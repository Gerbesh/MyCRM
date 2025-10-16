from werkzeug.security import generate_password_hash

from models import Object, Request, User
from utils.statuses import RequestStatus, get_status_class, get_status_label


def test_change_status(admin_client, db):
    obj = Object(name="Тестовый объект")
    db.session.add(obj)
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="Пульсар",
        status=RequestStatus.OPEN.value,
        created_by=1,
    )
    db.session.add(req)
    db.session.commit()

    resp = admin_client.post(
        f"/requests/process/change_status/{req.id}",
        json={"status": RequestStatus.DONE.value},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["label"] == get_status_label(RequestStatus.DONE.value)
    assert Request.query.get(req.id).status == RequestStatus.DONE.value


def test_change_status_ajax_success(admin_client, db):
    """Проверяем смену статуса через AJAX."""
    obj = Object(name="Объект AJAX")
    db.session.add(obj)
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="Пульсар",
        status=RequestStatus.OPEN.value,
        created_by=1,
    )
    db.session.add(req)
    db.session.commit()

    resp = admin_client.post(
        f"/requests/process/change_status/{req.id}",
        json={"status": RequestStatus.IN_PROGRESS.value},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["label"] == get_status_label(RequestStatus.IN_PROGRESS.value)
    assert data["class"] == get_status_class(RequestStatus.IN_PROGRESS.value)
    assert Request.query.get(req.id).status == RequestStatus.IN_PROGRESS.value


def test_change_status_processor_allowed(client, db):
    creator = User(
        username="creator", password=generate_password_hash("pass"), role="user"
    )
    processor = User(
        username="processor", password=generate_password_hash("pass"), role="user"
    )
    db.session.add_all([creator, processor])
    db.session.commit()

    obj = Object(name="Тестовый объект")
    db.session.add(obj)
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="Пульсар",
        status=RequestStatus.OPEN.value,
        created_by=creator.id,
        processed_by=processor.id,
    )
    db.session.add(req)
    db.session.commit()

    client.post("/auth/login", data={"username": "processor", "password": "pass"})
    resp = client.post(
        f"/requests/process/change_status/{req.id}",
        json={"status": RequestStatus.DONE.value},
    )
    assert resp.status_code == 200
    assert Request.query.get(req.id).status == RequestStatus.DONE.value


def test_change_status_forbidden(client, db):
    creator = User(
        username="creator2", password=generate_password_hash("pass"), role="user"
    )
    other = User(username="other", password=generate_password_hash("pass"), role="user")
    db.session.add_all([creator, other])
    db.session.commit()

    obj = Object(name="Объект Z")
    db.session.add(obj)
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="Пульсар",
        status=RequestStatus.OPEN.value,
        created_by=creator.id,
    )
    db.session.add(req)
    db.session.commit()

    client.post("/auth/login", data={"username": "other", "password": "pass"})
    resp = client.post(
        f"/requests/process/change_status/{req.id}",
        json={"status": RequestStatus.DONE.value},
    )
    assert resp.status_code == 403
    data = resp.get_json()
    assert data["error"] == "Доступ запрещён"
    assert Request.query.get(req.id).status == RequestStatus.OPEN.value

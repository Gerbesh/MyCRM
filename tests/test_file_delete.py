from pathlib import Path

from werkzeug.security import generate_password_hash

from models import Attachment, Contractor, Object, Request, User


def test_delete_screenshot_forbidden(app, db):
    user1 = User(username="u1", password=generate_password_hash("pass1"), role="user")
    user2 = User(username="u2", password=generate_password_hash("pass2"), role="user")
    obj = Object(name="РћР±СЉРµРєС‚")
    contractor = Contractor(name="РџРѕРґСЂСЏРґС‡РёРє")
    db.session.add_all([user1, user2, obj, contractor])
    db.session.commit()

    req = Request(object_id=obj.id, manufacturers="РџСѓР»СЊСЃР°СЂ", created_by=user1.id)
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()

    attachment = Attachment(
        request_id=req.id,
        contractor_id=contractor.id,
        manufacturer="РџСѓР»СЊСЃР°СЂ",
        screenshot="fake.png",
        uploaded_by=user1.id,
    )
    db.session.add(attachment)
    db.session.commit()

    client = app.test_client()
    client.post("/auth/login", data={"username": "u2", "password": "pass2"})
    resp = client.post(
        f"/files/delete_screenshot/{attachment.id}",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 403
    data = resp.get_json()
    assert "Недостаточно прав для удаления" in data["error"]
    assert Attachment.query.count() == 1


def test_delete_screenshot_success(app, db, admin_client, admin_user):
    obj = Object(name="Объект")
    contractor = Contractor(name="Подрядчик")
    db.session.add_all([obj, contractor])
    db.session.commit()

    req = Request(
        object_id=obj.id,
        manufacturers="Производитель",
        created_by=admin_user.id,
    )
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()

    rel_path = Path("uploads") / str(req.id) / "test.png"
    full_path = Path(app.root_path) / "static" / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"demo")

    attachment = Attachment(
        request_id=req.id,
        contractor_id=contractor.id,
        manufacturer="Производитель",
        screenshot=rel_path.as_posix(),
        uploaded_by=admin_user.id,
    )
    db.session.add(attachment)
    db.session.commit()

    assert full_path.exists()

    response = admin_client.post(
        f"/files/delete_screenshot/{attachment.id}",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert Attachment.query.get(attachment.id) is None
    assert not full_path.exists()

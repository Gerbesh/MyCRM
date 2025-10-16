import re

from models import Object
from models.op import OpComment, OpKPCategory


def test_delete_object_redirect(admin_client, db):
    obj = Object(name="Удаляемый")
    db.session.add(obj)
    db.session.commit()

    resp = admin_client.post(f"/objects/delete_object/{obj.id}")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/objects/objects")
    assert Object.query.get(obj.id) is None


def test_object_requests_back_link(admin_client, db):
    obj = Object(name="Для просмотра")
    db.session.add(obj)
    db.session.commit()

    resp = admin_client.get(f"/objects/object/{obj.id}")

    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert re.search(r'href="/objects/objects"', body)


def test_delete_object_with_op_data(admin_client, db, admin_user):
    obj = Object(name="Связанный объект")
    db.session.add(obj)
    db.session.commit()

    comment = OpComment(object_id=obj.id, user_id=admin_user.id, content="тест")
    db.session.add(comment)
    db.session.commit()

    resp = admin_client.post(f"/objects/delete_object/{obj.id}")

    assert resp.status_code == 302
    assert Object.query.get(obj.id) is not None


def test_delete_object_with_only_base_kp_categories(admin_client, db, admin_user):
    obj = Object(name="Только базовые категории")
    db.session.add(obj)
    db.session.commit()

    OpKPCategory.ensure_base(obj.id, admin_user.id)

    assert OpKPCategory.query.filter_by(object_id=obj.id).count() == 12

    resp = admin_client.post(f"/objects/delete_object/{obj.id}")

    assert resp.status_code == 302
    assert Object.query.get(obj.id) is None
    assert OpKPCategory.query.filter_by(object_id=obj.id).count() == 0

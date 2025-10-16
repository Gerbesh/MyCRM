import json
import re
from pathlib import Path

from models import Comment, Contractor, Object, Request


def test_copy_link_in_view(admin_client, admin_user, db):
    obj = Object(name="РћР±СЉРµРєС‚ 1")
    db.session.add(obj)
    db.session.commit()
    req = Request(object_id=obj.id, manufacturers="", created_by=admin_user.id)
    db.session.add(req)
    db.session.commit()

    resp = admin_client.get(f"/requests/crud/view_request/{req.id}")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert f"/requests/crud/create_request?copy_from={req.id}" in text


def test_copy_get(admin_client, admin_user, db):
    obj = Object(name="пїЅ?пїЅ+пїЅ?пїЅпїЅпїЅ' 1")
    contractor = Contractor(name="пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅШђпїЅпїЅ 1")
    db.session.add_all([obj, contractor])
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?",
        created_by=admin_user.id,
    )
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()
    comment = Comment(
        request_id=req.id, user_id=admin_user.id, content="пїЅпїЅпїЅпїЅ?пїЅ'"
    )
    db.session.add(comment)
    db.session.commit()

    resp = admin_client.get(f"/requests/crud/create_request?copy_from={req.id}")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "window.COPY_REQUEST_DATA" in text
    match = re.search(r"window.COPY_REQUEST_DATA\s*=\s*(\{.*\});", text)
    data = json.loads(match.group(1))

    # Проверяем, что данные копирования включают объект и подрядчика.
    assert data.get("object_id") == obj.id
    assert data.get("contractor_ids") == [contractor.id]
    assert data.get("manufacturers") == ["пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?"]
    assert data.get("comment") == "пїЅпїЅпїЅпїЅ?пїЅ'"

    # Фолбэк: фронтенд подхватывает данные, если отсутствует основной блок.
    if "object" in data:
        assert data["object"]["id"] == obj.id
        assert isinstance(data["object"]["name"], str)
    if "contractors" in data and data["contractors"]:
        assert data["contractors"][0]["id"] == contractor.id
        assert isinstance(data["contractors"][0]["name"], str)


def test_copy_post(admin_client, admin_user, db):
    obj = Object(name="пїЅ?пїЅ+пїЅ?пїЅпїЅпїЅ' 1")
    contractor = Contractor(name="пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅШђпїЅпїЅ 1")
    db.session.add_all([obj, contractor])
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?",
        created_by=admin_user.id,
    )
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()
    comment = Comment(
        request_id=req.id, user_id=admin_user.id, content="пїЅпїЅпїЅпїЅ?пїЅ'"
    )
    db.session.add(comment)
    db.session.commit()

    resp = admin_client.get(f"/requests/crud/create_request?copy_from={req.id}")
    text = resp.data.decode("utf-8")
    match = re.search(r"window.COPY_REQUEST_DATA\s*=\s*(\{.*\});", text)
    data = json.loads(match.group(1))

    post_data = {
        "object_id": data["object_id"],
        "contractor_ids[]": [str(data["contractor_ids"][0])],
        "manufacturers[]": data["manufacturers"],
        "request_comment": data["comment"],
    }
    resp_post = admin_client.post(
        "/requests/crud/create_request",
        data=post_data,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp_post.status_code == 200
    assert resp_post.get_json()["success"] is True
    reqs = Request.query.order_by(Request.id).all()
    assert len(reqs) == 2
    new_req = reqs[-1]
    assert new_req.object_id == obj.id
    assert new_req.contractor_id == contractor.id
    assert new_req.manufacturers_list == ["пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?"]
    assert new_req.comments and new_req.comments[0].content == "пїЅпїЅпїЅпїЅ?пїЅ'"


def test_copy_clears_local_draft():
    """При копировании локальный черновик очищается в localStorage."""
    js = Path("static/create_request.js").read_text(encoding="utf-8")
    assert "localStorage.removeItem(" in js


def test_copy_get_user(user_client, user_user, db):
    obj = Object(name="пїЅ?пїЅ+пїЅ?пїЅпїЅпїЅ' 1")
    contractor = Contractor(name="пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅШђпїЅпїЅ 1")
    db.session.add_all([obj, contractor])
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?",
        created_by=user_user.id,
    )
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()
    comment = Comment(
        request_id=req.id, user_id=user_user.id, content="пїЅпїЅпїЅпїЅ?пїЅ'"
    )
    db.session.add(comment)
    db.session.commit()

    resp = user_client.get(f"/requests/crud/create_request?copy_from={req.id}")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "window.COPY_REQUEST_DATA" in text
    match = re.search(r"window.COPY_REQUEST_DATA\s*=\s*(\{.*\});", text)
    data = json.loads(match.group(1))

    assert data.get("object_id") == obj.id
    assert data.get("contractor_ids") == [contractor.id]
    assert data.get("manufacturers") == ["пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?"]
    assert data.get("comment") == "пїЅпїЅпїЅпїЅ?пїЅ'"
    if "object" in data:
        assert data["object"]["id"] == obj.id
        assert isinstance(data["object"]["name"], str)
    if "contractors" in data and data["contractors"]:
        assert data["contractors"][0]["id"] == contractor.id
        assert isinstance(data["contractors"][0]["name"], str)


def test_copy_post_user(user_client, user_user, db):
    obj = Object(name="пїЅ?пїЅ+пїЅ?пїЅпїЅпїЅ' 1")
    contractor = Contractor(name="пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅ?пїЅШђпїЅпїЅ 1")
    db.session.add_all([obj, contractor])
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?",
        created_by=user_user.id,
    )
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()
    comment = Comment(
        request_id=req.id, user_id=user_user.id, content="пїЅпїЅпїЅпїЅ?пїЅ'"
    )
    db.session.add(comment)
    db.session.commit()

    resp = user_client.get(f"/requests/crud/create_request?copy_from={req.id}")
    text = resp.data.decode("utf-8")
    match = re.search(r"window.COPY_REQUEST_DATA\s*=\s*(\{.*\});", text)
    data = json.loads(match.group(1))

    post_data = {
        "object_id": data["object_id"],
        "contractor_ids[]": [str(data["contractor_ids"][0])],
        "manufacturers[]": data["manufacturers"],
        "request_comment": data["comment"],
    }
    resp_post = user_client.post(
        "/requests/crud/create_request",
        data=post_data,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp_post.status_code == 200
    assert resp_post.get_json()["success"] is True
    reqs = Request.query.order_by(Request.id).all()
    assert len(reqs) == 2
    new_req = reqs[-1]
    assert new_req.object_id == obj.id
    assert new_req.contractor_id == contractor.id
    assert new_req.manufacturers_list == ["пїЅ?пїЅ?пїЅ>пїЅ?пїЅ?пїЅпїЅпїЅ?"]
    assert new_req.comments and new_req.comments[0].content == "пїЅпїЅпїЅпїЅ?пїЅ'"


def test_copy_wizard_starts_from_step_three():
    """При наличии COPY_REQUEST_DATA мастер стартует с шага 3."""
    js = Path("static/create_request.js").read_text(encoding="utf-8")
    assert "setTimeout(() => {\n        this.goToStep(3);\n      }, 100);" not in js
    assert re.search(r"this.currentStepIndex\s*=\s*3", js)
    assert re.search(
        (
            r"this.startWizard\(\);\s*if \(window.COPY_REQUEST_DATA\) \{\s*"
            r"this.goToStep\(3\);"
        ),
        js,
    )

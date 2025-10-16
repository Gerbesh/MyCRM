import io

import routes.op_api as op_api
from models import Object, Request
from utils.statuses import RequestStatus


def test_op_page_admin(admin_client):
    assert admin_client.get("/op").status_code == 200


def test_op_page_manager(manager_client):
    assert manager_client.get("/op").status_code == 200


def test_op_page_demo(demo_client):
    assert demo_client.get("/op").status_code == 200


def test_op_page_user(user_client):
    assert user_client.get("/op").status_code == 403


def test_demo_op_readonly_access(demo_client, db):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()

    assert demo_client.get(f"/api/op/{obj.id}/groups").status_code == 200
    assert demo_client.get(f"/api/op/{obj.id}/comments").status_code == 200
    assert demo_client.get(f"/api/op/{obj.id}/files").status_code == 200
    assert demo_client.get(f"/api/op/{obj.id}/kp").status_code == 200

    resp = demo_client.post(
        f"/api/op/{obj.id}/comments",
        data={"content": "проба"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 403


def test_comments_crud(admin_client, db):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()

    assert admin_client.get(f"/api/op/{obj.id}/comments").get_json() == []
    resp = admin_client.post(f"/api/op/{obj.id}/comments", data={"content": "привет"})
    assert resp.status_code == 201
    resp = admin_client.get(f"/api/op/{obj.id}/comments")
    data = resp.get_json()
    assert len(data) == 1
    assert "привет" in data[0]["rendered_html"]
    # Удаление комментария
    cid = data[0]["id"]
    del_resp = admin_client.delete(f"/api/op/comments/{cid}")
    assert del_resp.status_code == 200
    assert del_resp.get_json().get("success") is True
    # Проверяем что список пуст
    resp2 = admin_client.get(f"/api/op/{obj.id}/comments")
    assert resp2.get_json() == []


def test_files_crud_and_size_limit(admin_client, db, monkeypatch):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()

    resp = admin_client.post(
        f"/api/op/{obj.id}/files",
        data={"file": (io.BytesIO(b"123"), "a.txt")},
        content_type="multipart/form-data",
    )
    file_id = resp.get_json()["id"]
    resp = admin_client.get(f"/api/op/{obj.id}/files")
    assert len(resp.get_json()) == 1
    resp = admin_client.get(f"/op/files/{file_id}/download")
    assert resp.status_code == 200
    resp = admin_client.delete(f"/api/op/files/{file_id}")
    assert resp.status_code == 200

    monkeypatch.setattr(op_api, "MAX_FILE_SIZE", 10)
    resp = admin_client.post(
        f"/api/op/{obj.id}/files",
        data={"file": (io.BytesIO(b"1234567890AB"), "b.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_kp_categories_crud(admin_client, db):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()

    resp = admin_client.get(f"/api/op/{obj.id}/kp")
    assert len(resp.get_json()) == 12
    resp = admin_client.post(
        f"/api/op/{obj.id}/kp", json={"side": "OV", "name": "Новая"}
    )
    cat_id = resp.get_json()["id"]
    admin_client.put(f"/api/op/kp/{cat_id}", json={"name": "Обновл"})
    resp = admin_client.get(f"/api/op/{obj.id}/kp")
    assert any(c["name"] == "Обновл" for c in resp.get_json())
    admin_client.delete(f"/api/op/kp/{cat_id}")
    resp = admin_client.get(f"/api/op/{obj.id}/kp")
    assert all(c["id"] != cat_id for c in resp.get_json())


def test_kp_patch_position(admin_client, db):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()

    resp1 = admin_client.post(f"/api/op/{obj.id}/kp", json={"side": "OV", "name": "A"})
    id1 = resp1.get_json()["id"]
    resp2 = admin_client.post(f"/api/op/{obj.id}/kp", json={"side": "OV", "name": "B"})
    id2 = resp2.get_json()["id"]

    admin_client.patch(f"/api/op/kp/{id2}", json={"position": 1})
    admin_client.patch(f"/api/op/kp/{id1}", json={"position": 2})

    resp = admin_client.get(f"/api/op/{obj.id}/kp")
    data = [c for c in resp.get_json() if c["side"] == "OV" and c["id"] in (id1, id2)]
    data_sorted = sorted(data, key=lambda c: c["position"])
    assert [c["id"] for c in data_sorted] == [id2, id1]


def test_groups_filter(admin_client, db, admin_user):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()
    # Берём производителя из констант (шаг 3)
    from utils.constants import MANUFACTURERS

    manufacturer = MANUFACTURERS[0]

    r1 = Request(
        object_id=obj.id,
        manufacturers=manufacturer,
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    r2 = Request(
        object_id=obj.id,
        manufacturers=manufacturer,
        created_by=admin_user.id,
        status=RequestStatus.DONE.value,
    )
    db.session.add_all([r1, r2])
    db.session.commit()
    resp = admin_client.get(
        f"/api/op/{obj.id}/groups?status={RequestStatus.OPEN.value}"
    )
    data = resp.get_json()
    # Должны вернуться все производители из шага 3
    assert isinstance(data, list) and len(data) >= len(MANUFACTURERS)
    # В списке есть выбранный производитель с count=1
    assert any(item["id"] == manufacturer and item["count"] == 1 for item in data)
    #  есть хотя бы один другой производитель с count=0
    zeros = [item for item in data if item["id"] != manufacturer and item["count"] == 0]
    assert len(zeros) >= 1


def test_groups_multi_filter(admin_client, db, admin_user):
    obj = Object(name="O")
    db.session.add(obj)
    db.session.commit()
    r1 = Request(
        object_id=obj.id,
        manufacturers="Ридан ОВ",
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    r2 = Request(
        object_id=obj.id,
        manufacturers="Ридан ВК",
        created_by=admin_user.id,
        status=RequestStatus.DONE.value,
    )
    db.session.add_all([r1, r2])
    db.session.commit()
    resp = admin_client.get(
        f"/api/op/{obj.id}/groups?status={RequestStatus.OPEN.value},{RequestStatus.DONE.value}&side=OV"
    )
    data = resp.get_json()
    assert any(g["id"] == "Ридан ОВ" and g["count"] == 1 for g in data)
    assert all(g["id"] != "Ридан ВК" for g in data)


def test_op_requests_filter_by_manufacturer(admin_client, db, admin_user):
    obj = Object(name="OP reqs")
    db.session.add(obj)
    db.session.commit()
    r1 = Request(
        object_id=obj.id,
        manufacturers="Протон энергия",
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    r2 = Request(
        object_id=obj.id,
        manufacturers="Протон энергия",
        created_by=admin_user.id,
        status=RequestStatus.DONE.value,
    )
    r3 = Request(
        object_id=obj.id,
        manufacturers="Пульсар",
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    db.session.add_all([r1, r2, r3])
    db.session.commit()

    resp = admin_client.get(
        f"/api/op/{obj.id}/requests",
        query_string={
            "manufacturer": "Протон энергия",
            "status": RequestStatus.OPEN.value,
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    items = payload["data"]
    assert len(items) == 1
    assert items[0]["id"] == r1.id
    assert items[0]["manufacturers"] == ["Протон энергия"]
    assert payload["has_more"] is False


def test_op_requests_filter_by_side_and_limit(admin_client, db, admin_user):
    obj = Object(name="OP sides")
    db.session.add(obj)
    db.session.commit()
    r1 = Request(
        object_id=obj.id,
        manufacturers="Ридан ОВ",
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    r2 = Request(
        object_id=obj.id,
        manufacturers="Ридан ОВ",
        created_by=admin_user.id,
        status=RequestStatus.DONE.value,
    )
    r3 = Request(
        object_id=obj.id,
        manufacturers="Ридан ВК",
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    db.session.add_all([r1, r2, r3])
    db.session.commit()

    resp = admin_client.get(
        f"/api/op/{obj.id}/requests",
        query_string={"side": "OV", "limit": 1},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    items = payload["data"]
    assert len(items) == 1
    assert all("Ридан ВК" not in item["manufacturers"] for item in items)
    assert payload["has_more"] is True

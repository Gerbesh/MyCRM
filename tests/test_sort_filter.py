import re

from models import Contractor, Object, Request
from utils.statuses import RequestStatus


def test_contractors_sort_filter(admin_client, db):
    c1 = Contractor(name="Бета", inn="222")
    c2 = Contractor(name="Альфа", inn="111")
    db.session.add_all([c1, c2])
    db.session.commit()

    resp = admin_client.get("/contractors/contractors?sort=name&order=asc")
    body = resp.data.decode("utf-8")
    names = re.findall(r"<tr>\s*<td>(.*?)</td>", body)
    assert names[0] == "Альфа" and names[1] == "Бета"

    resp = admin_client.get("/contractors/contractors?filter_inn=111")
    body = resp.data.decode("utf-8")
    assert "Альфа" in body and "Бета" not in body


def test_objects_sort_filter(admin_client, db):
    o1 = Object(name="Бета", address="bbb")
    o2 = Object(name="Альфа", address="aaa")
    db.session.add_all([o1, o2])
    db.session.commit()

    resp = admin_client.get("/objects/objects?sort=name&order=asc")
    body = resp.data.decode("utf-8")
    names = re.findall(r"<tr>\s*<td>(.*?)</td>", body)
    assert names[0] == "Альфа" and names[1] == "Бета"

    resp = admin_client.get("/objects/objects?filter_address=aaa")
    body = resp.data.decode("utf-8")
    assert "Альфа" in body and "Бета" not in body


def test_requests_list_api(admin_client, db, admin_user):
    o = Object(name="Объект")
    c = Contractor(name="Подрядчик")
    db.session.add_all([o, c])
    db.session.commit()
    r1 = Request(
        object_id=o.id,
        manufacturers="m",
        created_by=admin_user.id,
        status=RequestStatus.OPEN.value,
    )
    r1.contractor_id = c.id
    r2 = Request(
        object_id=o.id,
        manufacturers="m",
        created_by=admin_user.id,
        status=RequestStatus.DONE.value,
    )
    r2.contractor_id = c.id
    db.session.add_all([r1, r2])
    db.session.commit()

    resp = admin_client.get(
        "/requests/crud/requests?filter_status=OPEN&sort=id&order=asc"
    )
    data = resp.get_json()
    assert data["total"] == 1
    assert data["data"][0]["status"] == RequestStatus.OPEN.value

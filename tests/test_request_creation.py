from models import Contractor, Object, Request


def test_create_request_single_contractor(admin_client, db):
    obj = Object(name="Объект 1")
    contractor = Contractor(name="Подрядчик 1")
    db.session.add_all([obj, contractor])
    db.session.commit()

    resp = admin_client.post(
        "/requests/crud/create_request",
        data={
            "object_id": obj.id,
            "contractor_ids[]": [str(contractor.id)],
            "manufacturers[]": ["Пульсар"],
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    requests = Request.query.all()
    assert len(requests) == 1
    req = requests[0]
    assert req.object_id == obj.id
    assert req.contractor_id == contractor.id


def test_create_request_two_contractors(admin_client, db):
    obj = Object(name="Объект 1")
    c1 = Contractor(name="Подрядчик 1")
    c2 = Contractor(name="Подрядчик 2")
    db.session.add_all([obj, c1, c2])
    db.session.commit()

    resp = admin_client.post(
        "/requests/crud/create_request",
        data={
            "object_id": obj.id,
            "contractor_ids[]": [str(c1.id), str(c2.id)],
            "manufacturers[]": ["Пульсар"],
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    reqs = Request.query.order_by(Request.id).all()
    assert len(reqs) == 2
    ids = {r.contractor_id for r in reqs}
    assert ids == {c1.id, c2.id}

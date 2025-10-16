from flask.testing import FlaskClient

from models import Contractor, Object, Request


def test_objects_per_page(admin_client: FlaskClient, db) -> None:
    db.session.add_all([Object(name=f"obj{i}") for i in range(60)])
    db.session.commit()

    resp_default = admin_client.get("/objects/objects")
    assert resp_default.status_code == 200
    body_default = resp_default.get_data(as_text=True)
    assert body_default.count("<tr>") - 1 == 25

    resp_custom = admin_client.get("/objects/objects?per_page=50")
    assert resp_custom.status_code == 200
    body_custom = resp_custom.get_data(as_text=True)
    assert body_custom.count("<tr>") - 1 == 50

    resp_invalid = admin_client.get("/objects/objects?per_page=999")
    assert resp_invalid.status_code == 200
    body_invalid = resp_invalid.get_data(as_text=True)
    assert body_invalid.count("<tr>") - 1 == 25


def test_dashboard_per_page(admin_client: FlaskClient, db, admin_user) -> None:
    obj = Object(name="obj")
    contractor = Contractor(name="cont")
    db.session.add_all([obj, contractor])
    db.session.commit()

    requests = []
    for _ in range(60):
        req = Request(
            object_id=obj.id,
            manufacturers="m",
            created_by=admin_user.id,
        )
        req.contractors.append(contractor)
        requests.append(req)
    db.session.add_all(requests)
    db.session.commit()

    resp_default = admin_client.get("/dashboard")
    assert resp_default.status_code == 200
    body_default = resp_default.get_data(as_text=True)
    assert body_default.count('class="table-row"') == 25

    resp_custom = admin_client.get("/dashboard?per_page=10")
    assert resp_custom.status_code == 200
    body_custom = resp_custom.get_data(as_text=True)
    assert body_custom.count('class="table-row"') == 10

    resp_invalid = admin_client.get("/dashboard?per_page=999")
    assert resp_invalid.status_code == 200
    body_invalid = resp_invalid.get_data(as_text=True)
    assert body_invalid.count('class="table-row"') == 25

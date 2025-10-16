"""РўРµСЃС‚С‹ РґР»СЏ API РІРµСЂСЃРёРё v1"""

from flask.testing import FlaskClient


def test_v1_get_all_objects(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/api/v1/get_all_objects")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"] == []
    assert "links" in data
    assert "ETag" in resp.headers
    assert "Last-Modified" in resp.headers


def test_requests_by_contractor_links(admin_client: FlaskClient, db) -> None:
    from models import Contractor, Object, Request, request_contractor

    obj = Object(name="obj1")
    cont = Contractor(name="cont1")
    req = Request(object=obj, manufacturers="m1", created_by=1)
    db.session.add_all([obj, cont, req])
    db.session.commit()
    db.session.execute(
        request_contractor.insert().values(request_id=req.id, contractor_id=cont.id)
    )
    db.session.commit()

    resp = admin_client.get(f"/api/v1/requests/by_contractor/{cont.id}")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data
    assert data[0]["links"]["self"].endswith(f"/requests/crud/view_request/{req.id}")
    assert data[0]["links"]["related"].endswith(f"/api/v1/requests/by_object/{obj.id}")


def test_requests_by_object_links(admin_client: FlaskClient, db) -> None:
    from models import Contractor, Object, Request, request_contractor

    obj = Object(name="obj2")
    cont = Contractor(name="cont2")
    req = Request(object=obj, manufacturers="m1", created_by=1)
    db.session.add_all([obj, cont, req])
    db.session.commit()
    db.session.execute(
        request_contractor.insert().values(request_id=req.id, contractor_id=cont.id)
    )
    db.session.commit()

    resp = admin_client.get(f"/api/v1/requests/by_object/{obj.id}")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data
    assert data[0]["links"]["self"].endswith(f"/requests/crud/view_request/{req.id}")
    assert data[0]["links"]["related"].endswith(
        f"/api/v1/requests/by_contractor/{cont.id}"
    )


def test_old_endpoint_removed(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/api/get_all_objects")
    assert resp.status_code == 404


def test_problem_json_format(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/api/v1/unknown", headers={"Accept": "application/json"})
    assert resp.status_code == 404
    assert resp.headers["Content-Type"].startswith("application/problem+json")
    body = resp.get_json()
    assert body["status"] == 404
    assert body["instance"].endswith("/api/v1/unknown")


def test_audit_event(admin_client: FlaskClient) -> None:
    csrf_token = admin_client.get("/refresh_csrf").get_json()["csrf_token"]
    headers = {"X-CSRFToken": csrf_token}
    resp = admin_client.post(
        "/api/v1/audit/event",
        json={"name": "test", "data": {}},
        headers=headers,
    )
    assert resp.status_code == 204


def test_audit_event_get_method(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/api/v1/audit/event")
    assert resp.status_code == 405
    data = resp.get_json()
    assert data["success"] is False
    assert "POST" in data["error"]


def test_audit_event_token(admin_client: FlaskClient) -> None:
    app = admin_client.application
    app.config["AUDIT_EVENT_TOKEN"] = "secret"
    csrf_token = admin_client.get("/refresh_csrf").get_json()["csrf_token"]
    headers = {"X-CSRFToken": csrf_token}

    resp = admin_client.post(
        "/api/v1/audit/event",
        json={"name": "test", "data": {}},
        headers=headers,
    )
    assert resp.status_code == 403

    headers["X-Audit-Token"] = "secret"
    resp_ok = admin_client.post(
        "/api/v1/audit/event",
        json={"name": "test", "data": {}},
        headers=headers,
    )
    assert resp_ok.status_code == 204
    app.config["AUDIT_EVENT_TOKEN"] = None


def test_v1_objects_pagination_and_cache(admin_client: FlaskClient, db) -> None:
    from models import Object

    db.session.add_all([Object(name=f"obj{i}") for i in range(3)])
    db.session.commit()

    resp = admin_client.get("/api/v1/get_all_objects?limit=2")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 2
    etag = resp.headers["ETag"]
    last_mod = resp.headers["Last-Modified"]

    resp_offset = admin_client.get("/api/v1/get_all_objects?limit=2&offset=2")
    assert resp_offset.status_code == 200
    data_offset = resp_offset.get_json()
    assert len(data_offset["data"]) == 1

    resp_cache = admin_client.get(
        "/api/v1/get_all_objects?limit=2", headers={"If-None-Match": etag}
    )
    assert resp_cache.status_code == 304

    resp_cache2 = admin_client.get(
        "/api/v1/get_all_objects?limit=2", headers={"If-Modified-Since": last_mod}
    )
    assert resp_cache2.status_code == 304


def test_v1_get_all_contractors(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/api/v1/get_all_contractors")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"] == []
    assert "links" in data
    assert "ETag" in resp.headers
    assert "Last-Modified" in resp.headers

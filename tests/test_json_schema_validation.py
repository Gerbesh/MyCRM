from types import SimpleNamespace

import pytest
from flask import Flask, jsonify
from jsonschema import ValidationError

from models import Object, Request
from utils.statuses import RequestStatus
from validation import json_schema


def test_add_user_schema_allows_csrf_token(admin_client):
    resp = admin_client.post(
        "/users/add_user",
        json={
            "username": "user_csrf",
            "password": "StrongPass123",
            "role": "user",
            "csrf_token": "dummy",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data and data.get("success")


def test_add_user_schema_missing_field(admin_client):
    # Пропускаем поле role
    resp = admin_client.post(
        "/users/add_user",
        json={
            "username": "new_user",
            "password": "StrongPass123",
        },
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data and ("error" in data or "title" in data)
    details = data.get("details") or data.get("errors")
    assert isinstance(details, list) and details
    # Проверяем, что среди ошибок фигурирует отсутствие role
    paths = {d.get("path") for d in details}
    assert "$" in paths or "role" in paths  # required указывает на корень


def test_change_request_object_schema_type_error(admin_client, db):
    obj = Object(name="Объект X")
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

    # Неверный тип new_object_id (string вместо integer)
    resp = admin_client.post(
        f"/requests/process/change_request_object/{req.id}",
        json={"new_object_id": "abc"},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data and ("error" in data or "title" in data)
    details = data.get("details") or data.get("errors", [])
    assert any(d.get("validator") == "type" for d in details)


def test_change_status_schema_enum_error(admin_client, db):
    obj = Object(name="Объект Y")
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
        json={"status": "NOT_A_STATUS"},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data and ("error" in data or "title" in data)
    details = data.get("details") or data.get("errors", [])
    assert any(d.get("validator") == "enum" for d in details)


def test_change_status_schema_allows_csrf_token(admin_client, db):
    obj = Object(name="Объект Z")
    db.session.add(obj)
    db.session.commit()
    req = Request(
        object_id=obj.id,
        manufacturers="Производитель",
        status=RequestStatus.OPEN.value,
        created_by=1,
    )
    db.session.add(req)
    db.session.commit()

    resp = admin_client.post(
        f"/requests/process/change_status/{req.id}",
        json={"status": RequestStatus.ACCEPTED.value, "csrf_token": "dummy"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data and data.get("success")
    assert data.get("label")
    assert data.get("class")


def test_change_request_object_schema_allows_csrf_token(admin_client, db):
    obj1 = Object(name="Объект A")
    obj2 = Object(name="Объект B")
    db.session.add_all([obj1, obj2])
    db.session.commit()
    req = Request(
        object_id=obj1.id,
        manufacturers="Производитель",
        status=RequestStatus.OPEN.value,
        created_by=1,
    )
    db.session.add(req)
    db.session.commit()

    resp = admin_client.post(
        f"/requests/process/change_request_object/{req.id}",
        json={"new_object_id": obj2.id, "csrf_token": "dummy"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data and data.get("success")
    assert data.get("new_object_name") == obj2.name


def test_json_schemas_validator_reports_errors():
    validator = json_schema.JSONSchemasValidator(
        {
            "demo": {
                "type": "object",
                "properties": {"count": {"type": "integer"}},
                "required": ["count"],
            }
        }
    )

    errors = validator.validate("demo", {"count": "пять"})

    assert errors
    assert errors[0].validator == "type"


def test_json_schemas_validator_returns_empty_for_unknown_schema():
    validator = json_schema.JSONSchemasValidator({})

    assert validator.validate("missing", {}) == []


def test_format_errors_provides_paths():
    error = ValidationError(
        "Неверный тип",
        validator="type",
        path=("count",),
        schema_path=("properties", "count", "type"),
    )

    formatted = json_schema._format_errors([error])

    assert formatted == [
        {
            "path": "count",
            "message": "Неверный тип",
            "validator": "type",
            "schema_path": "properties/count/type",
        }
    ]


@pytest.mark.usefixtures("app")
def test_init_json_validation_returns_error(monkeypatch):
    app = Flask("json-validation-test")
    app.testing = True

    error = ValidationError(
        "Ошибка поля",
        validator="type",
        path=("value",),
        schema_path=("properties", "value", "type"),
    )

    class DummyValidator:
        def validate(self, schema_key, data):  # noqa: D401, ANN001
            assert schema_key == "demo_schema"
            assert data == {"value": "abc"}
            return [error]

    monkeypatch.setattr(json_schema, "_validator", DummyValidator(), raising=False)
    monkeypatch.setitem(
        json_schema.ENDPOINT_SCHEMAS,
        ("validate_payload", "POST"),
        "demo_schema",
    )
    monkeypatch.setattr(
        json_schema,
        "current_user",
        SimpleNamespace(is_authenticated=True),
        raising=False,
    )

    json_schema.init_json_validation(app)

    @app.route("/validate", methods=["POST"])
    def validate_payload():  # noqa: D401
        return jsonify({"ok": True})

    with app.test_client() as client:
        resp = client.post("/validate", json={"value": "abc"})

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["error"] == "Ошибка валидации JSON"
    assert payload["details"][0]["path"] == "value"


def test_init_json_validation_skips_without_json(monkeypatch):
    app = Flask("json-validation-empty")
    app.testing = True

    class DummyValidator:
        def validate(self, schema_key, data):  # noqa: D401, ANN001
            raise AssertionError("валидатор не должен вызываться")

    monkeypatch.setattr(json_schema, "_validator", DummyValidator(), raising=False)
    monkeypatch.setitem(
        json_schema.ENDPOINT_SCHEMAS,
        ("validate_payload", "POST"),
        "demo_schema",
    )
    monkeypatch.setattr(
        json_schema,
        "current_user",
        SimpleNamespace(is_authenticated=True),
        raising=False,
    )

    json_schema.init_json_validation(app)

    @app.route("/validate", methods=["POST"])
    def validate_payload():  # noqa: D401
        return jsonify({"ok": True})

    with app.test_client() as client:
        resp = client.post("/validate")

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

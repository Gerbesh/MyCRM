from datetime import datetime, timedelta, timezone

import pytest

from models import Contractor, Object, Request
from routes import request_crud_routes
from utils.statuses import RequestStatus


def _create_request(db, owner_id):
    obj = Object(name="Тестовый объект")
    contractor = Contractor(name="Подрядчик 1")
    db.session.add_all([obj, contractor])
    db.session.commit()

    req = Request(
        object_id=obj.id,
        manufacturers="Производитель",
        created_by=owner_id,
        status=RequestStatus.OPEN.value,
    )
    req.contractors.append(contractor)
    db.session.add(req)
    db.session.commit()
    return req


@pytest.mark.usefixtures("admin_user")
def test_admin_updates_request_date(admin_client, db, admin_user, monkeypatch):
    offset = timezone(timedelta(hours=3))
    monkeypatch.setattr(request_crud_routes, "_get_local_timezone", lambda: offset)

    req = _create_request(db, admin_user.id)
    new_value = "2025-09-16T12:34"

    response = admin_client.post(
        f"/requests/crud/view_request/{req.id}",
        data={"created_at": new_value},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["created_at_form_value"] == new_value
    assert data["created_at_display"] == "16.09.2025 12:34"
    assert data["timezone_abbr"]

    db.session.refresh(req)
    assert req.created_at == datetime(2025, 9, 16, 9, 34)


def test_get_local_timezone_returns_tzinfo():
    tz = request_crud_routes._get_local_timezone()
    assert tz is None or request_crud_routes.datetime.now(timezone.utc).astimezone(tz).tzinfo is not None


@pytest.mark.usefixtures("admin_user")
def test_user_cannot_update_request_date(user_client, db, admin_user):
    req = _create_request(db, admin_user.id)
    original_created_at = req.created_at

    response = user_client.post(
        f"/requests/crud/view_request/{req.id}",
        data={"created_at": "2025-09-16T12:34"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "Доступ" in data["error"]

    db.session.refresh(req)
    assert req.created_at == original_created_at

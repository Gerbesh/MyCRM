from types import SimpleNamespace

import pytest

from models import Contractor
from utils import request_helpers


class BrokenRelation:
    def __iter__(self):
        raise RuntimeError("некорректный итератор")


@pytest.fixture()
def contractors(db):
    items = []
    for idx in range(1, 4):
        contractor = Contractor(name=f"Подрядчик {idx}")
        db.session.add(contractor)
        items.append(contractor)
    db.session.commit()
    return items


def test_get_request_contractor_prefers_relationship(app):
    request = SimpleNamespace(contractors=("a", "b"))

    with app.app_context():
        result = request_helpers.get_request_contractor(request)

    assert result == ["a", "b"]


def test_get_request_contractor_fallback_to_string_ids(app, contractors):
    request = SimpleNamespace(
        contractors=BrokenRelation(),
        contractor_ids="1, 2,abc, 3",
        contractor_id=None,
    )

    with app.app_context():
        result = request_helpers.get_request_contractor(request)

    assert {c.id for c in result} == {c.id for c in contractors}


def test_get_request_contractor_uses_single_id(app, contractors):
    request = SimpleNamespace(
        contractors=None, contractor_ids=None, contractor_id=contractors[0].id
    )

    with app.app_context():
        result = request_helpers.get_request_contractor(request)

    assert [c.id for c in result] == [contractors[0].id]

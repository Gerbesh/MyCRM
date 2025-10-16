"""Request helpers."""

from typing import TYPE_CHECKING, List

from flask import has_app_context

if TYPE_CHECKING:
    from models import Contractor, Request


def get_request_contractor(req: "Request") -> List["Contractor"]:
    """Return contractors for a request (prefers M2M relationship).

    Falls back to parsing legacy string field `contractor_ids`.
    """
    # Предпочитаем relationship
    rel = getattr(req, "contractors", None)
    if rel is not None:
        try:
            return list(rel)
        except Exception:
            pass

    # Резервный путь: разбор старого формата
    from database import db
    from models import Contractor

    ids: List[int] = []
    raw = getattr(req, "contractor_ids", None)
    if raw:
        parts = raw.split(",") if isinstance(raw, str) else raw
        for part in parts:
            p = str(part).strip()
            if p.isdigit():
                ids.append(int(p))

    if not ids and getattr(req, "contractor_id", None):
        ids = [req.contractor_id]

    if not ids:
        return []

    def _query(cid_list):
        return db.session.query(Contractor).filter(Contractor.id.in_(cid_list)).all()

    if has_app_context():
        return _query(ids)

    from app import app

    with app.app_context():
        return _query(ids)

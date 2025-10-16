"""Маршруты API версии v1"""

import hashlib
import hmac
import os
import time
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request, url_for
from flask_login import login_required, login_user
from werkzeug.security import check_password_hash

from models import Contractor, Object, Request, User
from utils.cache import prepare_cache
from utils.request_helpers import get_request_contractor

api_v1_bp = Blueprint("api_v1", __name__)


def _check_hmac(secret: str, ts: str, body: bytes, sign: str, ttl: int) -> bool:
    if not ts or not sign:
        return False
    try:
        if abs(time.time() - int(ts)) > ttl:
            return False
    except ValueError:
        return False
    mac = hmac.new(
        secret.encode(), ts.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(mac, sign)


# Removed in public repo
# @api_v1_bp.route("/deploy/check", methods=["POST"])
def deploy_check():
    """Проверяет, какие файлы отличаются на сервере."""
    data = request.get_json(silent=True) or {}
    login = data.get("login")
    password = data.get("password")
    key = data.get("key")
    files = data.get("files") or []
    user = User.query.filter_by(username=login).first()
    key_hash = current_app.config.get("DEPLOY_KEY_HASH")
    allow_legacy = current_app.config.get("ALLOW_LEGACY_DEPLOYKEY", True)
    secret = current_app.config.get("DEPLOY_HMAC_SECRET", "")
    ttl = int(current_app.config.get("DEPLOY_HMAC_TTL", 300))
    ts = request.headers.get("X-Ts", "")
    sign = request.headers.get("X-Sign", "")
    body_raw = request.get_data() or b""

    user_ok = bool(user and password and check_password_hash(user.password, password))
    hmac_ok = bool(secret) and _check_hmac(secret, ts, body_raw, sign, ttl)
    legacy_ok = allow_legacy and key_hash and key and check_password_hash(key_hash, key)
    if not (user_ok and (hmac_ok or legacy_ok)):
        return jsonify({"changed": []}), 401
    if legacy_ok and not hmac_ok:
        current_app.logger.warning("deploy_check: legacy key used (deprecated)")

    login_user(user)

    # В конфиге ключ может существовать со значением None. Корректно подстрахуемся.
    base_dir = current_app.config.get("DEPLOY_ROOT") or current_app.root_path
    changed: list[str] = []
    for f in files:
        path = f.get("path")
        md5_client = f.get("md5")
        if not path or not md5_client:
            continue
        try:
            full_path = os.path.join(base_dir, path)
            # Если файла нет или это не обычный файл — считаем изменённым
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                changed.append(path)
                continue
            h = hashlib.md5()
            with open(full_path, "rb") as fp:
                for chunk in iter(lambda: fp.read(8192), b""):
                    h.update(chunk)
            if h.hexdigest() != md5_client:
                changed.append(path)
        except Exception as e:
            # Никогда не падаем 500 из-за одного проблемного файла:
            # помечаем его как изменённый и продолжаем проверку
            current_app.logger.warning(
                "deploy_check: error reading %s: %s", full_path, e
            )
            changed.append(path)

    return jsonify({"changed": changed})


@api_v1_bp.route("/get_all_objects", methods=["GET"])
@login_required
def get_all_objects():
    """API для получения всех объектов с полной информацией для автокомплита"""
    try:
        limit = min(request.args.get("limit", 50, type=int), 100)
        offset = request.args.get("offset", 0, type=int)
        objects = Object.query.order_by(Object.id).offset(offset).limit(limit).all()
        objects_data = []
        for obj in objects:
            objects_data.append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "address": obj.address if hasattr(obj, "address") else None,
                    "customer": obj.customer if hasattr(obj, "customer") else None,
                    "links": {
                        "self": url_for(
                            "api_v1.api_requests_by_object",
                            object_id=obj.id,
                            _external=True,
                        ),
                        "next": None,
                        "related": url_for(
                            "api_v1.get_all_contractors", _external=True
                        ),
                    },
                }
            )

        last_modified = max(
            (obj.created_at for obj in objects), default=datetime.utcnow()
        )
        cache_result = prepare_cache(objects_data, last_modified)
        if isinstance(cache_result, Response):
            return cache_result
        etag, last_mod = cache_result

        response = {
            "data": objects_data,
            "links": {
                "self": url_for(
                    "api_v1.get_all_objects",
                    limit=limit,
                    offset=offset,
                    _external=True,
                ),
                "next": (
                    url_for(
                        "api_v1.get_all_objects",
                        limit=limit,
                        offset=offset + limit,
                        _external=True,
                    )
                    if len(objects) == limit
                    else None
                ),
                "related": url_for("api_v1.get_all_contractors", _external=True),
            },
        }
        resp = jsonify(response)
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_mod
        return resp
    except Exception as e:
        current_app.logger.error(f"Error in get_all_objects: {str(e)}")
        return (
            jsonify(
                {
                    "data": [],
                    "links": {
                        "self": url_for("api_v1.get_all_objects", _external=True)
                    },
                }
            ),
            500,
        )


@api_v1_bp.route("/get_all_contractors", methods=["GET"])
@login_required
def get_all_contractors():
    """API для получения всех подрядчиков"""
    try:
        limit = min(request.args.get("limit", 50, type=int), 100)
        offset = request.args.get("offset", 0, type=int)
        contractors = (
            Contractor.query.order_by(Contractor.id).offset(offset).limit(limit).all()
        )
        contractors_data = []
        for cont in contractors:
            contractors_data.append(
                {
                    "id": cont.id,
                    "name": cont.name,
                    "links": {
                        "self": url_for(
                            "api_v1.api_requests_by_contractor",
                            contractor_id=cont.id,
                            _external=True,
                        ),
                        "next": None,
                        "related": url_for("api_v1.get_all_objects", _external=True),
                    },
                }
            )

        last_modified = max(
            (cont.created_at for cont in contractors), default=datetime.utcnow()
        )
        cache_result = prepare_cache(contractors_data, last_modified)
        if isinstance(cache_result, Response):
            return cache_result
        etag, last_mod = cache_result

        response = {
            "data": contractors_data,
            "links": {
                "self": url_for(
                    "api_v1.get_all_contractors",
                    limit=limit,
                    offset=offset,
                    _external=True,
                ),
                "next": (
                    url_for(
                        "api_v1.get_all_contractors",
                        limit=limit,
                        offset=offset + limit,
                        _external=True,
                    )
                    if len(contractors) == limit
                    else None
                ),
                "related": url_for("api_v1.get_all_objects", _external=True),
            },
        }
        resp = jsonify(response)
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_mod
        return resp
    except Exception as e:
        current_app.logger.error(f"Error in get_all_contractors: {str(e)}")
        return (
            jsonify(
                {
                    "data": [],
                    "links": {
                        "self": url_for("api_v1.get_all_contractors", _external=True)
                    },
                }
            ),
            500,
        )


@api_v1_bp.route("/requests/by_contractor/<int:contractor_id>", methods=["GET"])
@login_required
def api_requests_by_contractor(contractor_id):
    """Заявки по подрядчику (для API)"""
    try:
        Contractor.query.get_or_404(contractor_id)
        from models import request_contractor

        limit = min(request.args.get("limit", 50, type=int), 100)
        offset = request.args.get("offset", 0, type=int)
        requests_query = (
            Request.query.join(
                request_contractor, request_contractor.c.request_id == Request.id
            )
            .filter(request_contractor.c.contractor_id == contractor_id)
            .order_by(Request.id.desc())
        )
        requests = requests_query.offset(offset).limit(limit).all()

        result = []
        for req in requests:
            contractors = get_request_contractor(req)
            result.append(
                {
                    "id": req.id,
                    "status": req.status,
                    "created_at": req.created_at.isoformat(),
                    "manufacturers": req.manufacturers_list,
                    "contractors": [{"id": c.id, "name": c.name} for c in contractors],
                    "links": {
                        "self": url_for(
                            "request_crud.view_request", id=req.id, _external=True
                        ),
                        "next": None,
                        "related": url_for(
                            "api_v1.api_requests_by_object",
                            object_id=req.object_id,
                            _external=True,
                        ),
                    },
                }
            )

        last_modified = max(
            (req.created_at for req in requests), default=datetime.utcnow()
        )
        cache_result = prepare_cache(result, last_modified)
        if isinstance(cache_result, Response):
            return cache_result
        etag, last_mod = cache_result

        response = {
            "data": result,
            "links": {
                "self": url_for(
                    "api_v1.api_requests_by_contractor",
                    contractor_id=contractor_id,
                    limit=limit,
                    offset=offset,
                    _external=True,
                ),
                "next": (
                    url_for(
                        "api_v1.api_requests_by_contractor",
                        contractor_id=contractor_id,
                        limit=limit,
                        offset=offset + limit,
                        _external=True,
                    )
                    if len(requests) == limit
                    else None
                ),
                "related": url_for("api_v1.get_all_contractors", _external=True),
            },
        }
        resp = jsonify(response)
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_mod
        return resp
    except Exception as e:
        current_app.logger.error(
            (
                f"Error in api_requests_by_contractor for contractor {contractor_id}: "
                f"{str(e)}"
            )
        )
        return (
            jsonify(
                {
                    "data": [],
                    "links": {
                        "self": url_for(
                            "api_v1.api_requests_by_contractor",
                            contractor_id=contractor_id,
                            _external=True,
                        )
                    },
                }
            ),
            500,
        )


@api_v1_bp.route("/requests/by_object/<int:object_id>", methods=["GET"])
@login_required
def api_requests_by_object(object_id):
    """Заявки по объекту (для API)"""
    try:
        Object.query.get_or_404(object_id)
        limit = min(request.args.get("limit", 50, type=int), 100)
        offset = request.args.get("offset", 0, type=int)
        requests_query = Request.query.filter_by(object_id=object_id).order_by(
            Request.id.desc()
        )
        requests = requests_query.offset(offset).limit(limit).all()

        result = []
        for req in requests:
            contractors = get_request_contractor(req)
            result.append(
                {
                    "id": req.id,
                    "status": req.status,
                    "created_at": req.created_at.isoformat(),
                    "manufacturers": req.manufacturers_list,
                    "contractors": [{"id": c.id, "name": c.name} for c in contractors],
                    "links": {
                        "self": url_for(
                            "request_crud.view_request", id=req.id, _external=True
                        ),
                        "next": None,
                        "related": (
                            url_for(
                                "api_v1.api_requests_by_contractor",
                                contractor_id=contractors[0].id,
                                _external=True,
                            )
                            if contractors
                            else None
                        ),
                    },
                }
            )

        last_modified = max(
            (req.created_at for req in requests), default=datetime.utcnow()
        )
        cache_result = prepare_cache(result, last_modified)
        if isinstance(cache_result, Response):
            return cache_result
        etag, last_mod = cache_result

        response = {
            "data": result,
            "links": {
                "self": url_for(
                    "api_v1.api_requests_by_object",
                    object_id=object_id,
                    limit=limit,
                    offset=offset,
                    _external=True,
                ),
                "next": (
                    url_for(
                        "api_v1.api_requests_by_object",
                        object_id=object_id,
                        limit=limit,
                        offset=offset + limit,
                        _external=True,
                    )
                    if len(requests) == limit
                    else None
                ),
                "related": url_for("api_v1.get_all_objects", _external=True),
            },
        }
        resp = jsonify(response)
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_mod
        return resp
    except Exception as e:
        current_app.logger.error(
            f"Error in api_requests_by_object for object {object_id}: {str(e)}"
        )
        return (
            jsonify(
                {
                    "data": [],
                    "links": {
                        "self": url_for(
                            "api_v1.api_requests_by_object",
                            object_id=object_id,
                            _external=True,
                        )
                    },
                }
            ),
            500,
        )

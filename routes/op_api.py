"""API для модуля OP."""

from __future__ import annotations

import logging
import mimetypes
import os
import time
import uuid
from typing import Any

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from flask_login import current_user, login_required
from werkzeug.utils import safe_join, secure_filename

from models import Object, OpComment, OpFile, OpKPCategory, Request, User, db
from security_utils import safe_log
from utils.constants import MANUFACTURERS
from utils.request_helpers import get_request_contractor

op_api_bp = Blueprint("op_api", __name__)

MAX_FILE_SIZE = 300 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
CACHE_TTL = 45  # секунды
_GROUPS_CACHE: dict[tuple[int, tuple[str, ...]], tuple[float, list[Any]]] = {}
MANUFACTURER_SIDES: dict[str, str | None] = {
    m: ("OV" if "ОВ" in m.upper() else "VK" if "ВК" in m.upper() else None)
    for m in MANUFACTURERS
}


def _check_role(allow_demo: bool = False) -> None:
    if allow_demo and getattr(current_user, "role", None) == "demo":
        return
    allowed_roles = {"admin", "manager"}
    if current_user.role not in allowed_roles:
        abort(403)


def _upload_dir() -> str:
    path = current_app.config.get(
        "OP_UPLOAD_DIR", os.path.join(current_app.root_path, "uploads", "op")
    )
    os.makedirs(path, exist_ok=True)
    return path


@op_api_bp.route("/api/op/<int:object_id>/groups")
@login_required
def op_groups(object_id: int):
    """Группировка заявок по производителям из шага 3 создания заявки.

    Возвращает список элементов вида {id, name, count}, где id=name=название
    производителя, а count — количество заявок по этому производителю на объекте.
    Поддерживается фильтрация по статусам и сторонам ОВ/ВК.
    """
    _check_role(allow_demo=True)

    # Поддержка множественных статусов в виде ?status=A,B или ?status=A&status=B
    raw_statuses = request.args.getlist("status")
    statuses: list[str] = []
    for rs in raw_statuses:
        statuses.extend([s.strip() for s in rs.split(",") if s.strip()])
    statuses_t = tuple(statuses)

    # Фильтр по сторонам (OV/VK) в формате ?side=OV или ?side=OV,VK
    raw_sides = request.args.getlist("side")
    sides: list[str] = []
    for rs in raw_sides:
        sides.extend([s.strip().upper() for s in rs.split(",") if s.strip()])
    sides_t = tuple(sides)

    cache_key = (object_id, statuses_t, sides_t)
    now = time.time()
    cached = _GROUPS_CACHE.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL:
        return jsonify(cached[1])

    # Собираем все заявки по объекту и считаем по производителям
    q = db.session.query(Request.manufacturers).filter(Request.object_id == object_id)
    if statuses_t:
        q = q.filter(Request.status.in_(statuses_t))

    counts: dict[str, int] = {}
    for (manufacturers_str,) in q.all():
        if not manufacturers_str:
            continue
        for raw in manufacturers_str.split(","):
            name = (raw or "").strip()
            if not name or name not in MANUFACTURERS:
                continue
            m_side = MANUFACTURER_SIDES.get(name)
            if sides_t and m_side and m_side not in sides_t:
                continue
            counts[name] = counts.get(name, 0) + 1

    # Формируем полный список: все производители из шага 3, даже если 0 заявок
    groups: list[dict[str, Any]] = []
    for m_name in sorted(MANUFACTURERS, key=lambda x: x.lower()):
        m_side = MANUFACTURER_SIDES.get(m_name)
        if sides_t and m_side and m_side not in sides_t:
            continue
        cnt = counts.get(m_name, 0)
        groups.append({"id": m_name, "name": m_name, "count": cnt})

    _GROUPS_CACHE[cache_key] = (now, groups)
    return jsonify(groups)


@op_api_bp.route("/api/op/<int:object_id>/requests")
@login_required
def op_requests(object_id: int):
    """Список заявок по объекту с учётом фильтров, используемых в OP."""
    _check_role(allow_demo=True)
    Object.query.get_or_404(object_id)

    raw_statuses = request.args.getlist("status")
    statuses: list[str] = []
    for rs in raw_statuses:
        statuses.extend([s.strip() for s in rs.split(",") if s.strip()])

    raw_sides = request.args.getlist("side")
    sides: list[str] = []
    for rs in raw_sides:
        sides.extend([s.strip().upper() for s in rs.split(",") if s.strip()])
    sides_set = {s for s in sides if s}

    manufacturer = (request.args.get("manufacturer") or "").strip()

    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(limit, 200))

    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    query = Request.query.filter(Request.object_id == object_id)
    if statuses:
        query = query.filter(Request.status.in_(tuple(statuses)))
    if manufacturer:
        query = query.filter(Request.manufacturers.contains(manufacturer))

    requests = query.order_by(Request.id.desc()).all()

    result: list[dict[str, Any]] = []
    for req in requests:
        manufacturers_list = [
            item.strip() for item in req.manufacturers_list if item.strip()
        ]
        if manufacturer and manufacturer not in manufacturers_list:
            continue
        if sides_set:
            if not any(
                MANUFACTURER_SIDES.get(item) in sides_set
                for item in manufacturers_list
                if item in MANUFACTURERS
            ):
                continue
        contractors = get_request_contractor(req)
        result.append(
            {
                "id": req.id,
                "status": req.status,
                "created_at": req.created_at.isoformat(),
                "manufacturers": manufacturers_list,
                "contractors": [
                    {"id": c.id, "name": c.name} for c in (contractors or [])
                ],
            }
        )

    paginated = result[offset : offset + limit]
    has_more = len(result) > offset + limit
    return jsonify({"data": paginated, "has_more": has_more})


@op_api_bp.route("/api/op/<int:object_id>/comments")
@login_required
def op_comments(object_id: int):
    """Получение списка комментариев."""
    _check_role(allow_demo=True)
    comments = (
        OpComment.query.filter_by(object_id=object_id)
        .order_by(OpComment.created_at)
        .all()
    )
    data = []
    for c in comments:
        user = User.query.get(c.user_id)
        comment_data = {
            "id": c.id,
            "content": c.content,
            "username": user.username if user else "",
            "created_at": c.created_at.strftime("%d.%m.%Y %H:%M"),
            "user_id": c.user_id,
            "can_delete": current_user.role == "admin" or c.user_id == current_user.id,
            "remaining_time": 0,
        }
        rendered = render_template(
            "_comment_item.html", comment=comment_data, current_user=current_user
        )
        comment_data["rendered_html"] = rendered
        data.append(comment_data)
    return jsonify(data)


@op_api_bp.route("/api/op/<int:object_id>/comments", methods=["POST"])
@login_required
def op_comment_add(object_id: int):
    """Добавление комментария."""
    _check_role()
    content = request.form.get("content") or (request.get_json(silent=True) or {}).get(
        "content"
    )
    if not content:
        return jsonify({"error": "Пустой комментарий"}), 400
    comment = OpComment(object_id=object_id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} добавил комментарий {comment.id}",
    )
    user = User.query.get(current_user.id)
    comment_data = {
        "id": comment.id,
        "content": comment.content,
        "username": user.username if user else "",
        "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
        "user_id": current_user.id,
        "can_delete": True,
        "remaining_time": 0,
    }
    rendered = render_template(
        "_comment_item.html", comment=comment_data, current_user=current_user
    )
    comment_data["rendered_html"] = rendered
    return jsonify(comment_data), 201


@op_api_bp.route("/api/op/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def op_comment_delete(comment_id: int):
    """Удаление комментария OP (админ или автор)."""
    _check_role()
    comment = OpComment.query.get_or_404(comment_id)
    if current_user.role != "admin" and comment.user_id != current_user.id:
        return jsonify({"error": "Нет прав на удаление"}), 403
    db.session.delete(comment)
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} удалил комментарий {comment_id}",
    )
    return jsonify({"success": True})


@op_api_bp.route("/api/op/<int:object_id>/files")
@login_required
def op_files(object_id: int):
    """Список файлов объекта."""
    _check_role(allow_demo=True)
    files = (
        OpFile.query.filter_by(object_id=object_id)
        .order_by(OpFile.uploaded_at.desc())
        .all()
    )
    data = [
        {
            "id": f.id,
            "original_name": f.original_name,
            "content_type": f.content_type,
            "size": f.size,
        }
        for f in files
    ]
    return jsonify(data)


@op_api_bp.route("/api/op/<int:object_id>/files", methods=["POST"])
@login_required
def op_file_upload(object_id: int):
    """Загрузка файла."""
    _check_role()
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Файл не передан"}), 400
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    mime = file.mimetype or mimetypes.guess_type(filename)[0]
    if ext not in ALLOWED_EXTENSIONS or ALLOWED_EXTENSIONS[ext] != mime:
        return jsonify({"error": "Недопустимый тип файла"}), 400
    unique = f"{uuid.uuid4().hex}_{filename}"
    dest = os.path.join(_upload_dir(), unique)
    size = 0
    try:
        with open(dest, "wb") as f:
            for chunk in iter(lambda: file.stream.read(64 * 1024), b""):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise ValueError("Файл слишком большой")
                f.write(chunk)
    except ValueError:
        try:
            os.remove(dest)
        except OSError:
            pass
        return jsonify({"error": "Файл слишком большой"}), 400
    op_file = OpFile(
        object_id=object_id,
        user_id=current_user.id,
        filename=unique,
        original_name=file.filename,
        content_type=mime,
        size=size,
    )
    db.session.add(op_file)
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} загрузил файл {op_file.id}",
    )
    return jsonify({"id": op_file.id}), 201


@op_api_bp.route("/api/op/files/<int:file_id>", methods=["DELETE"])
@login_required
def op_file_delete(file_id: int):
    """Удаление файла."""
    _check_role()
    op_file = OpFile.query.get_or_404(file_id)
    path = os.path.join(_upload_dir(), op_file.filename)
    try:
        os.remove(path)
    except OSError:
        pass
    db.session.delete(op_file)
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} удалил файл {file_id}",
    )
    return jsonify({"success": True})


@op_api_bp.route("/op/files/<int:file_id>/download")
@login_required
def op_file_download(file_id: int):
    """Скачивание файла."""
    _check_role(allow_demo=True)
    op_file = OpFile.query.get_or_404(file_id)
    directory = _upload_dir()
    safe_path = safe_join(directory, op_file.filename)
    if not safe_path or not os.path.isfile(safe_path):
        abort(404)
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} скачал файл {file_id}",
    )
    return send_from_directory(
        directory,
        op_file.filename,
        as_attachment=True,
        download_name=op_file.original_name,
        mimetype=op_file.content_type,
    )


@op_api_bp.route("/api/op/<int:object_id>/kp")
@login_required
def op_kp_get(object_id: int):
    """Категории КП объекта."""
    _check_role(allow_demo=True)
    cats = OpKPCategory.for_object(object_id, current_user.id)
    data = [
        {
            "id": c.id,
            "side": c.side,
            "name": c.name,
            "is_extra": c.is_extra,
            "position": c.position,
            "invoice_number": c.invoice_number,
        }
        for c in cats
    ]
    return jsonify(data)


@op_api_bp.route("/api/op/<int:object_id>/kp", methods=["POST"])
@login_required
def op_kp_add(object_id: int):
    """Создание категории КП."""
    _check_role()
    payload = request.get_json(silent=True) or {}
    side = payload.get("side")
    name = payload.get("name")
    if not side or not name:
        return jsonify({"error": "Неверные данные"}), 400
    # Определяем позицию: добавляем в конец списка для данной стороны
    if "position" in payload and isinstance(payload.get("position"), int):
        position = int(payload["position"])  # доверяем явному запросу
    else:
        max_pos = (
            db.session.query(db.func.max(OpKPCategory.position))
            .filter(OpKPCategory.object_id == object_id, OpKPCategory.side == side)
            .scalar()
            or 0
        )
        position = int(max_pos) + 1

    category = OpKPCategory(
        object_id=object_id,
        user_id=current_user.id,
        side=side,
        name=name,
        is_extra=payload.get("is_extra", False),
        position=position,
        invoice_number=payload.get("invoice_number"),
    )
    db.session.add(category)
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} создал категорию {category.id}",
    )
    return jsonify({"id": category.id}), 201


@op_api_bp.route("/api/op/kp/<int:cat_id>", methods=["PUT"])
@login_required
def op_kp_update(cat_id: int):
    """Обновление категории КП."""
    _check_role()
    category = OpKPCategory.query.get_or_404(cat_id)
    payload = request.get_json(silent=True) or {}
    for field in ("name", "invoice_number", "position", "is_extra", "side"):
        if field in payload:
            setattr(category, field, payload[field])
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} обновил категорию {cat_id}",
    )
    return jsonify({"success": True})


@op_api_bp.route("/api/op/kp/<int:cat_id>", methods=["PATCH"])
@login_required
def op_kp_patch(cat_id: int):
    """зменение позиции категории КП."""
    _check_role()
    category = OpKPCategory.query.get_or_404(cat_id)
    payload = request.get_json(silent=True) or {}
    position = payload.get("position")
    if not isinstance(position, int):
        return jsonify({"error": "Неверные данные"}), 400
    category.position = position
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} изменил позицию категории {cat_id}",
    )
    return jsonify({"success": True})


@op_api_bp.route("/api/op/kp/<int:cat_id>", methods=["DELETE"])
@login_required
def op_kp_delete(cat_id: int):
    """Удаление категории КП."""
    _check_role()
    category = OpKPCategory.query.get_or_404(cat_id)
    db.session.delete(category)
    db.session.commit()
    safe_log(
        current_app.logger,
        logging.INFO,
        f"[OP] Пользователь {current_user.username} удалил категорию {cat_id}",
    )
    return jsonify({"success": True})

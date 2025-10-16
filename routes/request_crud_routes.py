"""
CRUD операции для заявок (создание, просмотр, удаление)
"""

import logging
import os
import shutil
from datetime import datetime, timezone, tzinfo

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from extensions import limiter
from models import Attachment, Comment, Contractor, Object, Request, User, db
from security_utils import safe_log
from utils.constants import MANUFACTURERS
from utils.request_helpers import get_request_contractor
from utils.statuses import RequestStatus

request_crud_bp = Blueprint("request_crud", __name__)


def _get_local_timezone() -> tzinfo | None:
    """Возвращает часовую зону сервера."""
    return datetime.now().astimezone().tzinfo


def _format_request_created_at(value: datetime | None) -> dict[str, str]:
    """Подготовить строки для отображения и формы."""
    if not value:
        return {"display": "—", "form_value": ""}
    stored = value
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    else:
        stored = stored.astimezone(timezone.utc)
    local_tz = _get_local_timezone()
    if local_tz is not None:
        local_value = stored.astimezone(local_tz)
    else:
        local_value = stored
    return {
        "display": local_value.strftime("%d.%m.%Y %H:%M"),
        "form_value": local_value.strftime("%Y-%m-%dT%H:%M"),
    }


def _get_timezone_info() -> dict[str, str]:
    """Возвращает данные о текущей часовой зоне сервера."""
    local_tz = _get_local_timezone()
    if local_tz is not None:
        now_local = datetime.now(timezone.utc).astimezone(local_tz)
    else:
        now_local = datetime.now().astimezone()
        local_tz = now_local.tzinfo
    tzinfo_obj = now_local.tzinfo or local_tz
    offset = now_local.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset else 0
    sign = "+" if total_minutes >= 0 else "-"
    hours_abs, minutes_abs = divmod(abs(total_minutes), 60)
    offset_label = f"UTC{sign}{hours_abs:02d}:{minutes_abs:02d}"
    abbr = now_local.tzname() or offset_label
    tz_name = getattr(tzinfo_obj, "key", None) or getattr(tzinfo_obj, "zone", None)
    if not tz_name and tzinfo_obj is not None:
        tz_name = str(tzinfo_obj)
    title = (
        f"Текущая часовая зона: {tz_name} ({offset_label})"
        if tz_name
        else f"Текущая часовая зона: {offset_label}"
    )
    hint = (
        "Дата и время сохраняются в UTC и отображаются с учётом "
        f"локального смещения сервера ({offset_label})."
    )
    return {"abbr": abbr, "title": title, "hint": hint}


@request_crud_bp.route("/requests")
@login_required
def requests_list():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    query = Request.query
    for key, value in request.args.items():
        if key.startswith("filter_") and value:
            field = key[len("filter_") :]
            if hasattr(Request, field):
                query = query.filter(getattr(Request, field) == value)

    sort_columns = {
        "id": Request.id,
        "created_at": Request.created_at,
        "status": Request.status,
    }
    sort_col = sort_columns.get(sort, Request.created_at)
    sort_col = sort_col.desc() if order == "desc" else sort_col.asc()

    pagination = query.order_by(sort_col).paginate(
        page=page, per_page=per_page, error_out=False
    )
    data = [
        {
            "id": r.id,
            "status": r.status,
            "object_id": r.object_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in pagination.items
    ]
    return jsonify({"data": data, "total": pagination.total})


def _parse_contractor_ids(raw) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = str(raw).split(",")
    out = []
    for p in parts:
        p = str(p).strip()
        if p.isdigit():
            out.append(int(p))
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq


@request_crud_bp.route("/create_request", methods=["GET", "POST"])
@login_required
@limiter.limit("10/minute", methods=["POST"])
def create_request():
    """Создание новой заявки"""
    try:
        current_app.logger.debug(
            f"Accessing create_request route by user {current_user.username}"
        )
        if request.method == "POST":
            if current_user.role == "demo":
                message = "В демо-режиме отправка заявок недоступна."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                    return jsonify({"error": message, "demo_mode": True}), 403
                flash(message, "warning")
                return (
                    render_template("create_request.html", manufacturers=MANUFACTURERS),
                    403,
                )

            object_id = request.form.get("object_id", "").strip()
            contractor_ids_raw = request.form.getlist("contractor_ids[]")
            manufacturers = request.form.getlist("manufacturers[]")
            request_comment = request.form.get("request_comment", "").strip()

            if not object_id:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": "Выберите объект"}), 400
                flash("Выберите объект", "danger")
                return render_template(
                    "create_request.html", manufacturers=MANUFACTURERS
                )

            if not object_id.isdigit():
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": "Недопустимый идентификатор объекта"}), 400
                flash("Недопустимый идентификатор объекта", "danger")
                return render_template(
                    "create_request.html", manufacturers=MANUFACTURERS
                )

            contractor_ids = _parse_contractor_ids(contractor_ids_raw)
            if not contractor_ids:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": "Выберите хотя бы одного подрядчика"}), 400
                flash("Выберите хотя бы одного подрядчика", "danger")
                return render_template(
                    "create_request.html", manufacturers=MANUFACTURERS
                )

            if not manufacturers:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return (
                        jsonify({"error": "Выберите хотя бы одного производителя"}),
                        400,
                    )
                flash("Выберите хотя бы одного производителя", "danger")
                return render_template(
                    "create_request.html", manufacturers=MANUFACTURERS
                )

            created_requests = []

            # Загружаем файлы один раз, чтобы избежать ошибок потока
            # при множественных подрядчиках
            raw_files = request.files.getlist("files[]")
            prepared_files = []
            if raw_files:
                for file in raw_files:
                    if not file or not file.filename:
                        continue
                    file.stream.seek(0)
                    file_data = file.read()
                    size = len(file_data)
                    if size > 50 * 1024 * 1024:
                        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                            flash(
                                (
                                    f"Файл {file.filename} превышает максимальный "
                                    "размер 50MB"
                                ),
                                "danger",
                            )
                        continue
                    filename = secure_filename(file.filename)
                    prepared_files.append((filename, file_data))

            try:
                for cid in contractor_ids:
                    new_request = Request(
                        object_id=int(object_id),
                        manufacturers=",".join(manufacturers),
                        created_by=current_user.id,
                        status=RequestStatus.OPEN.value,
                    )
                    new_request.contractor_id = cid
                    db.session.add(new_request)
                    db.session.flush()

                    saved_files = []
                    if prepared_files:
                        upload_dir = os.path.join(
                            current_app.config["UPLOAD_FOLDER"], str(new_request.id)
                        )
                        os.makedirs(upload_dir, exist_ok=True)

                        for filename, file_data in prepared_files:
                            unique_filename = (
                                f"{new_request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                                f"{filename}"
                            )
                            filepath = os.path.join(upload_dir, unique_filename)
                            with open(filepath, "wb") as f:
                                f.write(file_data)
                            saved_files.append(
                                f"uploads/{new_request.id}/{unique_filename}"
                            )

                        if saved_files:
                            new_request.file_path = ",".join(saved_files)

                    if request_comment:
                        new_comment = Comment(
                            request_id=new_request.id,
                            user_id=current_user.id,
                            content=request_comment,
                        )
                        db.session.add(new_comment)

                    created_requests.append(new_request)

                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("Ошибка при создании заявок")
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": "Ошибка при создании заявок"}), 500
                flash("Ошибка при создании заявок", "danger")
                return render_template(
                    "create_request.html", manufacturers=MANUFACTURERS
                )

            current_app.logger.info(
                (
                    f"Создано заявок: {len(created_requests)} пользователем "
                    f"{current_user.username}"
                )
            )
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify(
                    {"success": True, "redirect_url": url_for("main.dashboard")}
                )
            flash(f"Создано заявок: {len(created_requests)}", "success")
            return redirect(url_for("main.dashboard"))

        copy_data = None
        copy_from = request.args.get("copy_from", "").strip()
        if copy_from.isdigit():
            src_req = Request.query.get(int(copy_from))
            if src_req:
                obj = (
                    db.session.get(Object, src_req.object_id)
                    if src_req.object_id
                    else None
                )
                contractors = get_request_contractor(src_req)

                copy_data = {
                    "object_id": src_req.object_id,
                    "contractor_ids": src_req.contractor_ids_list,
                    "manufacturers": src_req.manufacturers_list,
                    "comment": src_req.comments[0].content if src_req.comments else "",
                    # Дополнительные поля для совместимости: фронтенд использует их
                    # если основная структура недоступна
                    "object": (
                        {"id": src_req.object_id, "name": (obj.name if obj else "")}
                        if src_req.object_id
                        else None
                    ),
                    "contractors": (
                        [{"id": c.id, "name": c.name} for c in contractors]
                        if contractors
                        else []
                    ),
                }
        return render_template(
            "create_request.html",
            manufacturers=MANUFACTURERS,
            copy_data=copy_data,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in create_request route: {str(e)}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return (
                jsonify(
                    {"error": "Произошла ошибка при создании заявки", "details": str(e)}
                ),
                500,
            )

        flash("Произошла ошибка при создании заявки", "danger")
        return render_template("create_request.html", manufacturers=MANUFACTURERS), 500


@request_crud_bp.route("/view_request/<int:id>", methods=["GET", "POST"])
@login_required
def view_request(id):
    """Просмотр заявки и обновление даты размещения."""
    try:
        safe_log(
            current_app.logger,
            logging.INFO,
            f"Пользователь {current_user.username} открыл заявку {id}",
        )
        req = Request.query.get_or_404(id)
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if request.method == "POST":
            if current_user.role != "admin":
                message = "Доступ запрещён"
                if is_ajax:
                    return jsonify({"success": False, "error": message}), 403
                flash(message, "danger")
                return redirect(url_for("request_crud.view_request", id=id)), 403

            raw_created_at = request.form.get("created_at", "").strip()
            if not raw_created_at:
                message = "Укажите дату и время размещения"
                if is_ajax:
                    return jsonify({"success": False, "error": message}), 400
                flash(message, "danger")
                return redirect(url_for("request_crud.view_request", id=id)), 400

            try:
                new_created_at = datetime.fromisoformat(raw_created_at)
            except ValueError:
                try:
                    new_created_at = datetime.strptime(raw_created_at, "%Y-%m-%dT%H:%M")
                except ValueError:
                    message = "Некорректный формат даты и времени"
                    if is_ajax:
                        return jsonify({"success": False, "error": message}), 400
                    flash(message, "danger")
                    return redirect(url_for("request_crud.view_request", id=id)), 400

            local_tz = _get_local_timezone()
            if new_created_at.tzinfo is None:
                if local_tz is not None:
                    new_created_at_local = new_created_at.replace(tzinfo=local_tz)
                else:
                    new_created_at_local = new_created_at
            else:
                if local_tz is not None:
                    new_created_at_local = new_created_at.astimezone(local_tz)
                else:
                    new_created_at_local = new_created_at

            if isinstance(new_created_at_local, datetime) and new_created_at_local.tzinfo is not None:
                new_created_at_utc = new_created_at_local.astimezone(timezone.utc)
                new_created_at = new_created_at_utc.replace(tzinfo=None)
            else:
                new_created_at = new_created_at_local

            old_created_at = req.created_at
            try:
                req.created_at = new_created_at
                db.session.commit()
            except SQLAlchemyError as err:
                db.session.rollback()
                current_app.logger.error(
                    f"Ошибка при обновлении даты заявки {id}: {err}", exc_info=True
                )
                message = "Не удалось обновить дату заявки"
                if is_ajax:
                    return jsonify({"success": False, "error": message}), 500
                flash(message, "danger")
                return redirect(url_for("request_crud.view_request", id=id)), 500

            safe_log(
                current_app.logger,
                logging.INFO,
                (
                    f"Администратор {current_user.username} обновил дату заявки {id}: "
                    f"{old_created_at} → {req.created_at}"
                ),
            )

            formatted = _format_request_created_at(req.created_at)
            timezone_info = _get_timezone_info()
            message = "Дата размещения обновлена"
            if is_ajax:
                return jsonify(
                    {
                        "success": True,
                        "message": message,
                        "created_at_display": formatted["display"],
                        "created_at_form_value": formatted["form_value"],
                        "timezone_abbr": timezone_info["abbr"],
                        "timezone_title": timezone_info["title"],
                        "timezone_hint": timezone_info["hint"],
                    }
                )

            flash(message, "success")
            return redirect(url_for("request_crud.view_request", id=id))

        processed_by_user = None
        if req.processed_by:
            processed_by_user = db.session.get(User, req.processed_by)

        object_info = db.session.get(Object, req.object_id) if req.object_id else None
        contractors = get_request_contractor(req)

        # Загружаем комментарии
        comments = []
        for comment in req.comments:
            user = db.session.get(User, comment.user_id)
            # Вычисляем оставшееся время для удаления (для обычных пользователей)
            time_diff = datetime.utcnow() - comment.created_at
            can_delete = current_user.role == "admin" or (
                comment.user_id == current_user.id and time_diff.total_seconds() <= 60
            )
            remaining_time = (
                max(0, 60 - int(time_diff.total_seconds()))
                if comment.user_id == current_user.id
                else 0
            )

            comments.append(
                {
                    "id": comment.id,
                    "content": comment.content,
                    "created_at": comment.created_at,
                    "username": user.username if user else "Неизвестный",
                    "user_id": comment.user_id,
                    "can_delete": can_delete,
                    "remaining_time": remaining_time,
                }
            )

        # Загружаем файлы
        files = []
        request_dir = os.path.join(
            current_app.root_path, "static", "uploads", str(req.id)
        )
        if os.path.exists(request_dir):
            for filename in os.listdir(request_dir):
                filepath = os.path.join(request_dir, filename)
                if os.path.isfile(filepath) and not filename.startswith("."):
                    size = os.path.getsize(filepath)
                    files.append(
                        {
                            "path": filepath,
                            "rel_path": os.path.relpath(
                                filepath, os.path.join(current_app.root_path, "static")
                            ),
                            "filename": filename,
                            "size": (
                                f"{size // 1024} KB" if size > 1024 else f"{size} B"
                            ),
                        }
                    )

        # Загружаем вложения (скриншоты)
        attachments = []
        attachment_contractors = {}
        for attachment in Attachment.query.filter_by(request_id=req.id).all():
            contractor = db.session.get(Contractor, attachment.contractor_id)
            attachment_contractors[attachment.id] = (
                contractor.name if contractor else "Неизвестный"
            )
            attachments.append(attachment)

        formatted_created_at = _format_request_created_at(req.created_at)
        timezone_info = _get_timezone_info()

        return render_template(
            "view_request.html",
            req=req,
            object_info=object_info,
            contractors=contractors,
            processed_by_user=processed_by_user,
            comments=comments,
            files=files,
            attachments=attachments,
            attachment_contractors=attachment_contractors,
            created_at_display=formatted_created_at["display"],
            created_at_form_value=formatted_created_at["form_value"],
            timezone_info=timezone_info,
        )

    except Exception as e:
        current_app.logger.error(
            f"Error in view_request route for id {id}: {str(e)}", exc_info=True
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard")), 500


@request_crud_bp.route("/delete_request/<int:id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def delete_request(id):
    """Удаление заявки"""
    try:
        current_app.logger.debug(
            (
                f"Accessing delete_request route for id {id} "
                f"by user {current_user.username}"
            )
        )
        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            return redirect(url_for("main.dashboard"))
        req = Request.query.get_or_404(id)

        # Проверка прав (опционально)
        if current_user.role != "admin":
            flash("Только администратор может удалять заявки", "danger")
            return redirect(url_for("main.dashboard"))

        # Удаляем файлы с диска
        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], str(req.id))
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)  # Удаляем всю папку рекурсивно
            current_app.logger.info(f"Deleted upload directory: {upload_dir}")

        # Удаляем вложения (скриншоты)
        attachments = Attachment.query.filter_by(request_id=req.id).all()
        for att in attachments:
            if att.screenshot and os.path.exists(
                os.path.join(current_app.root_path, "static", att.screenshot)
            ):
                try:
                    os.remove(
                        os.path.join(current_app.root_path, "static", att.screenshot)
                    )
                except OSError as e:
                    current_app.logger.warning(
                        f"Could not delete attachment file: {str(e)}"
                    )
            db.session.delete(att)

        # Удаляем файлы из старой схемы (если они есть)
        if req.file_path:
            file_paths = req.file_path.split(",")
            for path in file_paths:
                if path.strip():
                    file_path = os.path.join(
                        current_app.root_path, "static", path.strip()
                    )
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            current_app.logger.info(f"Deleted file: {file_path}")
                        except OSError as e:
                            current_app.logger.warning(
                                f"Could not delete file {file_path}: {str(e)}"
                            )

        # Удаляем комментарии
        for comment in req.comments:
            db.session.delete(comment)

        # Удаляем саму заявку
        db.session.delete(req)
        db.session.commit()

        flash("Заявка и все связанные файлы удалены", "success")
        return redirect(url_for("main.dashboard"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting request {id}: {str(e)}")
        flash("Ошибка при удалении заявки", "danger")
        return redirect(url_for("main.dashboard")), 500


@request_crud_bp.route("/api/draft", methods=["GET", "POST"])
@login_required
def draft_session():
    """Хранение черновика заявки в сессии."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        draft = data.get("draft")
        if draft is None:
            session.pop("request_draft", None)
        else:
            session["request_draft"] = draft
        return jsonify({"ok": True})
    return jsonify({"draft": session.get("request_draft")})

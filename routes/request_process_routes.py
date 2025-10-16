"""
Обработка заявок и работа с файлами
"""

import os
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from extensions import limiter
from models import Attachment, Object, Request, db
from utils.constants import MANUFACTURERS
from utils.request_helpers import get_request_contractor
from utils.statuses import RequestStatus, get_status_class, get_status_label

request_process_bp = Blueprint("request_process", __name__)


@request_process_bp.route("/process_request/<int:id>", methods=["GET", "POST"])
@login_required
def process_request(id):
    """Обработка заявки"""
    try:
        current_app.logger.debug(
            (
                f"Accessing process_request route for id {id} "
                f"by user {current_user.username}"
            )
        )
        req = Request.query.get_or_404(id)
        current_app.logger.debug(
            (
                f"process_request: Request {id} - contractors="
                f"{[c.id for c in get_request_contractor(req)]}"
            )
        )

        contractors = get_request_contractor(req)
        single_contractor = contractors[0] if contractors else None

        if request.method == "POST":
            return submit_process_request(id)

        # Загружаем вложения для отображения уже загруженных файлов
        attachments = Attachment.query.filter_by(request_id=req.id).all()

        # Загружаем объект заявки
        object_info = db.session.get(Object, req.object_id) if req.object_id else None

        return render_template(
            "process_request.html",
            req=req,
            object_info=object_info,
            contractors=contractors,
            single_contractor=single_contractor,
            manufacturers=MANUFACTURERS,
            attachments=attachments,
        )
    except Exception as e:
        current_app.logger.error(
            f"Error in process_request route for id {id}: {str(e)}"
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard")), 500


@request_process_bp.route("/submit_process_request/<int:id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def submit_process_request(id):
    """Обработка отправки формы заявки"""
    try:
        current_app.logger.debug(
            f"Processing request submission for id {id} by user {current_user.username}"
        )
        req = Request.query.get_or_404(id)

        # Получаем данные из формы
        contractor_id = request.form.get("contractor_id")
        manufacturers = request.form.getlist("manufacturers[]")

        current_app.logger.debug(
            f"Received contractor_id: {contractor_id}, manufacturers: {manufacturers}"
        )

        if not contractor_id:
            flash("Выберите подрядчика", "danger")
            return redirect(url_for("request_process.process_request", id=id))

        # Проверяем, что contractor_id состоит только из цифр
        if not contractor_id.isdigit():
            flash("Некорректный ID подрядчика", "danger")
            return redirect(url_for("request_process.process_request", id=id))

        if not manufacturers:
            flash("Выберите хотя бы одного производителя", "danger")
            return redirect(url_for("request_process.process_request", id=id))

        # Обработка загруженных файлов
        files = request.files.getlist("screenshots[]")
        saved_attachments = 0

        current_app.logger.debug(f"Received {len(files)} files for processing")

        if files and any(f.filename for f in files):
            # Создаём папку для загрузок
            upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], str(req.id))
            os.makedirs(upload_dir, exist_ok=True)

            for i, file in enumerate(files):
                if file and file.filename:
                    manufacturer = (
                        manufacturers[i] if i < len(manufacturers) else manufacturers[0]
                    )
                    current_app.logger.debug(
                        (
                            f"Processing file {i}: {file.filename} for manufacturer: "
                            f"{manufacturer}"
                        )
                    )

                    # Безопасные имена
                    filename = secure_filename(file.filename)
                    manufacturer_safe = secure_filename(manufacturer)
                    unique_filename = (
                        f"{req.id}_{contractor_id}_{manufacturer_safe}_"
                        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    )
                    file_path = os.path.join(upload_dir, unique_filename)

                    try:
                        file.save(file_path)
                        current_app.logger.debug(f"File saved to: {file_path}")

                        # Создаём запись в базе
                        attachment = Attachment(
                            request_id=req.id,
                            contractor_id=int(contractor_id),
                            manufacturer=manufacturer,
                            screenshot=f"uploads/{req.id}/{unique_filename}",
                            uploaded_by=current_user.id,
                        )
                        db.session.add(attachment)
                        saved_attachments += 1
                        current_app.logger.debug(
                            f"Attachment record created for file: {filename}"
                        )

                    except Exception as e:
                        current_app.logger.error(
                            f"Error saving file {filename}: {str(e)}"
                        )
                        continue
        else:
            current_app.logger.debug("No files received or all files are empty")

        # Проверяем, обработана ли заявка полностью
        all_manufacturers = set(req.manufacturers_list)
        processed_manufacturers = set()

        # Получаем все обработанные производители
        attachments = Attachment.query.filter_by(request_id=req.id).all()
        for att in attachments:
            processed_manufacturers.add(att.manufacturer)

        # Обновляем статус заявки
        if all_manufacturers.issubset(processed_manufacturers):
            req.status = (
                request.form.get("new_status") or RequestStatus.IN_PROGRESS.value
            )
            req.processed_by = current_user.id
            req.processed_at = db.func.now()
        else:
            req.status = request.form.get("new_status") or RequestStatus.OPEN.value

        db.session.commit()

        if saved_attachments > 0:
            flash(
                f"Заявка обработана. Сохранено {saved_attachments} файлов.", "success"
            )
        else:
            flash("Заявка обновлена, но файлы не были загружены", "warning")

        return redirect(url_for("main.dashboard"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error in submit_process_request for id {id}: {str(e)}"
        )
        flash(f"Ошибка при обработке заявки: {str(e)}", "danger")
        return redirect(url_for("request_process.process_request", id=id))


@request_process_bp.route("/change_request_object/<int:id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def change_request_object(id):
    """зменение объекта заявки"""
    try:
        current_app.logger.debug(
            f"Changing object for request {id} by user {current_user.username}"
        )
        req = Request.query.get_or_404(id)

        # Проверяем права доступа
        if current_user.role != "admin" and current_user.id != req.created_by:
            return jsonify({"error": "Доступ запрещен"}), 403

        # Получаем данные из запроса
        data = request.get_json()
        new_object_id = data.get("new_object_id")

        if not new_object_id:
            return jsonify({"error": "Не указан ID нового объекта"}), 400

        # Проверяем, что объект существует
        new_object = db.session.get(Object, int(new_object_id))
        if not new_object:
            return jsonify({"error": "Объект не найден"}), 404

        # Сохраняем старый объект для логирования
        old_object_id = req.object_id
        old_object = db.session.get(Object, old_object_id) if old_object_id else None

        # Обновляем объект заявки
        req.object_id = int(new_object_id)
        db.session.commit()

        current_app.logger.info(
            (
                f"Request {id} object changed from "
                f"{old_object.name if old_object else 'Unknown'} "
                f"(ID: {old_object_id}) to {new_object.name} (ID: {new_object_id}) "
                f"by user {current_user.username}"
            )
        )

        return jsonify(
            {
                "success": True,
                "message": f'Объект заявки изменен на "{new_object.name}"',
                "new_object_name": new_object.name,
            }
        )

    except ValueError:
        return jsonify({"error": "Некорректный ID объекта"}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing object for request {id}: {str(e)}")
        return jsonify({"error": "Ошибка при изменении объекта заявки"}), 500


@request_process_bp.route("/change_status/<int:id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def change_status(id: int):
    """."""
    try:
        current_app.logger.debug(
            f"Changing status for request {id} by user {current_user.username}"
        )
        req = Request.query.get_or_404(id)

        can_change = (
            current_user.role == "admin"
            or current_user.id == req.created_by
            or current_user.id == req.processed_by
        )
        if not can_change:
            return jsonify({"error": "Доступ запрещён"}), 403

        data = request.get_json() or {}
        new_status = data.get("status")
        if new_status not in RequestStatus.all():
            return jsonify({"error": "Недопустимый статус"}), 400

        old_status = req.status
        req.status = new_status
        db.session.commit()

        current_app.logger.info(
            f"Request {id} status changed from {old_status} to {new_status} "
            f"by user {current_user.username}"
        )

        return jsonify(
            {
                "success": True,
                "label": get_status_label(new_status),
                "class": get_status_class(new_status),
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing status for request {id}: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка"}), 500

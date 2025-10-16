"""
Маршруты для работы с файлами и вложениями
"""

import logging
import os

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    send_from_directory,
)
from flask_login import current_user, login_required
from werkzeug.utils import safe_join

from models import Attachment, db
from security_utils import safe_log

file_bp = Blueprint("files", __name__)


@file_bp.route("/delete_screenshot/<int:attachment_id>", methods=["POST"])
@login_required
def delete_screenshot(attachment_id):
    """Удаление скриншота"""
    try:
        safe_log(
            current_app.logger,
            logging.INFO,
            f"Пользователь {current_user.username} удаляет скриншот {attachment_id}",
        )

        attachment = Attachment.query.get_or_404(attachment_id)

        # Проверяем права доступа
        if current_user.role != "admin" and attachment.uploaded_by != current_user.id:
            safe_log(
                current_app.logger,
                logging.WARNING,
                (
                    "Недостаточно прав: пользователь "
                    f"{current_user.username} попытался удалить скриншот "
                    f"{attachment_id}"
                ),
            )
            return jsonify({"error": "Недостаточно прав для удаления"}), 403

        # Удаляем файл с диска
        if attachment.screenshot:
            file_path = os.path.join(
                current_app.root_path, "static", attachment.screenshot
            )
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    current_app.logger.warning(
                        f"Could not delete file {file_path}: {str(e)}"
                    )

        # Удаляем запись из базы
        db.session.delete(attachment)
        db.session.commit()

        safe_log(
            current_app.logger,
            logging.INFO,
            (
                f"Скриншот {attachment_id} успешно удалён пользователем "
                f"{current_user.username}"
            ),
        )

        return jsonify({"success": True, "message": "Скриншот успешно удален"})

    except Exception as e:
        db.session.rollback()
        safe_log(
            current_app.logger,
            logging.ERROR,
            f"Ошибка при удалении скриншота {attachment_id}: {str(e)}",
        )
        return jsonify({"error": f"Ошибка при удалении скриншота: {str(e)}"}), 500


@file_bp.route("/download_file/<path:filename>")
@login_required
def download_file(filename):
    """Скачивание файла"""
    try:
        base_dir = os.path.join(current_app.root_path, "static")
        directory = os.path.dirname(filename)
        file_name = os.path.basename(filename)

        safe_directory = safe_join(base_dir, directory)
        if not safe_directory:
            current_app.logger.warning(f"Unsafe path: {filename}")
            abort(404)

        full_path = os.path.join(safe_directory, file_name)
        if not os.path.isfile(full_path):
            current_app.logger.warning(f"File not found: {filename}")
            abort(404)

        return send_from_directory(safe_directory, file_name, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error downloading file {filename}: {str(e)}")
        abort(500)

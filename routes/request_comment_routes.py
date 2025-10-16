"""
Комментарии и дополнительные функции для заявок
"""

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

from extensions import limiter
from models import Comment, Contractor, Object, Request, db

request_comment_bp = Blueprint("request_comment", __name__)


@request_comment_bp.route("/add_comment/<int:request_id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def add_comment(request_id):
    """Добавление комментария к заявке"""
    try:
        current_app.logger.debug(
            (
                f"Accessing add_comment route for request_id {request_id} "
                f"by user {current_user.username}"
            )
        )
        Request.query.get_or_404(request_id)

        content = request.form.get("content", "").strip()
        wants_json = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes["application/json"]
            > request.accept_mimetypes["text/html"]
        )
        if not content:
            if wants_json:
                return jsonify({"error": "Введите текст комментария"}), 400
            flash("Введите текст комментария", "danger")
            return redirect(url_for("request_crud.view_request", id=request_id))

        # Создаем комментарий
        comment = Comment(
            request_id=request_id, user_id=current_user.id, content=content
        )
        db.session.add(comment)
        db.session.commit()

        current_app.logger.info(
            f"Comment added to request {request_id} by user {current_user.username}"
        )

        # Для AJAX‑запросов формируем HTML нового комментария
        if wants_json:
            # Вычисляем возможность удаления и время до его истечения
            remaining_time = 60
            comment_data = {
                "id": comment.id,
                "content": comment.content,
                "username": current_user.username,
                "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
                "user_id": current_user.id,
                "can_delete": True,
                "remaining_time": remaining_time,
            }
            rendered_html = render_template(
                "_comment_item.html", comment=comment_data, current_user=current_user
            )
            return jsonify({"success": True, "rendered_html": rendered_html})

        # Для обычных запросов - редирект
        flash("Комментарий добавлен", "success")
        return redirect(url_for("request_crud.view_request", id=request_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error adding comment to request {request_id}: {str(e)}"
        )

        if wants_json:
            return jsonify({"error": "Ошибка при добавлении комментария"}), 500

        flash("Ошибка при добавлении комментария", "danger")
        return redirect(url_for("request_crud.view_request", id=request_id))


@request_comment_bp.route("/delete_comment/<int:comment_id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def delete_comment(comment_id):
    """Удаление комментария"""
    try:
        current_app.logger.debug(
            (
                f"Accessing delete_comment route for comment_id {comment_id} "
                f"by user {current_user.username}"
            )
        )
        comment = Comment.query.get_or_404(comment_id)

        # Проверяем права на удаление
        time_diff = datetime.utcnow() - comment.created_at
        can_delete = current_user.role == "admin" or (
            comment.user_id == current_user.id and time_diff.total_seconds() <= 60
        )

        if not can_delete:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": "Вы не можете удалить этот комментарий"}), 403
            flash("Вы не можете удалить этот комментарий", "danger")
            return redirect(url_for("request_crud.view_request", id=comment.request_id))

        request_id = comment.request_id
        db.session.delete(comment)
        db.session.commit()

        current_app.logger.info(
            f"Comment {comment_id} deleted by user {current_user.username}"
        )

        # Для AJAX запросов возвращаем JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Комментарий удален"})

        # Для обычных запросов - редирект
        flash("Комментарий удален", "success")
        return redirect(url_for("request_crud.view_request", id=request_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting comment {comment_id}: {str(e)}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Ошибка при удалении комментария"}), 500

        flash("Ошибка при удалении комментария", "danger")
        return redirect(url_for("request_crud.view_request", id=comment.request_id))


@request_comment_bp.route(
    "/remove_contractor_from_request/<int:request_id>/<int:contractor_id>",
    methods=["POST"],
)
@login_required
@limiter.limit("10/minute")
def remove_contractor_from_request(request_id, contractor_id):
    """Удаление подрядчика из заявки"""
    try:
        current_app.logger.debug(
            (
                "Accessing remove_contractor_from_request route for request_id "
                f"{request_id}, contractor_id {contractor_id} "
                f"by user {current_user.username}"
            )
        )
        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            return redirect(url_for("main.dashboard"))

        req = Request.query.get_or_404(request_id)

        if req.contractor_id != contractor_id:
            flash("Подрядчик не найден в заявке", "warning")
            return redirect(url_for("request_crud.view_request", id=request_id))

        req.contractor_id = None
        db.session.commit()

        current_app.logger.info(
            (
                f"Contractor {contractor_id} removed from request {request_id} "
                f"by user {current_user.username}"
            )
        )
        flash("Подрядчик удален из заявки", "success")

        return redirect(url_for("request_crud.view_request", id=request_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            (
                f"Error removing contractor {contractor_id} from request {request_id}: "
                f"{str(e)}"
            )
        )
        flash("Ошибка при удалении подрядчика", "danger")
        return redirect(url_for("request_crud.view_request", id=request_id))


@request_comment_bp.route("/object_requests/<int:object_id>")
@login_required
def object_requests(object_id):
    """Просмотр всех заявок для объекта"""
    try:
        current_app.logger.debug(
            (
                f"Accessing object_requests route for object_id {object_id} "
                f"by user {current_user.username}"
            )
        )
        obj = Object.query.get_or_404(object_id)

        requests = (
            Request.query.filter_by(object_id=object_id)
            .order_by(Request.created_at.desc())
            .all()
        )

        return render_template("object_requests.html", object=obj, requests=requests)

    except Exception as e:
        current_app.logger.error(
            f"Error in object_requests route for object_id {object_id}: {str(e)}"
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard"))


@request_comment_bp.route("/contractor_requests/<int:contractor_id>")
@login_required
def contractor_requests(contractor_id):
    """Просмотр всех заявок для подрядчика"""
    try:
        current_app.logger.debug(
            (
                "Accessing contractor_requests route for contractor_id "
                f"{contractor_id} "
                f"by user {current_user.username}"
            )
        )
        contractor = Contractor.query.get_or_404(contractor_id)

        # Получаем заявки, где есть этот подрядчик
        all_requests = Request.query.all()
        requests = [req for req in all_requests if req.contractor_id == contractor_id]

        requests.sort(key=lambda x: x.created_at, reverse=True)

        for req in requests:
            object_info = (
                db.session.get(Object, req.object_id) if req.object_id else None
            )
            req.object_ref = object_info

        return render_template(
            "contractor_requests.html", contractor=contractor, requests=requests
        )

    except Exception as e:
        current_app.logger.error(
            (
                "Error in contractor_requests route for contractor_id "
                f"{contractor_id}: "
                f"{str(e)}"
            )
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard"))

"""
Маршруты для работы с объектами
"""

import logging

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
from sqlalchemy import func

from models import Object, Request, db
from models.op import OpComment, OpFile, OpKPCategory
from routes.search_routes import search_with_multiple_fields
from security_utils import safe_log

object_bp = Blueprint("object", __name__)


@object_bp.route("/objects")
@login_required
def objects():
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)
        if per_page not in (10, 25, 50, 100):
            per_page = 25
        search = request.args.get("search", "").strip()

        # Базовый запрос с оптимизацией
        query = Object.query

        # Применяем поиск, если есть
        if search:
            # спользуем продвинутый поиск по нескольким полям
            all_objects = query.all()
            search_fields = ["name", "address", "customer"]
            filtered_objects = search_with_multiple_fields(
                search, all_objects, search_fields, threshold=0.4
            )

            # Получаем ID отфильтрованных объектов
            filtered_ids = [obj[0].id for obj in filtered_objects]

            # Применяем фильтр к основному запросу
            if filtered_ids:
                query = query.filter(Object.id.in_(filtered_ids))
            else:
                # Если нет совпадений, возвращаем пустой результат
                query = query.filter(Object.id == -1)

        sort = request.args.get("sort", "created_at")
        order = request.args.get("order", "desc")
        sort_columns = {
            "name": Object.name,
            "created_at": Object.created_at,
            "address": Object.address,
        }
        sort_col = sort_columns.get(sort, Object.created_at)
        sort_col = sort_col.desc() if order == "desc" else sort_col.asc()

        for key, value in request.args.items():
            if key.startswith("filter_") and value:
                field = key[len("filter_") :]
                if hasattr(Object, field):
                    query = query.filter(getattr(Object, field) == value)

        pagination = query.order_by(sort_col).paginate(
            page=page, per_page=per_page, error_out=False
        )
        objects = pagination.items

        # Оптимизированный подсчет заявок
        if objects:
            object_ids = [obj.id for obj in objects]
            request_counts = (
                db.session.query(
                    Request.object_id, db.func.count(Request.id).label("count")
                )
                .filter(Request.object_id.in_(object_ids))
                .group_by(Request.object_id)
                .all()
            )

            # Создаем словарь для быстрого доступа
            count_dict = {count.object_id: count.count for count in request_counts}

            # Присваиваем количество заявок каждому объекту
            for obj in objects:
                obj.request_count = count_dict.get(obj.id, 0)
        else:
            for obj in objects:
                obj.request_count = 0

        return render_template(
            "objects.html",
            objects=objects,
            pagination=pagination,
            search=search,
            per_page=per_page,
        )
    except Exception as e:
        safe_log(
            logging.getLogger(__name__),
            logging.ERROR,
            f"Error in objects route: {str(e)}",
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard")), 500


@object_bp.route("/add_object", methods=["POST"])
@login_required
def add_object():
    """Добавление нового объекта"""
    try:
        current_app.logger.debug(
            f"Accessing add_object route by user {current_user.username}"
        )
        name = request.form.get("name")
        if not name:
            return jsonify({"error": "Название объекта обязательно"}), 400

        # Проверяем существование объекта без учета регистра
        existing = Object.query.filter(
            func.lower(Object.name) == func.lower(name.strip())
        ).first()
        if existing:
            return jsonify({"error": "Объект с таким названием уже существует"}), 400

        new_object = Object(name=name.strip())
        db.session.add(new_object)
        db.session.commit()
        return jsonify({"id": new_object.id, "name": new_object.name})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in add_object route: {str(e)}")
        return jsonify({"error": "Ошибка при создании объекта"}), 500


@object_bp.route("/edit_object/<int:id>", methods=["GET", "POST"])
@login_required
def edit_object(id):
    """Редактирование объекта"""
    try:
        current_app.logger.debug(
            f"Accessing edit_object route for id {id} by user {current_user.username}"
        )

        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            return redirect(url_for("object.objects"))

        object_item = Object.query.get_or_404(id)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            address = request.form.get("address", "").strip()
            customer = request.form.get("customer", "").strip()
            phone = request.form.get("phone", "").strip()

            if not name:
                flash("Название объекта обязательно", "danger")
                return render_template("edit_object.html", object=object_item)

            # Проверяем уникальность имени (исключая текущий объект)
            existing = Object.query.filter(
                func.lower(Object.name) == func.lower(name), Object.id != id
            ).first()
            if existing:
                flash("Объект с таким названием уже существует", "danger")
                return render_template("edit_object.html", object=object_item)

            object_item.name = name
            object_item.address = address if address else None
            object_item.customer = customer if customer else None
            object_item.phone = phone if phone else None

            db.session.commit()
            flash("Объект успешно обновлен", "success")
            return redirect(url_for("object.objects"))

        return render_template("edit_object.html", object=object_item)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in edit_object route for id {id}: {str(e)}")
        flash("Произошла ошибка", "danger")
        return redirect(url_for("object.objects")), 500


@object_bp.route("/delete_object/<int:id>", methods=["POST"])
@login_required
def delete_object(id):
    """Удаление объекта"""
    try:
        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            return redirect(url_for("object.objects"))

        obj = Object.query.get_or_404(id)

        # Проверяем связанные сущности
        if Request.query.filter_by(object_id=id).first():
            flash("Нельзя удалить объект, так как он связан с заявками", "danger")
            return redirect(url_for("object.objects"))

        if (
            OpComment.query.filter_by(object_id=id).first()
            or OpFile.query.filter_by(object_id=id).first()
            or OpKPCategory.query.filter(
                OpKPCategory.object_id == id,
                (
                    OpKPCategory.invoice_number.isnot(None)
                    | (OpKPCategory.is_extra.is_(True))
                ),
            ).first()
        ):
            flash(
                "Нельзя удалить объект, так как он содержит связанные данные КП",
                "danger",
            )
            return redirect(url_for("object.objects"))
        # Удаляем базовые категории КП без данных,
        # чтобы удовлетворить ограничение внешнего ключа
        OpKPCategory.query.filter_by(object_id=id).delete()

        db.session.delete(obj)
        db.session.commit()
        flash("Объект удален", "success")
        return redirect(url_for("object.objects"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in delete_object route for id {id}: {str(e)}")
        flash("Ошибка при удалении объекта", "danger")
        return redirect(url_for("object.objects")), 500


@object_bp.route("/object/<int:id>")
@login_required
def object_requests(id):
    """Заявки по объекту"""
    try:
        current_app.logger.debug(
            (
                f"Accessing object_requests route for id {id} "
                f"by user {current_user.username}"
            )
        )
        obj = Object.query.get_or_404(id)

        requests = (
            Request.query.filter_by(object_id=id)
            .order_by(Request.created_at.desc())
            .all()
        )

        return render_template("object_requests.html", object=obj, requests=requests)
    except Exception as e:
        current_app.logger.error(
            f"Error in object_requests route for id {id}: {str(e)}"
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("objects.objects")), 500

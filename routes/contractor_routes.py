"""
Маршруты для работы с подрядчиками
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

from models import Contractor, Request, db
from routes.search_routes import search_with_multiple_fields
from security_utils import safe_log

contractor_bp = Blueprint("contractor", __name__)


@contractor_bp.route("/contractors")
@login_required
def contractors():
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)
        if per_page not in (10, 25, 50, 100):
            per_page = 25
        search = request.args.get("search", "").strip()

        # Базовый запрос с оптимизацией
        query = Contractor.query

        # Применяем поиск, если есть
        if search:
            # спользуем продвинутый поиск по нескольким полям
            all_contractors = query.all()
            search_fields = ["name", "inn", "contact_person", "phone", "email"]
            filtered_contractors = search_with_multiple_fields(
                search, all_contractors, search_fields, threshold=0.4
            )

            # Получаем ID отфильтрованных подрядчиков
            filtered_ids = [cont[0].id for cont in filtered_contractors]

            # Применяем фильтр к основному запросу
            if filtered_ids:
                query = query.filter(Contractor.id.in_(filtered_ids))
            else:
                # Если нет совпадений, возвращаем пустой результат
                query = query.filter(Contractor.id == -1)

        sort = request.args.get("sort", "created_at")
        order = request.args.get("order", "desc")
        sort_columns = {
            "name": Contractor.name,
            "inn": Contractor.inn,
            "created_at": Contractor.created_at,
        }
        sort_col = sort_columns.get(sort, Contractor.created_at)
        sort_col = sort_col.desc() if order == "desc" else sort_col.asc()

        for key, value in request.args.items():
            if key.startswith("filter_") and value:
                field = key[len("filter_") :]
                if hasattr(Contractor, field):
                    query = query.filter(getattr(Contractor, field) == value)

        pagination = query.order_by(sort_col).paginate(
            page=page, per_page=per_page, error_out=False
        )
        contractors = pagination.items

        # Оптимизированный подсчёт заявок для всех подрядчиков на странице
        if contractors:
            contractor_ids = [c.id for c in contractors]

            # Recompute counts via proper JOIN on association table
            from models import request_contractor

            counts = (
                db.session.query(
                    request_contractor.c.contractor_id.label("cid"),
                    func.count(Request.id).label("cnt"),
                )
                .join(Request, request_contractor.c.request_id == Request.id)
                .filter(request_contractor.c.contractor_id.in_(contractor_ids))
                .group_by(request_contractor.c.contractor_id)
                .all()
            )
            count_dict = {cid: 0 for cid in contractor_ids}
            for row in counts:
                # row may be tuple-like (cid, cnt)
                cid = getattr(row, "cid", None) or row[0]
                cnt_val = getattr(row, "cnt", None) or row[1]
                count_dict[cid] = cnt_val

            # Присваиваем количество заявок каждому подрядчику
            for contractor in contractors:
                contractor.request_count = count_dict.get(contractor.id, 0)
        else:
            for contractor in contractors:
                contractor.request_count = 0

        return render_template(
            "contractors.html",
            contractors=contractors,
            pagination=pagination,
            search=search,
            per_page=per_page,
        )
    except Exception as e:
        safe_log(
            logging.getLogger(__name__),
            logging.ERROR,
            f"Error in contractors route: {str(e)}",
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard")), 500


@contractor_bp.route("/add_contractor", methods=["POST"])
@login_required
def add_contractor():
    """Добавление нового подрядчика"""
    try:
        current_app.logger.debug(
            f"Accessing add_contractor route by user {current_user.username}"
        )
        name = request.form.get("name", "").strip()

        # Валидация имени
        if not name:
            return jsonify({"error": "Название подрядчика обязательно"}), 400

        if len(name) < 2:
            return (
                jsonify(
                    {"error": "Название подрядчика должно содержать минимум 2 символа"}
                ),
                400,
            )

        if len(name) > 200:
            return (
                jsonify(
                    {
                        "error": (
                            "Название подрядчика слишком длинное "
                            "(максимум 200 символов)"
                        )
                    }
                ),
                400,
            )

        # Проверяем существование подрядчика без учета регистра
        existing = Contractor.query.filter(
            func.lower(Contractor.name) == func.lower(name)
        ).first()
        if existing:
            return jsonify({"error": "Подрядчик с таким названием уже существует"}), 400

        new_contractor = Contractor(name=name)
        db.session.add(new_contractor)
        db.session.commit()

        current_app.logger.info(
            f"New contractor created: {name} by user {current_user.username}"
        )
        return jsonify(
            {"id": new_contractor.id, "name": new_contractor.name, "success": True}
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in add_contractor route: {str(e)}")
        return jsonify({"error": f"Ошибка при создании подрядчика: {str(e)}"}), 500


@contractor_bp.route("/edit_contractor/<int:id>", methods=["GET", "POST"])
@login_required
def edit_contractor(id):
    """Редактирование подрядчика"""
    try:
        current_app.logger.debug(
            (
                f"Accessing edit_contractor route for id {id} "
                f"by user {current_user.username}"
            )
        )

        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            return redirect(url_for("contractor.contractors"))

        contractor = Contractor.query.get_or_404(id)
        next_url = request.args.get("next")

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            inn = request.form.get("inn", "").strip()
            contact_person = request.form.get("contact_person", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()

            if not name:
                flash("Название подрядчика обязательно", "danger")
                return render_template(
                    "edit_contractor.html", contractor=contractor, next_url=next_url
                )

            # Проверяем уникальность имени (исключая текущего подрядчика)
            existing = Contractor.query.filter(
                func.lower(Contractor.name) == func.lower(name), Contractor.id != id
            ).first()
            if existing:
                flash("Подрядчик с таким названием уже существует", "danger")
                return render_template(
                    "edit_contractor.html", contractor=contractor, next_url=next_url
                )

            contractor.name = name
            contractor.inn = inn if inn else None
            contractor.contact_person = contact_person if contact_person else None
            contractor.phone = phone if phone else None
            contractor.email = email if email else None

            db.session.commit()
            flash("Подрядчик успешно обновлен", "success")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("contractor.contractors"))

        return render_template(
            "edit_contractor.html", contractor=contractor, next_url=next_url
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error in edit_contractor route for id {id}: {str(e)}"
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("contractor.contractors")), 500


@contractor_bp.route("/delete_contractor/<int:id>", methods=["POST"])
@login_required
def delete_contractor(id):
    """Удаление подрядчика"""
    try:
        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            return redirect(url_for("contractor.contractors"))

        contractor = Contractor.query.get_or_404(id)

        # Проверяем, есть ли связанные заявки
        from models import request_contractor

        requests = (
            Request.query.join(
                request_contractor, request_contractor.c.request_id == Request.id
            )
            .filter(request_contractor.c.contractor_id == id)
            .first()
        )
        if requests:
            flash("Нельзя удалить подрядчика, так как он связан с заявками", "danger")
            return redirect(url_for("contractor.contractors"))

        db.session.delete(contractor)
        db.session.commit()
        flash("Подрядчик удален", "success")
        return redirect(url_for("contractor.contractors"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error in delete_contractor route for id {id}: {str(e)}"
        )
        flash("Ошибка при удалении подрядчика", "danger")
        return redirect(url_for("contractor.contractors")), 500


@contractor_bp.route("/contractor/<int:id>")
@login_required
def contractor_requests(id):
    """Заявки по подрядчику"""
    try:
        current_app.logger.debug(
            (
                f"Accessing contractor_requests route for id {id} "
                f"by user {current_user.username}"
            )
        )
        from models import Object

        contractor = Contractor.query.get_or_404(id)

        # Получаем заявки, в которых участвует этот подрядчик
        from models import request_contractor

        requests = (
            Request.query.join(
                request_contractor, request_contractor.c.request_id == Request.id
            )
            .filter(request_contractor.c.contractor_id == id)
            .order_by(Request.created_at.desc())
            .all()
        )

        # Загружаем связанные объекты
        object_ids = {req.object_id for req in requests}
        objects_dict = {}
        if object_ids:
            objects = Object.query.filter(Object.id.in_(object_ids)).all()
            objects_dict = {obj.id: obj for obj in objects}

        return render_template(
            "contractor_requests.html",
            contractor=contractor,
            requests=requests,
            objects_dict=objects_dict,
        )
    except Exception as e:
        current_app.logger.error(
            f"Error in contractor_requests route for id {id}: {str(e)}"
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("contractors.contractors")), 500

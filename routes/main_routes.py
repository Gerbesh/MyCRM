"""
Основные маршруты приложения
"""

import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from models import Contractor, Object, Request, User, db
from security_utils import safe_log, validate_password_strength
from utils.statuses import RequestStatus

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@main_bp.route("/index")
@login_required
def index():
    try:
        safe_log(
            current_app.logger,
            logging.INFO,
            f"Пользователь {current_user.username} открыл главную страницу",
        )
        response = make_response(render_template("index.html"))
        response.headers["Cache-Control"] = "no-cache"
        return response
    except Exception as e:
        current_app.logger.error(f"Error in index route: {str(e)}")
        raise  # Для development, чтобы увидеть реальную ошибку


@main_bp.route("/dashboard")
@login_required
def dashboard():
    try:
        safe_log(
            current_app.logger,
            logging.INFO,
            f"Пользователь {current_user.username} открыл дашборд",
        )
        status_filter = request.args.get("status", "all")
        search_query = request.args.get("search", "").strip()
        my_requests_only = request.args.get("my_requests") == "true"
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)
        if per_page not in (10, 25, 50, 100):
            per_page = 25

        # Фильтрация заявок
        query = Request.query

        # Фильтр по статусу (новый Enum + совместимость со старыми значениями)
        if status_filter in RequestStatus.all():
            query = query.filter_by(status=status_filter)
        elif status_filter == "processed":
            query = query.filter_by(status=RequestStatus.DONE.value)
        elif status_filter == "unprocessed":
            query = query.filter(
                Request.status.in_(
                    [
                        RequestStatus.OPEN.value,
                        RequestStatus.IN_PROGRESS.value,
                        RequestStatus.NEED_INFO.value,
                    ]
                )
            )

        # Фильтр "Только мои заявки"
        if my_requests_only:
            query = query.filter_by(created_by=current_user.id)

        # Поиск
        request_order = {}  # нициализируем по умолчанию
        if search_query:
            from routes.search_routes import search_with_multiple_fields

            # Получаем все заявки для поиска
            all_requests = query.all()

            # Подготавливаем данные для расширенного поиска
            enhanced_requests = []

            # Предварительно загружаем связанные данные для поиска
            if all_requests:
                request_ids = [req.id for req in all_requests]
                object_ids = list(set(req.object_id for req in all_requests))

                # Загружаем объекты
                objects_dict = {
                    obj.id: obj
                    for obj in db.session.query(Object)
                    .filter(Object.id.in_(object_ids))
                    .all()
                }

                # Загружаем подрядчиков
                contractor_ids = set()
                for req in all_requests:
                    contractor_ids.update(req.contractor_ids_list)
                contractor_ids = list(contractor_ids)

                contractors_dict = {
                    c.id: c
                    for c in db.session.query(Contractor)
                    .filter(Contractor.id.in_(contractor_ids))
                    .all()
                }

                # Создаем расширенные объекты для поиска
                for req in all_requests:
                    obj = objects_dict.get(req.object_id)

                    # Собираем имена подрядчиков для этой заявки
                    contractor_names = []
                    for cid in req.contractor_ids_list:
                        contractor = contractors_dict.get(cid)
                        if contractor:
                            contractor_names.append(contractor.name)

                    # Создаем объект с дополнительными полями для поиска
                    enhanced_req = type(
                        "EnhancedRequest",
                        (),
                        {
                            "id": req.id,
                            "original_request": req,
                            "object_name": obj.name if obj else "",
                            "object_address": obj.address if obj else "",
                            "object_customer": obj.customer if obj else "",
                            "manufacturers": req.manufacturers or "",
                            "contractor_names": " ".join(contractor_names),
                            "combined_search_text": " ".join(
                                filter(
                                    None,
                                    [
                                        obj.name if obj else "",
                                        obj.address if obj else "",
                                        obj.customer if obj else "",
                                        req.manufacturers or "",
                                        " ".join(contractor_names),
                                    ],
                                )
                            ),
                        },
                    )()

                    enhanced_requests.append(enhanced_req)

            # спользуем продвинутый поиск с низким порогом для гибкости
            search_fields = [
                "object_name",
                "object_address",
                "object_customer",
                "manufacturers",
                "contractor_names",
                "combined_search_text",
            ]

            search_results = search_with_multiple_fields(
                search_query, enhanced_requests, search_fields, threshold=0.3
            )

            # Получаем ID найденных заявок
            if search_results:
                found_request_ids = [result[0].id for result in search_results]
                query = Request.query.filter(Request.id.in_(found_request_ids))

                # Сохраняем порядок релевантности
                request_order = {
                    req_id: i for i, req_id in enumerate(found_request_ids)
                }
            else:
                # Если нет совпадений, возвращаем пустой результат
                query = Request.query.filter(Request.id == -1)
                request_order = {}

        # Пагинация с оптимизированными запросами
        if search_query and "request_order" in locals() and request_order:
            # Для поисковых результатов сортируем по релевантности
            requests_with_relevance = query.all()

            # Сортируем по релевантности
            requests_with_relevance.sort(key=lambda x: request_order.get(x.id, 999))

            # Ручная пагинация для поисковых результатов
            total_items = len(requests_with_relevance)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            requests = requests_with_relevance[start_idx:end_idx]

            # Создаем объект пагинации вручную
            class ManualPagination:
                def __init__(self, items, page, per_page, total):
                    self.items = items
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = (total + per_page - 1) // per_page if total > 0 else 1
                    self.has_prev = page > 1
                    self.has_next = page < self.pages
                    self.prev_num = page - 1 if self.has_prev else None
                    self.next_num = page + 1 if self.has_next else None

                def iter_pages(
                    self, left_edge=2, left_current=2, right_current=3, right_edge=2
                ):
                    last = self.pages
                    for num in range(1, last + 1):
                        if (
                            num <= left_edge
                            or (
                                self.page - left_current - 1
                                < num
                                < self.page + right_current
                            )
                            or num > last - right_edge
                        ):
                            yield num

            pagination = ManualPagination(requests, page, per_page, total_items)
        else:
            # Обычная пагинация для не-поисковых запросов
            pagination = query.order_by(Request.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            requests = pagination.items

        # Оптимизированная загрузка связанных данных
        if requests:
            # Собираем все ID за один проход
            contractor_ids = set()
            object_ids = {req.object_id for req in requests}
            request_ids = [req.id for req in requests]
            creator_ids = {
                req.created_by for req in requests
            }  # Авторов собираем отдельно

            for req in requests:
                contractor_ids.update(req.contractor_ids_list)

            # Загружаем данные одним запросом
            contractors = {
                c.id: c
                for c in Contractor.query.filter(
                    Contractor.id.in_(contractor_ids)
                ).all()
            }
            objects = {
                o.id: o for o in Object.query.filter(Object.id.in_(object_ids)).all()
            }
            users = {u.id: u for u in User.query.filter(User.id.in_(creator_ids)).all()}

            # Загружаем вложения одним запросом
            from models import Attachment

            attachments = Attachment.query.filter(
                Attachment.request_id.in_(request_ids)
            ).all()
            attachment_map = {}
            for att in attachments:
                key = (att.request_id, att.contractor_id)
                if key not in attachment_map:
                    attachment_map[key] = set()
                attachment_map[key].add(att.manufacturer)
        else:
            contractors = {}
            objects = {}
            users = {}
            attachment_map = {}

        # Формируем строки для отображения
        table_rows = []
        for req in requests:
            obj = objects.get(req.object_id)
            obj_name = obj.name if obj else "Без объекта"

            for cid in req.contractor_ids_list:
                contractor = contractors.get(cid)
                contractor_name = contractor.name if contractor else "Неизвестно"

                # Все производители в заявке
                all_manufacturers = req.manufacturers_list

                # Обработанные производители для этого подрядчика
                processed_manufacturers = attachment_map.get((req.id, cid), set())

                # Формируем строки с цветами
                manufacturer_badges = []
                for mfr in all_manufacturers:
                    is_processed = mfr in processed_manufacturers
                    manufacturer_badges.append(
                        {"name": mfr, "is_processed": is_processed}
                    )

                # Определяем статус заявки
                all_processed = True
                for other_cid in req.contractor_ids_list:
                    other_key = (req.id, other_cid)
                    other_processed = attachment_map.get(other_key, set())
                    other_manufacturers = set(req.manufacturers_list)
                    if not other_manufacturers.issubset(other_processed):
                        all_processed = False
                        break

                display_status = req.status

                creator = users.get(req.created_by)
                creator_name = creator.username if creator else "Неизвестно"

                table_rows.append(
                    {
                        "request": req,
                        "contractor": contractor,
                        "contractor_name": contractor_name,
                        "object_name": obj_name,
                        "creator_name": creator_name,
                        "manufacturer_badges": manufacturer_badges,
                        "created_at": req.created_at,
                        "status": display_status,
                    }
                )

        # Подсчёт заявок, созданных сегодня
        from datetime import date, datetime

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        today_count = Request.query.filter(
            Request.created_at >= today_start, Request.created_at <= today_end
        ).count()

        # Подсчёт общей статистики из базы данных (не из пагинированных данных)
        total_requests = Request.query.count()
        processed_requests = Request.query.filter_by(
            status=RequestStatus.DONE.value
        ).count()
        unprocessed_requests = Request.query.filter(
            Request.status.in_(
                [
                    RequestStatus.OPEN.value,
                    RequestStatus.IN_PROGRESS.value,
                    RequestStatus.NEED_INFO.value,
                ]
            )
        ).count()

        return render_template(
            "dashboard.html",
            table_rows=table_rows,
            pagination=pagination,
            current_filter=status_filter,
            per_page=per_page,
            today_count=today_count,
            total_requests=total_requests,
            processed_requests=processed_requests,
            unprocessed_requests=unprocessed_requests,
            search_query=search_query,
            my_requests_only=my_requests_only,
        )
    except Exception as e:
        # Логируем и делегируем обработку централизованному обработчику,
        # чтобы отобразить подробности ошибки пользователю
        current_app.logger.error(f"Error in dashboard route: {str(e)}", exc_info=True)
        from error_handler import handle_generic_error

        return handle_generic_error(e)


@main_bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    try:
        current_app.logger.debug(
            f"Accessing change_password route by user {current_user.username}"
        )

        if request.method == "POST":
            from werkzeug.security import check_password_hash, generate_password_hash

            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if not current_password or not new_password or not confirm_password:
                flash("Заполните все поля", "danger")
                return render_template("change_password.html")

            if not check_password_hash(current_user.password, current_password):
                flash("Текущий пароль неверный", "danger")
                return render_template("change_password.html")

            if new_password != confirm_password:
                flash("Новые пароли не совпадают", "danger")
                return render_template("change_password.html")

            valid, error = validate_password_strength(new_password)
            if not valid:
                flash(error, "danger")
                return render_template("change_password.html")

            current_user.password = generate_password_hash(new_password)
            db.session.commit()
            flash("Пароль успешно изменен", "success")
            return redirect(url_for("main.dashboard"))

        return render_template("change_password.html")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in change_password route: {str(e)}")
        flash("Произошла ошибка при смене пароля", "danger")
        return render_template("change_password.html"), 500

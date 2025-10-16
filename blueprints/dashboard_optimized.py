"""
Оптимизированный blueprint дашборда с эффективными запросами к БД.
Устраняет проблему N+1 и использует корректные JOIN-запросы.
"""

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
from sqlalchemy import case, func, or_
from sqlalchemy.orm import (
    joinedload,
    selectinload,
)

from models import Attachment, Contractor, Object, Request, User, db
from security_utils import sanitize_input
from utils.statuses import RequestStatus

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Оптимизированный дашборд: эффективные запросы и минимум обращений к БД
    """
    try:
        current_app.logger.debug(
            f"Доступ к оптимизированному дашборду: пользователь {current_user.username}"
        )

        # Получаем параметры фильтра
        status_filter = request.args.get("status", "all")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)
        if per_page not in (10, 25, 50, 100):
            per_page = 25

        # Базовый запрос с жадной загрузкой связанных объектов
        base_query = Request.query.options(
            joinedload(Request.creator),
            joinedload(Request.processor),
            joinedload(Request.object),  # Загружаем объект тем же запросом
        )

        # Применяем фильтр статуса (поддержка старых и новых значений)
        if status_filter in RequestStatus.all():
            base_query = base_query.filter_by(status=status_filter)
        elif status_filter == "processed":
            base_query = base_query.filter_by(status=RequestStatus.DONE.value)
        elif status_filter == "unprocessed":
            base_query = base_query.filter(
                Request.status.in_(
                    [
                        RequestStatus.OPEN.value,
                        RequestStatus.IN_PROGRESS.value,
                        RequestStatus.NEED_INFO.value,
                    ]
                )
            )

        # Выполняем пагинированный запрос
        pagination = base_query.order_by(Request.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        requests = pagination.items

        if not requests:
            return render_template(
                "dashboard.html",
                table_rows=[],
                pagination=pagination,
                current_filter=status_filter,
                per_page=per_page,
            )

        # Собираем все ID для пакетной загрузки
        request_ids = [req.id for req in requests]
        contractor_ids = set()

        # Собираем ID подрядчиков из всех заявок
        for req in requests:
            contractor_ids.update(req.contractor_ids_list)

        # Пакетно загружаем подрядчиков одним запросом
        contractors_dict = {}
        if contractor_ids:
            contractors = Contractor.query.filter(
                Contractor.id.in_(contractor_ids)
            ).all()
            contractors_dict = {c.id: c for c in contractors}

        # Оптимизированный запрос вложений с единичным JOIN
        # Получаем всех обработанных производителей для каждой пары
        # (request_id, contractor_id)
        attachment_subquery = (
            db.session.query(
                Attachment.request_id,
                Attachment.contractor_id,
                func.group_concat(Attachment.manufacturer).label("manufacturers"),
            )
            .filter(Attachment.request_id.in_(request_ids))
            .group_by(Attachment.request_id, Attachment.contractor_id)
            .subquery()
        )

        # Execute the attachment query
        attachment_results = db.session.query(
            attachment_subquery.c.request_id,
            attachment_subquery.c.contractor_id,
            attachment_subquery.c.manufacturers,
        ).all()

        # Build attachment map
        attachment_map = {}
        for req_id, contractor_id, manufacturers_str in attachment_results:
            key = (req_id, contractor_id)
            if manufacturers_str:
                attachment_map[key] = set(manufacturers_str.split(","))
            else:
                attachment_map[key] = set()

        # Build optimized table rows
        table_rows = []

        for req in requests:
            # Object is already loaded via joinedload
            obj_name = req.object.name if req.object else "Без объекта"

            # Process each contractor for this request
            for cid in req.contractor_ids_list:
                contractor = contractors_dict.get(cid)
                contractor_name = contractor.name if contractor else "Неизвестно"

                # Get manufacturers for this request
                all_manufacturers = req.manufacturers_list

                # Get processed manufacturers for this contractor
                processed_manufacturers = attachment_map.get((req.id, cid), set())

                # Create manufacturer badges
                manufacturer_badges = []
                for mfr in all_manufacturers:
                    manufacturer_badges.append(
                        {"name": mfr, "is_processed": mfr in processed_manufacturers}
                    )

                # Status comes from request field (unified enum)
                display_status = req.status

                table_rows.append(
                    {
                        "request": req,
                        "contractor": contractor,
                        "contractor_name": contractor_name,
                        "object_name": obj_name,
                        "manufacturer_badges": manufacturer_badges,
                        "created_at": req.created_at,
                        "status": display_status,
                    }
                )

        current_app.logger.debug(
            f"Dashboard loaded {len(table_rows)} rows with {len(requests)} requests"
        )

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

        # Подсчёт заявок, созданных сегодня
        from datetime import date, datetime

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        today_count = Request.query.filter(
            Request.created_at >= today_start, Request.created_at <= today_end
        ).count()

        return render_template(
            "dashboard.html",
            table_rows=table_rows,
            pagination=pagination,
            current_filter=status_filter,
            per_page=per_page,
            total_requests=total_requests,
            processed_requests=processed_requests,
            unprocessed_requests=unprocessed_requests,
            today_count=today_count,
        )

    except Exception as e:
        current_app.logger.error(f"Error in optimized dashboard: {str(e)}")
        flash("Произошла ошибка при загрузке дашборда", "danger")
        return redirect(url_for("main.index")), 500


@dashboard_bp.route("/dashboard/stats")
@login_required
def dashboard_stats():
    """
    Efficient dashboard statistics using aggregation queries
    """
    try:
        # Single query for request statistics
        stats_query = db.session.query(
            func.count(Request.id).label("total_requests"),
            func.sum(
                case([(Request.status == RequestStatus.DONE.value, 1)], else_=0)
            ).label("processed_requests"),
            func.sum(
                case(
                    [
                        (
                            Request.status.in_(
                                [
                                    RequestStatus.OPEN.value,
                                    RequestStatus.IN_PROGRESS.value,
                                    RequestStatus.NEED_INFO.value,
                                ]
                            ),
                            1,
                        )
                    ],
                    else_=0,
                )
            ).label("unprocessed_requests"),
            func.count(func.distinct(Request.created_by)).label("unique_creators"),
        ).first()

        # Contractor statistics
        contractor_stats = db.session.query(
            func.count(Contractor.id).label("total_contractors")
        ).first()

        # Object statistics
        object_stats = db.session.query(
            func.count(Object.id).label("total_objects")
        ).first()

        # Recent activity (last 7 days)
        from datetime import datetime, timedelta

        week_ago = datetime.utcnow() - timedelta(days=7)

        recent_activity = (
            db.session.query(func.count(Request.id).label("requests_this_week"))
            .filter(Request.created_at >= week_ago)
            .first()
        )

        stats = {
            "total_requests": stats_query.total_requests or 0,
            "processed_requests": stats_query.processed_requests or 0,
            "unprocessed_requests": stats_query.unprocessed_requests or 0,
            "unique_creators": stats_query.unique_creators or 0,
            "total_contractors": contractor_stats.total_contractors or 0,
            "total_objects": object_stats.total_objects or 0,
            "requests_this_week": recent_activity.requests_this_week or 0,
        }

        return jsonify(stats)

    except Exception as e:
        current_app.logger.error(f"Error in dashboard stats: {str(e)}")
        return jsonify({"error": "Failed to load statistics"}), 500


@dashboard_bp.route("/dashboard/search")
@login_required
def dashboard_search():
    """
    Optimized search across requests with full-text capabilities
    """
    try:
        query = request.args.get("q", "").strip()

        # Validate search query
        query, valid, error = sanitize_input(query, max_length=100)
        if not valid:
            return jsonify({"error": error}), 400

        if len(query) < 2:
            return jsonify([])

        # Optimized search query with JOINs
        search_results = (
            Request.query.options(
                joinedload(Request.object),
                joinedload(Request.creator),
                selectinload(Request.contractors),
            )
            .join(Object)
            .join(User, Request.created_by == User.id)
            .filter(
                or_(
                    Object.name.ilike(f"%{query}%"),
                    Object.address.ilike(f"%{query}%"),
                    Object.customer.ilike(f"%{query}%"),
                    User.username.ilike(f"%{query}%"),
                    Request.status.ilike(f"%{query}%"),
                )
            )
            .limit(20)
            .all()
        )

        results = []
        for req in search_results:
            results.append(
                {
                    "id": req.id,
                    "object_name": req.object.name if req.object else "",
                    "status": req.status,
                    "created_by": req.creator.username if req.creator else "",
                    "created_at": req.created_at.strftime("%Y-%m-%d %H:%M"),
                    "contractors": [c.name for c in req.contractors],
                }
            )

        return jsonify(results)

    except Exception as e:
        current_app.logger.error(f"Error in dashboard search: {str(e)}")
        return jsonify({"error": "Search failed"}), 500


@dashboard_bp.route("/dashboard/export")
@login_required
def dashboard_export():
    """
    Export dashboard data efficiently for reports
    """
    try:
        export_format = request.args.get("format", "json")

        # Efficient query for export
        export_query = Request.query.options(
            joinedload(Request.object),
            joinedload(Request.creator),
            joinedload(Request.processor),
            selectinload(Request.contractors),
        ).order_by(Request.created_at.desc())

        requests = export_query.all()

        export_data = []
        for req in requests:
            export_data.append(
                {
                    "id": req.id,
                    "object": req.object.name if req.object else "",
                    "contractors": [c.name for c in req.contractors],
                    "manufacturers": req.manufacturers_list,
                    "status": req.status,
                    "created_by": req.creator.username if req.creator else "",
                    "processed_by": req.processor.username if req.processor else "",
                    "created_at": req.created_at.isoformat(),
                    "processed_at": (
                        req.processed_at.isoformat() if req.processed_at else None
                    ),
                }
            )

        if export_format == "csv":
            # Convert to CSV format
            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "id",
                    "object",
                    "contractors",
                    "manufacturers",
                    "status",
                    "created_by",
                    "processed_by",
                    "created_at",
                    "processed_at",
                ],
            )
            writer.writeheader()

            for row in export_data:
                # Convert lists to strings for CSV
                row["contractors"] = ", ".join(row["contractors"])
                row["manufacturers"] = ", ".join(row["manufacturers"])
                writer.writerow(row)

            from flask import Response

            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=dashboard_export.csv"
                },
            )

        return jsonify(export_data)

    except Exception as e:
        current_app.logger.error(f"Error in dashboard export: {str(e)}")
        return jsonify({"error": "Export failed"}), 500

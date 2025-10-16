import os
import platform
import shlex
import shutil
import shutil as _shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from zipfile import ZIP_DEFLATED, ZipFile

from flask import (
    Blueprint,
    after_this_request,
    current_app,
    flash,
    redirect,
    render_template,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import inspect, text

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/restart", methods=["POST"])
@login_required
def restart_app():
    """Перезапускает приложение через systemd или указанную команду."""
    if getattr(current_user, "role", None) != "admin":
        flash("Доступ запрещён", "danger")
        return redirect(url_for("main.index"))

    allow_systemctl = bool(current_app.config.get("ALLOW_SYSTEMCTL_RESTART", False))
    service_name = (current_app.config.get("SYSTEMD_SERVICE_NAME") or "").strip()
    command_template = (current_app.config.get("APP_RESTART_COMMAND") or "").strip()
    deploy_command = (current_app.config.get("DEPLOY_RESTART_COMMAND") or "").strip()
    if not command_template:
        command_template = deploy_command
    if not command_template:
        legacy_script_candidates = [
            Path(current_app.root_path) / ".restart-app",
            Path(current_app.root_path).parent / ".restart-app",
        ]
        for candidate in legacy_script_candidates:
            if not candidate.is_file():
                continue

            if os.access(candidate, os.X_OK):
                command_template = str(candidate)
            else:
                command_template = f"/bin/sh {shlex.quote(str(candidate))}"
            break

    try:
        if command_template:
            command = _prepare_restart_command(command_template, service_name)
            _run_restart_command(command)
        elif allow_systemctl and service_name:
            _run_restart_command(f"systemctl restart {service_name}")
        else:
            flash(
                "Команда перезапуска не настроена: задайте SYSTEMD_SERVICE_NAME "
                "и ALLOW_SYSTEMCTL_RESTART или APP_RESTART_COMMAND",
                "warning",
            )
            return redirect(url_for("main.index"))
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        current_app.logger.error(
            "systemctl перезапуск завершился ошибкой %s: %s", exc.returncode, stderr
        )
        flash("Не удалось инициировать перезапуск", "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка перезапуска приложения: {exc}")
        flash("Не удалось инициировать перезапуск", "danger")
    else:
        flash("Перезапуск приложения запущен", "success")

    return redirect(url_for("main.index"))


def _prepare_restart_command(template: str, service_name: str) -> str:
    command = template
    if "{service}" in template:
        if not service_name:
            raise ValueError(
                "SYSTEMD_SERVICE_NAME не задан для подстановки команды перезапуска"
            )
        command = template.replace("{service}", service_name)
    return command


def _run_restart_command(command: str) -> None:
    if not command:
        raise ValueError("Команда перезапуска пустая")
    args = shlex.split(command)
    current_app.logger.info("Запуск перезапуска через: %s", " ".join(args[:4]))
    subprocess.run(args, check=True, capture_output=True, text=True)


def _sqlite_db_path() -> str | None:
    """Вернуть путь к файлу SQLite, если используется SQLite. наче None."""
    try:
        from database import db  # локальный импорт, чтобы избежать циклов

        url = db.engine.url
        if url.get_backend_name() == "sqlite":
            return url.database  # абсолютный путь к файлу
    except Exception as e:  # noqa: BLE001
        current_app.logger.warning(f"Не удалось определить путь SQLite: {e}")
    return None


def _dump_rdbms_to_sql(tmp_dir: str) -> str | None:
    """Попытаться создать SQL-дамп для MySQL/Postgres.

    Возвращает путь к файлу либо None.

    Для MySQL используется mysqldump (пароль передаётся через env MYSQL_PWD),
    для PostgreSQL — pg_dump (пароль через env PGPASSWORD).
    Если утилит нет — вернёт None.
    """
    try:
        from database import db  # локальный импорт

        url = db.engine.url
        backend = url.get_backend_name()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if backend == "mysql":
            mysqldump = shutil.which("mysqldump")
            if not mysqldump:
                return None
            out_path = os.path.join(tmp_dir, f"db_dump_{ts}.sql")
            env = os.environ.copy()
            if url.password:
                env["MYSQL_PWD"] = str(url.password)
            cmd = [
                mysqldump,
                f"-h{url.host or 'localhost'}",
                f"-P{url.port or 3306}",
                f"-u{url.username or ''}",
                "--databases",
                url.database or "",
                "--routines",
                "--events",
                "--single-transaction",
            ]
            # Не логируем команду, чтобы не светить креды
            with open(out_path, "wb") as f:
                proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
            if proc.returncode == 0 and os.path.getsize(out_path) > 0:
                return out_path
            # Логируем только stderr без паролей
            current_app.logger.warning(
                (
                    f"mysqldump завершился с кодом {proc.returncode}: "
                    f"{proc.stderr.decode(errors='ignore')[:500]}"
                )
            )
            return None

        if backend in {"postgresql", "postgres"}:
            pg_dump = shutil.which("pg_dump")
            if not pg_dump:
                return None
            out_path = os.path.join(tmp_dir, f"db_dump_{ts}.sql")
            env = os.environ.copy()
            if url.password:
                env["PGPASSWORD"] = str(url.password)
            cmd = [
                pg_dump,
                "-h",
                url.host or "localhost",
                "-p",
                str(url.port or 5432),
                "-U",
                url.username or "",
                "-F",
                "p",  # plain SQL
                "-f",
                out_path,
                url.database or "",
            ]
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
            )
            if proc.returncode == 0 and os.path.isfile(out_path):
                return out_path
            current_app.logger.warning(
                (
                    f"pg_dump завершился с кодом {proc.returncode}: "
                    f"{proc.stderr.decode(errors='ignore')[:500]}"
                )
            )
            return None
    except Exception as e:  # noqa: BLE001
        current_app.logger.warning(f"Ошибка дампа БД: {e}")
    return None


def _export_db_to_json(tmp_dir: str) -> str | None:
    """Экспорт всех таблиц БД в JSON как универсальный фолбэк для бэкапа."""
    try:
        import json

        from database import db

        insp = inspect(db.engine)
        tables = insp.get_table_names()
        result: dict[str, list[dict]] = {}
        with db.engine.connect() as conn:
            for t in tables:
                try:
                    rows = conn.execute(text(f'SELECT * FROM "{t}"')).mappings().all()
                    result[t] = [dict(r) for r in rows]
                except Exception as te:  # noqa: BLE001
                    current_app.logger.warning(
                        f"Не удалось экспортировать таблицу {t}: {te}"
                    )
        out_path = os.path.join(tmp_dir, "db_dump.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, default=str)
        return out_path
    except Exception as e:  # noqa: BLE001
        current_app.logger.error(f"Ошибка экспорта БД в JSON: {e}")
        return None


@admin_bp.route("/admin/backup", methods=["POST"])
@login_required
def create_backup():
    """Создать архив с бэкапом БД и вложений и отдать на скачивание."""
    if getattr(current_user, "role", None) != "admin":
        flash("Доступ запрещён", "danger")
        return redirect(url_for("main.index"))

    # Временная рабочая директория
    base_tmp = os.path.join(current_app.root_path, "tmp")
    os.makedirs(base_tmp, exist_ok=True)
    work_dir = tempfile.mkdtemp(prefix="backup_", dir=base_tmp)
    os.makedirs(work_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(work_dir, f"crm_backup_{ts}.zip")

    db_item_path: str | None = None
    attachments_root = current_app.config.get(
        "UPLOAD_FOLDER", os.path.join(current_app.root_path, "static", "uploads")
    )

    try:
        # 1) Бэкап БД
        sqlite_path = _sqlite_db_path()
        if sqlite_path and os.path.isfile(sqlite_path):
            # Копируем файл SQLite
            db_copy = os.path.join(work_dir, f"app_{ts}.sqlite")
            shutil.copy2(sqlite_path, db_copy)
            db_item_path = db_copy
            current_app.logger.info("Скопирован файл SQLite для бэкапа")
        else:
            # Пытаемся сделать SQL‑дамп для MySQL/Postgres
            dump_path = _dump_rdbms_to_sql(work_dir)
            if dump_path:
                db_item_path = dump_path
                current_app.logger.info("Создан SQL‑дамп БД для бэкапа")
            else:
                # Универсальный фолбэк — JSON экспорт
                json_path = _export_db_to_json(work_dir)
                if json_path:
                    db_item_path = json_path
                    current_app.logger.info("Создан JSON‑дамп БД для бэкапа")

        # 2) Формирование ZIP
        with ZipFile(zip_path, mode="w", compression=ZIP_DEFLATED) as zf:
            # БД
            if db_item_path and os.path.isfile(db_item_path):
                arcname = os.path.join("db", os.path.basename(db_item_path)).replace(
                    "\\", "/"
                )
                zf.write(db_item_path, arcname)

            # Вложения (uploads)
            if os.path.isdir(attachments_root):
                for root, _dirs, files in os.walk(attachments_root):
                    for name in files:
                        full_path = os.path.join(root, name)
                        rel = os.path.relpath(full_path, attachments_root)
                        arcname = os.path.join("attachments", rel).replace("\\", "/")
                        try:
                            zf.write(full_path, arcname)
                        except Exception as fe:  # noqa: BLE001
                            current_app.logger.warning(
                                (
                                    "Не удалось добавить файл во вложениях: "
                                    f"{full_path}: {fe}"
                                )
                            )

        # 3) Отдаём на скачивание
        @after_this_request
        def _cleanup_tmp(response):  # noqa: D401
            """Удаление временных файлов бэкапа после ответа."""
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
            return response

        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=os.path.basename(zip_path),
            max_age=0,
        )
    except Exception as e:  # noqa: BLE001
        current_app.logger.error(f"Ошибка создания бэкапа: {e}")
        flash("Не удалось создать бэкап", "danger")
        return redirect(url_for("main.index"))


@admin_bp.route("/admin/generate-demo-data", methods=["POST"])
@login_required
def generate_demo_data_action():
    """Создаёт демо-данные в базе, если заявок ещё меньше порога."""
    if getattr(current_user, "role", None) != "admin":
        flash("Доступ запрещён", "danger")
        return redirect(url_for("main.index"))

    contractors_target = int(current_app.config.get("DEMO_SEED_CONTRACTORS", 3000))
    objects_target = int(current_app.config.get("DEMO_SEED_OBJECTS", 2000))
    requests_target = int(current_app.config.get("DEMO_SEED_REQUESTS", 5000))

    from utils.demo_seed import generate_demo_data  # локальный импорт

    try:
        result = generate_demo_data(
            contractors_target,
            objects_target,
            requests_target,
            logger=current_app.logger,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Ошибка генерации демо-данных: {0}".format(exc))
        from database import db

        db.session.rollback()
        flash("Не удалось сгенерировать тестовую БД", "danger")
        return redirect(url_for("main.index"))

    if result.skipped:
        flash(
            (
                "В БД уже есть {count} или больше заявок, генерация пропущена."
            ).format(count=requests_target),
            "info",
        )
        return redirect(url_for("main.index"))

    flash(
        (
            "Сгенерирована тестовая БД: заявки +{req}, объекты +{obj}, "
            "подрядчики +{cont}, комментарии +{com}."
        ).format(
            req=result.created_requests,
            obj=result.created_objects,
            cont=result.created_contractors,
            com=result.created_comments,
        ),
        "success",
    )
    return redirect(url_for("main.index"))


def _human_size(n: int) -> str:
    try:
        units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
        size = float(n)
        i = 0
        while size >= 1024 and i < len(units) - 1:
            size /= 1024.0
            i += 1
        return ("{:.0f} {}" if size.is_integer() else "{:.1f} {}").format(
            size, units[i]
        )
    except Exception:
        return str(n)


def _read_meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                parts = v.strip().split()
                if parts:
                    try:
                        out[k] = int(parts[0])  # КБ
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def _uptime_seconds() -> int | None:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            val = float(f.read().split()[0])
            return int(val)
    except Exception:
        return None


def _format_duration(sec: int | None) -> str:
    if sec is None:
        return "—"
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    parts = []
    if d:
        parts.append(f"{d} д")
    if h:
        parts.append(f"{h} ч")
    parts.append(f"{m} м")
    return " ".join(parts)


def _db_counts() -> tuple[dict[str, int], int]:
    from database import db  # локальный импорт

    counts: dict[str, int] = {}
    total = 0
    try:
        insp = inspect(db.engine)
        tables = insp.get_table_names()
        dialect = db.engine.dialect.name

        def quote(name: str) -> str:
            if dialect == "mysql":
                return f"`{name}`"
            elif dialect == "postgresql":
                return f'"{name}"'
            else:
                return f'"{name}"'

        with db.engine.connect() as conn:
            for t in tables:
                try:
                    q = text(f"SELECT COUNT(*) AS c FROM {quote(t)}")
                    c = conn.execute(q).scalar() or 0
                    counts[t] = int(c)
                    total += int(c)
                except Exception as e:
                    current_app.logger.warning(f"COUNT(*) для {t} не выполнен: {e}")
    except Exception as e:
        current_app.logger.warning(f"Не удалось получить список таблиц: {e}")
    return counts, total


@admin_bp.route("/admin/system")
@login_required
def system_page():
    if getattr(current_user, "role", None) != "admin":
        flash("Доступ запрещён", "danger")
        return redirect(url_for("main.index"))

    mi = _read_meminfo()
    mem_total_b = mi.get("MemTotal", 0) * 1024
    mem_avail_b = mi.get("MemAvailable", 0) * 1024
    mem_used_b = max(mem_total_b - mem_avail_b, 0)
    mem_used_percent = round(mem_used_b / mem_total_b * 100, 1) if mem_total_b else 0.0
    if mem_used_percent >= 90:
        mem_status = "danger"
    elif mem_used_percent >= 75:
        mem_status = "warning"
    else:
        mem_status = "success"

    swap_total_b = mi.get("SwapTotal", 0) * 1024
    swap_free_b = mi.get("SwapFree", 0) * 1024
    swap_used_b = max(swap_total_b - swap_free_b, 0)
    swap_used_percent = (
        round(swap_used_b / swap_total_b * 100, 1) if swap_total_b else 0.0
    )
    if swap_total_b == 0:
        swap_status = "muted"
    elif swap_used_percent >= 80:
        swap_status = "danger"
    elif swap_used_percent >= 50:
        swap_status = "warning"
    else:
        swap_status = "success"

    try:
        load1, load5, load15 = os.getloadavg()  # type: ignore[attr-defined]
    except Exception:
        load1 = load5 = load15 = 0.0
    cpu_count = os.cpu_count() or 1
    load_per_cpu = {
        "1m": round(load1 / cpu_count, 2) if cpu_count else 0.0,
        "5m": round(load5 / cpu_count, 2) if cpu_count else 0.0,
        "15m": round(load15 / cpu_count, 2) if cpu_count else 0.0,
    }
    load_metric = load_per_cpu["1m"]
    if load_metric >= 1.2:
        load_status = "danger"
    elif load_metric >= 0.7:
        load_status = "warning"
    else:
        load_status = "success"
    up = _uptime_seconds()
    started_at_str = ""
    if up:
        started = datetime.now() - timedelta(seconds=up)
        started_at_str = started.strftime("%d.%m.%Y %H:%M:%S")

    try:
        du_total, _du_used, du_free = _shutil.disk_usage("/")
        du_used = du_total - du_free
        du_used_percent = round(du_used / du_total * 100, 1) if du_total else 0.0
    except Exception:
        du_total = du_free = du_used = 0
        du_used_percent = 0.0
    if du_total:
        if du_used_percent >= 90:
            disk_status = "danger"
        elif du_used_percent >= 75:
            disk_status = "warning"
        else:
            disk_status = "success"
    else:
        disk_status = "muted"

    table_counts, rows_total = _db_counts()
    tables_sorted = sorted(table_counts.items(), key=lambda item: item[1], reverse=True)
    top_tables = tables_sorted[:5]
    tables_alpha = sorted(table_counts.items())

    py_ver = platform.python_version()
    python_impl = platform.python_implementation()
    try:
        with open(
            os.path.join(current_app.root_path, "VERSION"), encoding="utf-8"
        ) as vf:
            app_ver = vf.read().strip()
    except Exception:
        app_ver = ""
    try:
        from database import db

        url = db.engine.url
        db_backend = url.get_backend_name()
        host_part = ""
        if url.host:
            host_part = str(url.host)
            if url.port:
                host_part += f":{url.port}"
        db_dsn = f"{db_backend}://{host_part or 'localhost'}/{url.database or ''}"
    except Exception:
        db_backend = "unknown"
        db_dsn = ""
    try:
        from importlib import metadata as importlib_metadata  # type: ignore[import]
    except Exception:
        importlib_metadata = None  # type: ignore[assignment]

    flask_version = ""
    werkzeug_version = ""
    if importlib_metadata:
        try:
            flask_version = importlib_metadata.version("Flask")
        except Exception:
            pass
        try:
            werkzeug_version = importlib_metadata.version("Werkzeug")
        except Exception:
            pass

    redis_available = bool(current_app.config.get("REDIS_AVAILABLE", False))

    data = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "os_pretty": platform.platform(),
        "host": {
            "hostname": platform.node(),
            "machine": platform.machine(),
            "kernel": platform.release(),
            "architecture": " ".join(part for part in platform.architecture() if part),
        },
        "python": py_ver,
        "python_impl": python_impl,
        "framework": {
            "flask": flask_version,
            "werkzeug": werkzeug_version,
        },
        "app_version": app_ver,
        "uptime": _format_duration(up),
        "uptime_details": {
            "seconds": up or 0,
            "started_at": started_at_str,
        },
        "load": {
            "1m": round(load1, 2),
            "5m": round(load5, 2),
            "15m": round(load15, 2),
            "per_cpu": load_per_cpu,
            "cpu_count": cpu_count,
            "status": load_status,
        },
        "memory": {
            "total": _human_size(mem_total_b),
            "available": _human_size(mem_avail_b),
            "used": _human_size(mem_used_b),
            "total_bytes": mem_total_b,
            "available_bytes": mem_avail_b,
            "used_bytes": mem_used_b,
            "used_percent": mem_used_percent,
            "free_percent": round(100 - mem_used_percent, 1) if mem_total_b else 0.0,
            "status": mem_status,
        },
        "swap": {
            "total": _human_size(swap_total_b),
            "free": _human_size(swap_free_b),
            "used": _human_size(swap_used_b),
            "total_bytes": swap_total_b,
            "free_bytes": swap_free_b,
            "used_bytes": swap_used_b,
            "used_percent": swap_used_percent,
            "free_percent": round(100 - swap_used_percent, 1) if swap_total_b else 0.0,
            "status": swap_status,
        },
        "disk": {
            "path": "/",
            "root_total": _human_size(du_total),
            "root_free": _human_size(du_free),
            "used": _human_size(du_used),
            "total_bytes": du_total,
            "free_bytes": du_free,
            "used_bytes": du_used,
            "used_percent": du_used_percent,
            "status": disk_status,
        },
        "db": {
            "backend": db_backend,
            "dsn": db_dsn,
            "tables": table_counts,
            "rows_total": rows_total,
            "tables_sorted": tables_alpha,
            "top_tables": top_tables,
        },
        "redis_available": redis_available,
    }

    return render_template("admin/system.html", data=data)

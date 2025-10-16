from datetime import datetime
from pathlib import Path

import click
from flask import current_app

from database import db
from models import Attachment, Request


def register_cleanup_commands(app):
    """Регистрация CLI-команд очистки."""

    @app.cli.command("cleanup:sessions")
    @click.option(
        "--dry-run/--no-dry-run", default=True, help="Только отчёт без удаления"
    )
    def cleanup_sessions(dry_run: bool):
        """Удаляет файловые сессии старше `PERMANENT_SESSION_LIFETIME`."""
        if current_app.config.get("SESSION_TYPE") != "filesystem":
            current_app.logger.info(
                "Файловые сессии не используются, очистка не требуется"
            )
            return

        session_dir = Path(current_app.config.get("SESSION_FILE_DIR", ""))
        if not session_dir.exists():
            current_app.logger.info("Каталог сессий не найден")
            return

        lifetime = current_app.permanent_session_lifetime
        now = datetime.utcnow()
        checked = removed = 0

        for path in session_dir.glob("*"):
            if not path.is_file():
                continue
            checked += 1
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
            if now - mtime > lifetime:
                if dry_run:
                    current_app.logger.info(f"Удаление {path} (dry-run)")
                else:
                    try:
                        path.unlink()
                        removed += 1
                        current_app.logger.info(f"Удалён {path}")
                    except OSError as e:
                        current_app.logger.error(f"Не удалось удалить {path}: {e}")

        current_app.logger.info(f"Проверено файлов: {checked}, удалено: {removed}")

    @app.cli.command("cleanup:uploads")
    @click.option(
        "--dry-run/--no-dry-run", default=True, help="Только отчёт без удаления"
    )
    def cleanup_uploads(dry_run: bool):
        """Находит и удаляет файлы без записей в БД."""
        upload_root = Path(current_app.config["UPLOAD_FOLDER"])
        if not upload_root.exists():
            current_app.logger.info("Каталог загрузок не найден")
            return

        static_root = upload_root.parent
        db_paths = set()

        # Сбор путей из Request.file_path
        for (file_paths,) in db.session.query(Request.file_path).all():
            if not file_paths:
                continue
            for rel in file_paths.split(","):
                db_paths.add((static_root / rel).resolve())

        # Сбор путей из Attachment.screenshot
        for (rel_path,) in db.session.query(Attachment.screenshot).all():
            if rel_path:
                db_paths.add((static_root / rel_path).resolve())

        checked = removed = 0
        for file in upload_root.rglob("*"):
            if not file.is_file():
                continue
            checked += 1
            if file.resolve() not in db_paths:
                if dry_run:
                    current_app.logger.info(f"Осиротевший файл: {file} (dry-run)")
                else:
                    try:
                        file.unlink()
                        removed += 1
                        current_app.logger.info(f"Удалён {file}")
                    except OSError as e:
                        current_app.logger.error(f"Не удалось удалить {file}: {e}")

        current_app.logger.info(f"Проверено файлов: {checked}, удалено: {removed}")

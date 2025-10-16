import os
from datetime import timedelta
from pathlib import Path

from models import Object, Request, User


def test_cleanup_sessions(tmp_path, app):
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    old_type = app.config.get("SESSION_TYPE")
    old_dir = app.config.get("SESSION_FILE_DIR")
    old_lifetime = app.permanent_session_lifetime
    try:
        app.config["SESSION_TYPE"] = "filesystem"
        app.config["SESSION_FILE_DIR"] = str(session_dir)
        app.permanent_session_lifetime = timedelta(seconds=1)

        old_file = session_dir / "old.sess"
        old_file.write_text("1")
        new_file = session_dir / "new.sess"
        new_file.write_text("2")
        os.utime(old_file, (0, 0))

        runner = app.test_cli_runner()
        runner.invoke(args=["cleanup:sessions"])
        assert old_file.exists()
        assert new_file.exists()

        runner.invoke(args=["cleanup:sessions", "--no-dry-run"])
        assert not old_file.exists()
        assert new_file.exists()
    finally:
        app.config["SESSION_TYPE"] = old_type
        if old_dir is not None:
            app.config["SESSION_FILE_DIR"] = old_dir
        app.permanent_session_lifetime = old_lifetime


def test_cleanup_uploads(tmp_path, app, db):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    old_upload = app.config.get("UPLOAD_FOLDER")
    try:
        app.config["UPLOAD_FOLDER"] = str(upload_dir)

        obj = Object(name="O")
        user = User(username="u", password="p", role="admin")
        db.session.add_all([obj, user])
        db.session.commit()

        req = Request(object_id=obj.id, manufacturers="m", created_by=user.id)
        db.session.add(req)
        db.session.commit()
        kept_rel = f"uploads/{req.id}/kept.txt"
        req.file_path = kept_rel
        db.session.commit()

        kept_file = Path(app.config["UPLOAD_FOLDER"]) / str(req.id) / "kept.txt"
        kept_file.parent.mkdir(parents=True, exist_ok=True)
        kept_file.write_text("a")
        orphan_file = Path(app.config["UPLOAD_FOLDER"]) / "orphan.txt"
        orphan_file.write_text("b")

        runner = app.test_cli_runner()
        runner.invoke(args=["cleanup:uploads"])
        assert orphan_file.exists()
        assert kept_file.exists()

        runner.invoke(args=["cleanup:uploads", "--no-dry-run"])
        assert not orphan_file.exists()
        assert kept_file.exists()
    finally:
        if old_upload is not None:
            app.config["UPLOAD_FOLDER"] = old_upload

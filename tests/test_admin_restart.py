import os
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

# Добавляем корень проекта в PYTHONPATH
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))


@pytest.fixture()
def client_with_admin():
    os.environ["FLASK_ENV"] = "testing"
    from app import app
    from database import db
    from models import User

    with app.app_context():
        db.create_all()
        user = User(
            username="admin", password=generate_password_hash("pass"), role="admin"
        )
        db.session.add(user)
        db.session.commit()
        app.config["ALLOW_SYSTEMCTL_RESTART"] = True
        app.config["SYSTEMD_SERVICE_NAME"] = "crm.service"
        app.config["APP_RESTART_COMMAND"] = ""
        app.config["DEPLOY_RESTART_COMMAND"] = ""
        client = app.test_client()
        client.post("/auth/login", data={"username": "admin", "password": "pass"})
        yield client
        db.session.remove()
        db.drop_all()
        sys.modules.pop("app", None)


@pytest.fixture()
def client_with_user():
    os.environ["FLASK_ENV"] = "testing"
    from app import app
    from database import db
    from models import User

    with app.app_context():
        db.create_all()
        user = User(
            username="user", password=generate_password_hash("pass"), role="user"
        )
        db.session.add(user)
        db.session.commit()
        app.config["ALLOW_SYSTEMCTL_RESTART"] = True
        app.config["SYSTEMD_SERVICE_NAME"] = "crm.service"
        app.config["APP_RESTART_COMMAND"] = ""
        app.config["DEPLOY_RESTART_COMMAND"] = ""
        client = app.test_client()
        client.post("/auth/login", data={"username": "user", "password": "pass"})
        yield client
        db.session.remove()
        db.drop_all()
        sys.modules.pop("app", None)


def test_admin_restart_invokes_systemctl(monkeypatch, client_with_admin):
    from routes import admin_routes

    called = {}

    def fake_run(command: str) -> None:
        called["command"] = command

    monkeypatch.setattr(admin_routes, "_run_restart_command", fake_run)

    resp = client_with_admin.post("/admin/restart")

    assert resp.status_code == 302
    assert called["command"] == "systemctl restart crm.service"


def test_admin_restart_uses_custom_command(monkeypatch, client_with_admin):
    from app import app as app_module
    from routes import admin_routes

    app_module.config["APP_RESTART_COMMAND"] = "sudo systemctl restart {service}"

    called = {}

    def fake_run(command: str) -> None:
        called["command"] = command

    monkeypatch.setattr(admin_routes, "_run_restart_command", fake_run)

    resp = client_with_admin.post("/admin/restart")

    assert resp.status_code == 302
    assert called["command"] == "sudo systemctl restart crm.service"


def test_admin_restart_uses_deploy_command(monkeypatch, client_with_admin):
    from app import app as app_module
    from routes import admin_routes

    app_module.config["APP_RESTART_COMMAND"] = ""
    app_module.config["DEPLOY_RESTART_COMMAND"] = "sudo systemctl restart {service}"
    app_module.config["ALLOW_SYSTEMCTL_RESTART"] = False

    called = {}

    def fake_run(command: str) -> None:
        called["command"] = command

    monkeypatch.setattr(admin_routes, "_run_restart_command", fake_run)

    resp = client_with_admin.post("/admin/restart")

    assert resp.status_code == 302
    assert called["command"] == "sudo systemctl restart crm.service"


def test_restart_without_permissions(monkeypatch, client_with_admin):
    from app import app as app_module
    from routes import admin_routes

    app_module.config["ALLOW_SYSTEMCTL_RESTART"] = False
    app_module.config["APP_RESTART_COMMAND"] = ""

    monkeypatch.setattr(
        admin_routes,
        "_run_restart_command",
        lambda command: (_ for _ in ()).throw(RuntimeError("should not be called")),
    )

    resp = client_with_admin.post("/admin/restart")

    assert resp.status_code == 302


def test_non_admin_cannot_restart(monkeypatch, client_with_user):
    from routes import admin_routes

    monkeypatch.setattr(
        admin_routes,
        "_run_restart_command",
        lambda command: (_ for _ in ()).throw(RuntimeError("should not be called")),
    )

    resp = client_with_user.post("/admin/restart")

    assert resp.status_code == 302


def test_admin_restart_legacy_script(monkeypatch, client_with_admin):
    from app import app as app_module
    from routes import admin_routes

    script_path = Path(app_module.root_path) / ".restart-app"
    backup = None
    if script_path.exists():
        backup = script_path.read_bytes()
    script_path.write_text("#!/bin/sh\necho ok\n")
    script_path.chmod(0o755)

    app_module.config["APP_RESTART_COMMAND"] = ""
    app_module.config["DEPLOY_RESTART_COMMAND"] = ""
    app_module.config["ALLOW_SYSTEMCTL_RESTART"] = False

    called = {}

    def fake_run(command: str) -> None:
        called["command"] = command

    monkeypatch.setattr(admin_routes, "_run_restart_command", fake_run)

    try:
        resp = client_with_admin.post("/admin/restart")
        assert resp.status_code == 302
        assert Path(called["command"]) == script_path
    finally:
        if backup is None and script_path.exists():
            script_path.unlink()
        elif backup is not None:
            script_path.write_bytes(backup)


def test_admin_restart_legacy_script_not_executable(
    monkeypatch, client_with_admin
):
    from app import app as app_module
    from routes import admin_routes

    script_path = Path(app_module.root_path) / ".restart-app"
    backup = None
    if script_path.exists():
        backup = script_path.read_bytes()
    script_path.write_text("#!/bin/sh\necho ok\n")
    script_path.chmod(0o644)

    app_module.config["APP_RESTART_COMMAND"] = ""
    app_module.config["DEPLOY_RESTART_COMMAND"] = ""
    app_module.config["ALLOW_SYSTEMCTL_RESTART"] = False

    called = {}

    def fake_run(command: str) -> None:
        called["command"] = command

    monkeypatch.setattr(admin_routes, "_run_restart_command", fake_run)

    try:
        resp = client_with_admin.post("/admin/restart")
        assert resp.status_code == 302
        assert called["command"].startswith("/bin/sh ")
        assert str(script_path) in called["command"]
    finally:
        if backup is None and script_path.exists():
            script_path.unlink()
        elif backup is not None:
            script_path.write_bytes(backup)

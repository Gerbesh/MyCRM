import os

from flask import Blueprint, abort, jsonify, render_template
from flask_login import current_user, login_required

admin_logs_bp = Blueprint("admin_logs", __name__, template_folder="../templates")

LOG_FILE_PATH = os.path.join(os.getcwd(), "logs", "audit.log")


def tail(path, max_lines=200):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ РїРѕСЃР»РµРґРЅРёРµ СЃС‚СЂРѕРєРё С„Р°Р№Р»Р°."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        block = -1024
        data = b""
        while -block < size:
            f.seek(block, os.SEEK_END)
            data = f.read(-block) + data
            if data.count(b"\n") > max_lines:
                break
            block *= 2
        return data.decode("utf-8", errors="replace").splitlines()[-max_lines:]


@admin_logs_bp.route("/admin/logs")
@login_required
def logs_page():
    if getattr(current_user, "role", "") != "admin":
        abort(403)
    return render_template("admin/logs.html")


@admin_logs_bp.route("/admin/logs/data")
@login_required
def logs_data():
    if getattr(current_user, "role", "") != "admin":
        abort(403)
    lines = tail(LOG_FILE_PATH, max_lines=300)
    return jsonify({"lines": lines})

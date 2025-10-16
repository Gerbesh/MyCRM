"""Blueprint модуля OP."""

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

op_bp = Blueprint("op", __name__)


def _check_role(allow_demo: bool = False) -> None:
    """Разрешены только администраторы и менеджеры."""
    if allow_demo and getattr(current_user, "role", None) == "demo":
        return
    allowed_roles = {"admin", "manager"}
    if current_user.role not in allowed_roles:
        abort(403)


@op_bp.route("/op")
@login_required
def op_index():
    """Страница модуля OP."""
    _check_role(allow_demo=True)
    return render_template("op/index.html", obj=None)


@op_bp.route("/op/<int:object_id>")
@login_required
def op_object(object_id: int):
    """Страница OP с предзагруженным объектом."""
    _check_role(allow_demo=True)
    from models import Object  # локальный импорт, чтобы избежать циклов

    obj = Object.query.get_or_404(object_id)
    return render_template("op/index.html", obj=obj)

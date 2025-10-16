"""
Маршруты для управления пользователями
"""

import logging
import random
import string

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

from models import Request, User, db
from security_utils import safe_log, validate_password_strength

user_bp = Blueprint("user", __name__)


@user_bp.route("/")
@login_required
def users():
    try:
        safe_log(
            current_app.logger,
            logging.DEBUG,
            f"Accessing users route by user {current_user.username}",
        )

        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            safe_log(
                current_app.logger,
                logging.WARNING,
                f"Unauthorized access to users route by {current_user.username}",
            )
            return redirect(url_for("main.dashboard"))

        users = User.query.all()
        reset_password_base = url_for("user.reset_user_password", id=0)[:-1]
        return render_template(
            "users.html", users=users, RESET_USER_PASSWORD_BASE=reset_password_base
        )
    except Exception as e:
        safe_log(current_app.logger, logging.ERROR, f"Error in users route: {str(e)}")
        flash("Произошла ошибка", "danger")
        return redirect(url_for("main.dashboard")), 500


@user_bp.route("/add_user", methods=["POST"])
@login_required
def add_user():
    """Добавление нового пользователя"""
    try:
        if current_user.role != "admin":
            safe_log(
                current_app.logger,
                logging.WARNING,
                f"Unauthorized add_user attempt by {current_user.username}",
            )
            return jsonify({"error": "Доступ запрещен"}), 403

        # Получение данных
        data = request.get_json()
        if not data:
            data = request.form

        username = data.get("username")
        password = data.get("password")
        role = data.get("role")

        if not username or not password or not role:
            return jsonify({"error": "Все поля обязательны"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Пользователь с таким именем уже существует"}), 400

        valid, error = validate_password_strength(password)
        if not valid:
            return jsonify({"error": error}), 400

        from werkzeug.security import generate_password_hash

        new_user = User(
            username=username, password=generate_password_hash(password), role=role
        )
        db.session.add(new_user)
        db.session.commit()
        safe_log(
            current_app.logger,
            logging.INFO,
            f"User {username} created by {current_user.username}",
        )
        return jsonify({"success": True, "password": password})
    except Exception as e:
        db.session.rollback()
        safe_log(
            current_app.logger, logging.ERROR, f"Error in add_user route: {str(e)}"
        )
        return jsonify({"error": "Произошла ошибка"}), 500


@user_bp.route("/edit_user/<int:id>", methods=["GET", "POST"])
@login_required
def edit_user(id):
    try:
        safe_log(
            current_app.logger,
            logging.DEBUG,
            f"Accessing edit_user route for id {id} by user {current_user.username}",
        )

        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            safe_log(
                current_app.logger,
                logging.WARNING,
                f"Unauthorized edit_user access for id {id} by {current_user.username}",
            )
            return redirect(url_for("user.users"))

        user = User.query.get_or_404(id)

        if request.method == "POST":
            from werkzeug.security import generate_password_hash

            username = request.form.get("username")
            role = request.form.get("role")
            password = request.form.get("password")

            if not username or not role:
                flash("Заполните обязательные поля", "danger")
                return render_template("edit_user.html", user=user)

            if User.query.filter_by(username=username).filter(User.id != id).first():
                flash("Пользователь с таким именем уже существует", "danger")
                return render_template("edit_user.html", user=user)

            user.username = username
            user.role = role
            if password:
                valid, error = validate_password_strength(password)
                if not valid:
                    flash(error, "danger")
                    return render_template("edit_user.html", user=user)
                user.password = generate_password_hash(password)

            db.session.commit()
            flash("Пользователь успешно обновлен", "success")
            return redirect(url_for("user.users"))

        return render_template("edit_user.html", user=user)
    except Exception as e:
        db.session.rollback()
        safe_log(
            current_app.logger,
            logging.ERROR,
            f"Error in edit_user route for id {id}: {str(e)}",
        )
        flash("Произошла ошибка", "danger")
        return redirect(url_for("user.users")), 500


@user_bp.route("/delete_user/<int:id>", methods=["POST"])
@login_required
def delete_user(id):
    """Удаление пользователя"""
    try:
        if current_user.role != "admin":
            flash("Доступ запрещен", "danger")
            safe_log(
                current_app.logger,
                logging.WARNING,
                (
                    f"Unauthorized delete_user attempt for id {id} by "
                    f"{current_user.username}"
                ),
            )
            return redirect(url_for("user.users"))

        if id == current_user.id:
            flash("Нельзя удалить самого себя", "danger")
            return redirect(url_for("user.users"))

        user = User.query.get_or_404(id)

        # Проверяем, есть ли связанные заявки
        requests = Request.query.filter_by(created_by=id).first()
        if requests:
            flash("Нельзя удалить пользователя, так как он связан с заявками", "danger")
            return redirect(url_for("user.users"))

        db.session.delete(user)
        db.session.commit()
        flash("Пользователь удален", "success")
        return redirect(url_for("user.users"))
    except Exception as e:
        db.session.rollback()
        safe_log(
            current_app.logger,
            logging.ERROR,
            f"Error in delete_user route for id {id}: {str(e)}",
        )
        flash("Ошибка при удалении пользователя", "danger")
        return redirect(url_for("user.users")), 500


@user_bp.route("/reset_user_password/<int:id>", methods=["POST"])
@login_required
def reset_user_password(id):
    """Сброс пароля пользователя"""
    try:
        if current_user.role != "admin":
            safe_log(
                current_app.logger,
                logging.WARNING,
                (
                    f"Unauthorized reset_user_password attempt for id {id} by "
                    f"{current_user.username}"
                ),
            )
            return jsonify({"error": "Доступ запрещен"}), 403
        if id == current_user.id:
            safe_log(
                current_app.logger,
                logging.WARNING,
                f"{current_user.username} attempted to reset own password",
            )
            return jsonify({"error": "Нельзя сбросить пароль самому себе"}), 403

        user = User.query.get_or_404(id)
        new_password = "".join(
            random.choices(string.ascii_letters + string.digits, k=8)
        )

        from werkzeug.security import generate_password_hash

        user.password = generate_password_hash(new_password)
        db.session.commit()

        safe_log(
            current_app.logger,
            logging.INFO,
            f"Password reset for user {user.username} by {current_user.username}",
        )
        return jsonify({"success": True, "new_password": new_password})
    except Exception as e:
        db.session.rollback()
        safe_log(
            current_app.logger,
            logging.ERROR,
            f"Error in reset_user_password route: {str(e)}",
        )
        return jsonify({"error": "Произошла ошибка"}), 500

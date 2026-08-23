from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User
from app.utils import log_activity

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", email=email), 401

        if not user.is_active:
            flash("Your account has been deactivated. Contact an administrator.", "error")
            return render_template("auth/login.html", email=email), 403

        login_user(user)
        user.touch_activity()
        log_activity(user, "user_login", f"{user.name} logged in.")
        db.session.commit()

        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard.index"))

    return render_template("auth/login.html", email="")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_activity(current_user, "user_logout", f"{current_user.name} logged out.")
    db.session.commit()
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
        elif new_password != confirm_password:
            flash("New passwords don't match.", "error")
        else:
            current_user.set_password(new_password)
            log_activity(current_user, "password_changed", f"{current_user.name} changed their password.")
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("profile.settings"))

    return render_template("auth/change_password.html")

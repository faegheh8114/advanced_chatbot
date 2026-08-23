from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Ticket
from app.utils import log_activity

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/", methods=["GET", "POST"])
@login_required
def view():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name cannot be empty.", "error")
        else:
            current_user.name = name
            log_activity(current_user, "profile_updated", f"{current_user.name} updated their profile.")
            db.session.commit()
            flash("Profile updated.", "success")
        return redirect(url_for("profile.view"))

    ticket_count = Ticket.query.filter_by(creator_id=current_user.id).count()
    assigned_count = Ticket.query.filter_by(assignee_id=current_user.id).count()
    return render_template("profile/view.html", ticket_count=ticket_count, assigned_count=assigned_count)


@profile_bp.route("/settings")
@login_required
def settings():
    return render_template("profile/settings.html")

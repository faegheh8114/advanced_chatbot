import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.decorators import admin_required
from app.models import (
    User, Department, Category, Ticket, ActivityLog, Role, TicketStatus, TicketPriority,
)
from app.utils import log_activity
from app.blueprints.tickets import apply_filters

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_tickets = Ticket.query.count()

    counts = {
        status: Ticket.query.filter_by(status=status).count() for status in TicketStatus.ORDER
    }
    urgent_tickets = Ticket.query.filter(
        Ticket.priority == TicketPriority.URGENT, Ticket.status.in_(TicketStatus.ACTIVE)
    ).count()
    unread_requests = Ticket.query.filter(Ticket.status == TicketStatus.OPEN).count()

    recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(12).all()
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        total_tickets=total_tickets,
        counts=counts,
        urgent_tickets=urgent_tickets,
        unread_requests=unread_requests,
        recent_activity=recent_activity,
        departments=departments,
    )


@admin_bp.route("/tickets")
@login_required
@admin_required
def tickets():
    query = apply_filters(Ticket.query)
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template(
        "tickets/list.html",
        tickets=pagination.items,
        pagination=pagination,
        title="All Tickets",
        empty_hint="No tickets match these filters.",
        endpoint="admin.tickets",
        categories=Category.query.filter_by(is_active=True).order_by(Category.name).all(),
        departments=Department.query.filter_by(is_active=True).order_by(Department.name).all(),
    )


@admin_bp.route("/reports")
@login_required
@admin_required
def reports():
    all_departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    return render_template("admin/reports.html", departments=all_departments)


@admin_bp.route("/activity-logs")
@login_required
@admin_required
def activity_logs():
    page = request.args.get("page", 1, type=int)
    query = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    action = request.args.get("action")
    if action:
        query = query.filter(ActivityLog.action == action)
    pagination = query.paginate(page=page, per_page=30, error_out=False)
    action_types = [row[0] for row in db.session.query(ActivityLog.action).distinct().all()]
    return render_template(
        "admin/activity_logs.html", pagination=pagination, logs=pagination.items,
        action_types=sorted(action_types), selected_action=action,
    )


@admin_bp.route("/settings")
@login_required
@admin_required
def settings():
    return render_template("admin/settings.html")


# ---------------------------------------------------------------- Users ----

@admin_bp.route("/users")
@login_required
@admin_required
def users():
    query = User.query
    q = request.args.get("q", "").strip()
    role = request.args.get("role")
    department_id = request.args.get("department", type=int)
    status = request.args.get("status")

    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    if role:
        query = query.filter(User.role == role)
    if department_id:
        query = query.filter(User.department_id == department_id)
    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active.is_(False))

    sort = request.args.get("sort", "name")
    if sort == "recent":
        query = query.order_by(User.created_at.desc())
    elif sort == "activity":
        query = query.order_by(User.last_active_at.desc().nullslast())
    else:
        query = query.order_by(User.name.asc())

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        "admin/users.html",
        pagination=pagination,
        users=pagination.items,
        departments=Department.query.order_by(Department.name).all(),
    )


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def user_create():
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        role = request.form.get("role")
        department_id = request.form.get("department_id", type=int)
        password = request.form.get("password") or ""

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        elif User.query.filter_by(email=email).first():
            errors.append("A user with this email already exists.")
        if role not in Role.ALL:
            errors.append("Invalid role.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if role != Role.SUPER_ADMIN and not department_id:
            errors.append("Department is required for this role.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/user_form.html", departments=departments, user=None, form=request.form)

        user = User(name=name, email=email, role=role, department_id=department_id or None)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        log_activity(current_user, "user_created", f"{current_user.name} created user {user.name} ({Role.LABELS[role]}).",
                     target_type="user", target_id=user.id)
        db.session.commit()
        flash(f"User {user.name} created.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", departments=departments, user=None, form={})


@admin_bp.route("/users/<int:user_id>")
@login_required
@admin_required
def user_detail(user_id):
    user = db.session.get(User, user_id) or abort(404)
    tickets_created = Ticket.query.filter_by(creator_id=user.id).order_by(Ticket.created_at.desc()).limit(10).all()
    tickets_assigned = Ticket.query.filter_by(assignee_id=user.id).order_by(Ticket.created_at.desc()).limit(10).all()
    activity = ActivityLog.query.filter_by(actor_id=user.id).order_by(ActivityLog.created_at.desc()).limit(20).all()
    return render_template(
        "admin/user_detail.html", user=user, tickets_created=tickets_created,
        tickets_assigned=tickets_assigned, activity=activity,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def user_edit(user_id):
    user = db.session.get(User, user_id) or abort(404)
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        role = request.form.get("role")
        department_id = request.form.get("department_id", type=int)

        errors = []
        if not name:
            errors.append("Name is required.")
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        elif existing:
            errors.append("Another user already uses this email.")
        if role not in Role.ALL:
            errors.append("Invalid role.")
        if role == Role.SUPER_ADMIN and current_user.role != Role.SUPER_ADMIN:
            errors.append("Only a Super Admin can assign the Super Admin role.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/user_form.html", departments=departments, user=user, form=request.form)

        user.name = name
        user.email = email
        user.role = role
        user.department_id = department_id or None
        log_activity(current_user, "user_updated", f"{current_user.name} updated user {user.name}.",
                     target_type="user", target_id=user.id)
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", departments=departments, user=user, form=None)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def user_toggle_active(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "error")
        return redirect(url_for("admin.users"))

    user.is_active = not user.is_active
    action = "user_activated" if user.is_active else "user_deactivated"
    log_activity(current_user, action, f"{current_user.name} {'activated' if user.is_active else 'deactivated'} {user.name}.",
                 target_type="user", target_id=user.id)
    db.session.commit()
    flash(f"User {'activated' if user.is_active else 'deactivated'}.", "success")
    return redirect(request.referrer or url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def user_reset_password(user_id):
    user = db.session.get(User, user_id) or abort(404)
    temp_password = secrets.token_urlsafe(9)
    user.set_password(temp_password)
    log_activity(current_user, "password_reset", f"{current_user.name} reset the password for {user.name}.",
                 target_type="user", target_id=user.id)
    db.session.commit()
    flash(f"Password reset for {user.name}. Temporary password: {temp_password}", "success")
    return redirect(request.referrer or url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You can't delete your own account.", "error")
        return redirect(url_for("admin.users"))

    has_history = Ticket.query.filter(
        or_(Ticket.creator_id == user.id, Ticket.assignee_id == user.id)
    ).first()
    if has_history:
        flash("This user has ticket history and can't be deleted. Deactivate them instead.", "error")
        return redirect(url_for("admin.users"))

    name = user.name
    db.session.delete(user)
    log_activity(current_user, "user_deleted", f"{current_user.name} deleted user {name}.")
    try:
        db.session.commit()
        flash(f"User {name} deleted.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("This user can't be deleted due to related records. Deactivate them instead.", "error")
    return redirect(url_for("admin.users"))


# ----------------------------------------------------------- Departments ----

@admin_bp.route("/departments")
@login_required
@admin_required
def departments():
    all_departments = Department.query.order_by(Department.name).all()
    return render_template("admin/departments.html", departments=all_departments)


@admin_bp.route("/departments/create", methods=["GET", "POST"])
@login_required
@admin_required
def department_create():
    managers = User.query.filter(User.role.in_([Role.MANAGER, Role.ADMIN, Role.SUPER_ADMIN]), User.is_active.is_(True)).order_by(User.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        manager_id = request.form.get("manager_id", type=int)

        if not name:
            flash("Department name is required.", "error")
        elif Department.query.filter_by(name=name).first():
            flash("A department with this name already exists.", "error")
        else:
            department = Department(name=name, description=description, manager_id=manager_id or None)
            db.session.add(department)
            db.session.flush()
            log_activity(current_user, "department_created", f"{current_user.name} created department {name}.",
                         target_type="department", target_id=department.id)
            db.session.commit()
            flash(f"Department {name} created.", "success")
            return redirect(url_for("admin.departments"))

    return render_template("admin/department_form.html", department=None, managers=managers)


@admin_bp.route("/departments/<int:department_id>")
@login_required
@admin_required
def department_detail(department_id):
    department = db.session.get(Department, department_id) or abort(404)
    members = User.query.filter_by(department_id=department.id).order_by(User.name).all()
    stats = {
        status: Ticket.query.filter_by(department_id=department.id, status=status).count()
        for status in TicketStatus.ORDER
    }
    return render_template("admin/department_detail.html", department=department, members=members, stats=stats)


@admin_bp.route("/departments/<int:department_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def department_edit(department_id):
    department = db.session.get(Department, department_id) or abort(404)
    managers = User.query.filter(User.role.in_([Role.MANAGER, Role.ADMIN, Role.SUPER_ADMIN]), User.is_active.is_(True)).order_by(User.name).all()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        manager_id = request.form.get("manager_id", type=int)

        existing = Department.query.filter(Department.name == name, Department.id != department.id).first()
        if not name:
            flash("Department name is required.", "error")
        elif existing:
            flash("Another department already uses this name.", "error")
        else:
            department.name = name
            department.description = description
            department.manager_id = manager_id or None
            log_activity(current_user, "department_updated", f"{current_user.name} updated department {name}.",
                         target_type="department", target_id=department.id)
            db.session.commit()
            flash("Department updated.", "success")
            return redirect(url_for("admin.departments"))

    return render_template("admin/department_form.html", department=department, managers=managers)


@admin_bp.route("/departments/<int:department_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def department_toggle_active(department_id):
    department = db.session.get(Department, department_id) or abort(404)
    department.is_active = not department.is_active
    log_activity(
        current_user, "department_updated",
        f"{current_user.name} {'enabled' if department.is_active else 'disabled'} department {department.name}.",
        target_type="department", target_id=department.id,
    )
    db.session.commit()
    flash(f"Department {'enabled' if department.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.departments"))


# ------------------------------------------------------------ Categories ----

@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@admin_required
def categories():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Category name is required.", "error")
        elif Category.query.filter_by(name=name).first():
            flash("This category already exists.", "error")
        else:
            category = Category(name=name)
            db.session.add(category)
            db.session.flush()
            log_activity(current_user, "category_created", f"{current_user.name} created category {name}.",
                         target_type="category", target_id=category.id)
            db.session.commit()
            flash(f"Category {name} created.", "success")
        return redirect(url_for("admin.categories"))

    all_categories = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=all_categories)


@admin_bp.route("/categories/<int:category_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def category_toggle_active(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    category.is_active = not category.is_active
    db.session.commit()
    flash(f"Category {'enabled' if category.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.categories"))

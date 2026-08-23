import os

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    abort, send_from_directory, current_app, jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import or_, case

from app.extensions import db
from app.models import (
    Ticket, TicketMessage, TicketAttachment, User, Department, Category,
    TicketStatus, TicketPriority, Role, NotificationType, Notification,
)
from app.utils import log_activity, notify, notify_many, save_upload

tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


def visible_tickets_query(user):
    if user.is_admin_like():
        return Ticket.query
    conditions = [
        Ticket.creator_id == user.id,
        Ticket.recipient_user_id == user.id,
        Ticket.assignee_id == user.id,
    ]
    if user.department_id:
        conditions.append(Ticket.department_id == user.department_id)
    return Ticket.query.filter(or_(*conditions))


def apply_filters(query):
    status = request.args.get("status")
    priority = request.args.get("priority")
    category_id = request.args.get("category", type=int)
    department_id = request.args.get("department", type=int)
    assignee_id = request.args.get("assignee", type=int)
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")

    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if category_id:
        query = query.filter(Ticket.category_id == category_id)
    if department_id:
        query = query.filter(Ticket.department_id == department_id)
    if assignee_id:
        query = query.filter(Ticket.assignee_id == assignee_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Ticket.title.ilike(like), Ticket.description.ilike(like)))

    if sort == "oldest":
        query = query.order_by(Ticket.created_at.asc())
    elif sort == "priority":
        # Highest priority first: urgent > high > medium > low.
        weight = case(
            *[(p, w) for p, w in TicketPriority.WEIGHT.items()],
            value=Ticket.priority,
        )
        query = query.order_by(weight.desc(), Ticket.created_at.desc())
    elif sort == "updated":
        query = query.order_by(Ticket.updated_at.desc())
    else:
        query = query.order_by(Ticket.created_at.desc())

    return query


def _render_list(base_query, title, empty_hint, endpoint):
    query = apply_filters(base_query)
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["ITEMS_PER_PAGE"]
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "tickets/list.html",
        tickets=pagination.items,
        pagination=pagination,
        title=title,
        empty_hint=empty_hint,
        endpoint=endpoint,
        categories=Category.query.filter_by(is_active=True).order_by(Category.name).all(),
        departments=Department.query.filter_by(is_active=True).order_by(Department.name).all(),
    )


@tickets_bp.route("/")
@login_required
def my_tickets():
    base = Ticket.query.filter(Ticket.creator_id == current_user.id)
    return _render_list(base, "My Tickets", "You haven't created any requests yet.", "tickets.my_tickets")


@tickets_bp.route("/inbox")
@login_required
def inbox():
    conditions = [Ticket.recipient_user_id == current_user.id, Ticket.assignee_id == current_user.id]
    if current_user.department_id:
        conditions.append(Ticket.department_id == current_user.department_id)
    base = Ticket.query.filter(or_(*conditions))
    return _render_list(base, "Inbox", "No incoming requests right now.", "tickets.inbox")


@tickets_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    employees = User.query.filter_by(is_active=True).order_by(User.name).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        category_id = request.form.get("category_id", type=int)
        priority = request.form.get("priority", TicketPriority.MEDIUM)
        recipient_type = request.form.get("recipient_type")
        recipient_user_id = request.form.get("recipient_user_id", type=int)
        recipient_department_id = request.form.get("recipient_department_id", type=int)

        errors = []
        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if priority not in TicketPriority.ORDER:
            errors.append("Invalid priority.")
        if recipient_type == "user" and not recipient_user_id:
            errors.append("Please select a recipient employee.")
        elif recipient_type == "department" and not recipient_department_id:
            errors.append("Please select a recipient department.")
        elif recipient_type not in ("user", "department"):
            errors.append("Please choose who this request goes to.")

        files = [f for f in request.files.getlist("attachments") if f and f.filename]
        if len(files) > 5:
            errors.append("You can attach up to 5 files.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "tickets/create.html", employees=employees, departments=departments,
                categories=categories, form=request.form,
            )

        ticket = Ticket(
            title=title,
            description=description,
            category_id=category_id or None,
            priority=priority,
            status=TicketStatus.OPEN,
            creator_id=current_user.id,
        )
        if recipient_type == "user":
            recipient = db.session.get(User, recipient_user_id)
            if not recipient or not recipient.is_active:
                flash("Selected employee is not available.", "error")
                return render_template(
                    "tickets/create.html", employees=employees, departments=departments,
                    categories=categories, form=request.form,
                )
            ticket.recipient_user_id = recipient.id
            ticket.department_id = recipient.department_id
            ticket.assignee_id = recipient.id
        else:
            department = db.session.get(Department, recipient_department_id)
            if not department or not department.is_active:
                flash("Selected department is not available.", "error")
                return render_template(
                    "tickets/create.html", employees=employees, departments=departments,
                    categories=categories, form=request.form,
                )
            ticket.department_id = department.id
            ticket.assignee_id = department.manager_id

        db.session.add(ticket)
        db.session.flush()  # assign ticket.id

        opening_message = TicketMessage(ticket_id=ticket.id, sender_id=current_user.id, body=description)
        db.session.add(opening_message)
        db.session.flush()

        for file_storage in files:
            try:
                stored_name, original_name, size = save_upload(file_storage, f"ticket_{ticket.id}")
            except ValueError as exc:
                flash(str(exc), "error")
                continue
            db.session.add(TicketAttachment(
                ticket_id=ticket.id, message_id=opening_message.id, uploader_id=current_user.id,
                original_filename=original_name, stored_filename=stored_name,
                content_type=file_storage.content_type, size_bytes=size,
            ))

        log_activity(
            current_user, "ticket_created",
            f"{current_user.name} created ticket {ticket.ticket_number}: \"{title}\"",
            target_type="ticket", target_id=ticket.id,
        )

        recipients = []
        if ticket.recipient_user_id:
            recipients.append(db.session.get(User, ticket.recipient_user_id))
        elif ticket.department_id:
            recipients = User.query.filter_by(department_id=ticket.department_id, is_active=True).all()
        notify_many(
            recipients, NotificationType.NEW_TICKET,
            f"New request: {ticket.ticket_number}",
            body=title, ticket=ticket, exclude_user_id=current_user.id,
        )

        db.session.commit()
        flash(f"Ticket successfully created. Your request has been sent.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    return render_template(
        "tickets/create.html", employees=employees, departments=departments,
        categories=categories, form={},
    )


@tickets_bp.route("/<int:ticket_id>")
@login_required
def detail(ticket_id):
    ticket = db.session.get(Ticket, ticket_id) or abort(404)
    if not ticket.can_view(current_user):
        abort(403)

    show_internal_notes = current_user.is_admin_like() or current_user.role == Role.MANAGER or current_user.id == ticket.assignee_id
    messages = [m for m in ticket.messages if not m.is_internal_note or show_internal_notes]

    # Mark related notifications for this ticket as read when the user opens it.
    Notification.query.filter_by(user_id=current_user.id, ticket_id=ticket.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()

    assignable_users = []
    if ticket.department_id:
        assignable_users = User.query.filter_by(department_id=ticket.department_id, is_active=True).order_by(User.name).all()
    elif current_user.is_admin_like():
        assignable_users = User.query.filter_by(is_active=True).order_by(User.name).all()

    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        messages=messages,
        can_manage=ticket.can_manage(current_user),
        assignable_users=assignable_users,
        show_internal_notes=show_internal_notes,
    )


@tickets_bp.route("/<int:ticket_id>/reply", methods=["POST"])
@login_required
def reply(ticket_id):
    ticket = db.session.get(Ticket, ticket_id) or abort(404)
    if not ticket.can_view(current_user):
        abort(403)

    body = (request.form.get("body") or "").strip()
    is_internal_note = bool(request.form.get("is_internal_note")) and ticket.can_manage(current_user)
    files = [f for f in request.files.getlist("attachments") if f and f.filename]

    if not body and not files:
        flash("Write a message or attach a file before sending.", "error")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    message = TicketMessage(ticket_id=ticket.id, sender_id=current_user.id, body=body or "(attachment)",
                             is_internal_note=is_internal_note)
    db.session.add(message)
    db.session.flush()

    for file_storage in files[:5]:
        try:
            stored_name, original_name, size = save_upload(file_storage, f"ticket_{ticket.id}")
        except ValueError as exc:
            flash(str(exc), "error")
            continue
        db.session.add(TicketAttachment(
            ticket_id=ticket.id, message_id=message.id, uploader_id=current_user.id,
            original_filename=original_name, stored_filename=stored_name,
            content_type=file_storage.content_type, size_bytes=size,
        ))

    if not is_internal_note and ticket.status == TicketStatus.RESOLVED:
        ticket.status = TicketStatus.IN_PROGRESS

    log_activity(
        current_user, "message_sent",
        f"{current_user.name} {'added an internal note on' if is_internal_note else 'replied to'} ticket {ticket.ticket_number}.",
        target_type="ticket", target_id=ticket.id,
    )

    if not is_internal_note:
        recipients = {ticket.creator, ticket.recipient_user, ticket.assignee}
        recipients.discard(None)
        notify_many(
            recipients, NotificationType.NEW_REPLY,
            f"New reply on {ticket.ticket_number}",
            body=body[:180] if body else "New attachment", ticket=ticket,
            exclude_user_id=current_user.id,
        )

    db.session.commit()
    flash("Internal note added." if is_internal_note else "Message sent.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.route("/<int:ticket_id>/status", methods=["POST"])
@login_required
def change_status(ticket_id):
    ticket = db.session.get(Ticket, ticket_id) or abort(404)
    if not ticket.can_manage(current_user):
        abort(403)

    new_status = request.form.get("status")
    if new_status not in TicketStatus.ORDER:
        flash("Invalid status.", "error")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    old_status = ticket.status
    ticket.status = new_status
    from datetime import datetime
    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = datetime.utcnow()
    if new_status == TicketStatus.CLOSED:
        ticket.closed_at = datetime.utcnow()

    log_activity(
        current_user, "status_changed",
        f"{current_user.name} changed ticket {ticket.ticket_number} status from "
        f"{TicketStatus.LABELS[old_status]} to {TicketStatus.LABELS[new_status]}.",
        target_type="ticket", target_id=ticket.id,
    )

    recipients = {ticket.creator, ticket.assignee}
    recipients.discard(None)
    notify_many(
        recipients, NotificationType.STATUS_CHANGED,
        f"{ticket.ticket_number} is now {TicketStatus.LABELS[new_status]}",
        ticket=ticket, exclude_user_id=current_user.id,
    )

    db.session.commit()
    flash(f"Status updated to {TicketStatus.LABELS[new_status]}.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.route("/<int:ticket_id>/priority", methods=["POST"])
@login_required
def change_priority(ticket_id):
    ticket = db.session.get(Ticket, ticket_id) or abort(404)
    if not ticket.can_manage(current_user):
        abort(403)

    new_priority = request.form.get("priority")
    if new_priority not in TicketPriority.ORDER:
        flash("Invalid priority.", "error")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    old_priority = ticket.priority
    ticket.priority = new_priority
    log_activity(
        current_user, "priority_changed",
        f"{current_user.name} changed ticket {ticket.ticket_number} priority from "
        f"{TicketPriority.LABELS[old_priority]} to {TicketPriority.LABELS[new_priority]}.",
        target_type="ticket", target_id=ticket.id,
    )
    db.session.commit()
    flash(f"Priority updated to {TicketPriority.LABELS[new_priority]}.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.route("/<int:ticket_id>/assign", methods=["POST"])
@login_required
def assign(ticket_id):
    ticket = db.session.get(Ticket, ticket_id) or abort(404)
    if not ticket.can_manage(current_user):
        abort(403)

    assignee_id = request.form.get("assignee_id", type=int)
    new_assignee = db.session.get(User, assignee_id) if assignee_id else None
    if assignee_id and not new_assignee:
        flash("Selected user not found.", "error")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    old_assignee = ticket.assignee
    ticket.assignee_id = new_assignee.id if new_assignee else None
    if ticket.status == TicketStatus.OPEN and new_assignee:
        ticket.status = TicketStatus.IN_PROGRESS

    description = (
        f"{current_user.name} reassigned ticket {ticket.ticket_number} to {new_assignee.name}."
        if new_assignee else
        f"{current_user.name} unassigned ticket {ticket.ticket_number}."
    )
    log_activity(current_user, "ticket_reassigned", description, target_type="ticket", target_id=ticket.id)

    if new_assignee:
        notify(
            new_assignee, NotificationType.ASSIGNED,
            f"Ticket {ticket.ticket_number} assigned to you",
            body=ticket.title, ticket=ticket,
        )
    db.session.commit()
    flash("Ticket assignment updated.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.route("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    attachment = db.session.get(TicketAttachment, attachment_id) or abort(404)
    if not attachment.ticket.can_view(current_user):
        abort(403)
    directory = os.path.join(current_app.config["UPLOAD_FOLDER"], f"ticket_{attachment.ticket_id}")
    return send_from_directory(directory, attachment.stored_filename, as_attachment=True,
                                download_name=attachment.original_filename)

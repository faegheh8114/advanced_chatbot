from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Notification, Ticket, TicketMessage, Department,
    TicketStatus, TicketPriority, Role,
)
from app.decorators import admin_required
from app.template_helpers import get_locale
from app.translations import STATUS_LABELS, PRIORITY_LABELS, DEFAULT_LOCALE

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/notifications/summary")
@login_required
def notifications_summary():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(8)
        .all()
    )
    return jsonify({
        "unread_count": current_user.unread_notification_count(),
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "ticket_id": n.ticket_id,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() + "Z",
            }
            for n in items
        ],
    })


@api_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.user_id != current_user.id:
        abort(404)
    notification.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/tickets/<int:ticket_id>/messages")
@login_required
def ticket_messages(ticket_id):
    ticket = db.session.get(Ticket, ticket_id) or abort(404)
    if not ticket.can_view(current_user):
        abort(403)

    after_id = request.args.get("after_id", type=int, default=0)
    show_internal_notes = (
        current_user.is_admin_like() or current_user.role == Role.MANAGER or current_user.id == ticket.assignee_id
    )

    query = TicketMessage.query.filter(TicketMessage.ticket_id == ticket.id, TicketMessage.id > after_id)
    if not show_internal_notes:
        query = query.filter(TicketMessage.is_internal_note.is_(False))
    messages = query.order_by(TicketMessage.created_at.asc()).all()

    def serialize(m):
        return {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": m.sender.name,
            "sender_initials": m.sender.initials,
            "sender_color": m.sender.avatar_color,
            "body": m.body,
            "is_internal_note": m.is_internal_note,
            "created_at": m.created_at.isoformat() + "Z",
            "attachments": [
                {"id": a.id, "name": a.original_filename, "size": a.human_size(), "is_image": a.is_image}
                for a in m.attachments
            ],
        }

    return jsonify({"messages": [serialize(m) for m in messages], "status": ticket.status})


@api_bp.route("/analytics/overview")
@login_required
@admin_required
def analytics_overview():
    since = datetime.utcnow() - timedelta(days=13)
    daily_counts = (
        db.session.query(func.date(Ticket.created_at), func.count(Ticket.id))
        .filter(Ticket.created_at >= since)
        .group_by(func.date(Ticket.created_at))
        .all()
    )
    volume_map = {str(d): c for d, c in daily_counts}
    volume_series = []
    for i in range(14):
        day = (since + timedelta(days=i)).date()
        volume_series.append({"label": day.strftime("%b %d"), "value": volume_map.get(str(day), 0)})

    by_department = (
        db.session.query(Department.name, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.department_id == Department.id)
        .group_by(Department.id)
        .all()
    )

    by_status = (
        db.session.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    )
    locale = get_locale()
    status_labels = STATUS_LABELS.get(locale, STATUS_LABELS[DEFAULT_LOCALE])
    priority_labels = PRIORITY_LABELS.get(locale, PRIORITY_LABELS[DEFAULT_LOCALE])

    status_map = dict(by_status)
    status_series = [
        {"label": status_labels[s], "value": status_map.get(s, 0)} for s in TicketStatus.ORDER
    ]

    by_priority = (
        db.session.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    )
    priority_map = dict(by_priority)
    priority_series = [
        {"label": priority_labels[p], "value": priority_map.get(p, 0)} for p in TicketPriority.ORDER
    ]

    return jsonify({
        "volume": volume_series,
        "by_department": [{"label": name, "value": count} for name, count in by_department],
        "by_status": status_series,
        "by_priority": priority_series,
    })

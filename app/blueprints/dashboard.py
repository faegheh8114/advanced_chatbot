from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Ticket, TicketMessage, Notification, ActivityLog, TicketStatus, TicketPriority, Role
from app.extensions import db
from sqlalchemy import or_, and_

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _visible_tickets_query(user):
    """Tickets this user is allowed to see, matching Ticket.can_view semantics."""
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


@dashboard_bp.route("/")
@login_required
def index():
    user = current_user
    base = _visible_tickets_query(user)

    counts = {
        "open": base.filter(Ticket.status == TicketStatus.OPEN).count(),
        "in_progress": base.filter(Ticket.status == TicketStatus.IN_PROGRESS).count(),
        "waiting": base.filter(Ticket.status == TicketStatus.WAITING).count(),
        "resolved": base.filter(Ticket.status == TicketStatus.RESOLVED).count(),
        "closed": base.filter(Ticket.status == TicketStatus.CLOSED).count(),
        "urgent": base.filter(
            Ticket.priority == TicketPriority.URGENT,
            Ticket.status.in_(TicketStatus.ACTIVE),
        ).count(),
    }

    my_open_tickets = base.filter(Ticket.status.in_(TicketStatus.ACTIVE)).count()

    recent_tickets = base.order_by(Ticket.updated_at.desc()).limit(6).all()

    # Recent conversation activity: latest messages on tickets visible to the user,
    # excluding the user's own messages (i.e. "someone replied to me").
    visible_ticket_ids = [t.id for t in base.with_entities(Ticket.id).all()]
    recent_replies = (
        TicketMessage.query.filter(
            TicketMessage.ticket_id.in_(visible_ticket_ids),
            TicketMessage.sender_id != user.id,
            TicketMessage.is_internal_note.is_(False),
        )
        .order_by(TicketMessage.created_at.desc())
        .limit(6)
        .all()
    )

    unread_notifications = (
        Notification.query.filter_by(user_id=user.id, is_read=False)
        .order_by(Notification.created_at.desc())
        .limit(6)
        .all()
    )

    recent_activity = (
        ActivityLog.query.filter(ActivityLog.actor_id == user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard/user_dashboard.html",
        counts=counts,
        my_open_tickets=my_open_tickets,
        recent_tickets=recent_tickets,
        recent_replies=recent_replies,
        unread_notifications=unread_notifications,
        recent_activity=recent_activity,
        unread_messages_count=len(recent_replies),
    )
